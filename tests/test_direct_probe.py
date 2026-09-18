"""Offline checks for the opt-in probe: no real credentials or network calls."""

import base64
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/probe_direct_usage.py"
SPEC = importlib.util.spec_from_file_location("direct_probe", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class MetricsTests(unittest.TestCase):
    def test_weekly_primary_does_not_invent_session(self):
        result = {"rateLimitsByLimitId": {"codex": {"primary": {
            "usedPercent": 76, "windowDurationMins": 10080, "resetsAt": 1789805443}}}}
        metrics = probe.codex_metrics(result)
        self.assertEqual([item["id"] for item in metrics], ["codex.weekly"])
        self.assertEqual(metrics[0]["remaining_percent"], 24)

    def test_all_codex_buckets_and_unknown_windows_survive(self):
        result = {"rateLimitsByLimitId": {
            "codex": {"primary": {"usedPercent": 0, "windowDurationMins": 300}},
            "other": {"primary": {"usedPercent": 25, "windowDurationMins": 60}}}}
        metrics = probe.codex_metrics(result)
        self.assertEqual([item["id"] for item in metrics], ["codex.session", "other.primary"])
        self.assertEqual(metrics[1]["window_minutes"], 60)
        self.assertIsNone(metrics[0]["resets_at"])

    def test_missing_and_invalid_quotas_are_not_zero(self):
        buckets = [{"bucketId": "missing"}, {"bucketId": "boolean", "remainingFraction": True},
                   {"bucketId": "nan", "remainingFraction": float("nan")},
                   {"bucketId": "range", "remainingFraction": 1.5},
                   {"bucketId": "full", "remainingFraction": 1}]
        metrics = probe.antigravity_metrics({"response": {"groups": [{"buckets": buckets}]}})
        self.assertEqual([item["id"] for item in metrics], ["full"])
        self.assertEqual(metrics[0]["used_percent"], 0)
        self.assertIsNone(metrics[0]["resets_at"])
        self.assertEqual(probe.claude_metrics({"five_hour": {"utilization": None}}), [])
        self.assertEqual(probe.codex_metrics({"rateLimits": {"primary": {}}}), [])

    def test_only_usage_fields_are_emitted(self):
        payload = {"five_hour": {"utilization": 5, "resets_at": "token-secret",
                                 "access_token": "token-secret", "email": "private@example.com"},
                   "extra_usage": {"is_enabled": False, "monthly_limit": 2000, "used_credits": 2100,
                                   "access_token": "token-secret"}}
        metrics = probe.claude_metrics(payload)
        encoded = json.dumps(metrics)
        self.assertNotIn("token-secret", encoded)
        self.assertNotIn("private@example.com", encoded)
        self.assertIsNone(metrics[0]["resets_at"])
        self.assertNotIn("used_percent", metrics[1])
        self.assertEqual(metrics[1]["used_credits"], 2100)

    def test_errors_cannot_leak_response_or_credentials(self):
        def failing():
            raise ValueError("Authorization: Bearer token-secret, private@example.com")
        result = probe.run_probe("test", failing)
        self.assertEqual(result["error_type"], "ValueError")
        self.assertNotIn("token-secret", json.dumps(result))

    def test_keychain_timeout_is_reported_without_subprocess_output(self):
        error = probe.subprocess.TimeoutExpired("security", 20, output=b"token-secret")
        with patch.object(probe.sys, "platform", "darwin"), \
                patch.object(probe.subprocess, "run", side_effect=error):
            result = probe.run_probe("claude", lambda: probe.keychain("Claude Code-credentials"))
        self.assertEqual(result["status"], "keychain_read_timeout")
        self.assertNotIn("token-secret", json.dumps(result))


class DesktopAccountTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.root = self.home / "Library/Application Support/Claude"
        self.root.mkdir(parents=True)
        connection = sqlite3.connect(self.root / "Cookies")
        connection.execute("CREATE TABLE cookies (host_key, name, value, encrypted_value, last_update_utc)")
        connection.execute("INSERT INTO cookies VALUES (?, ?, ?, ?, ?)",
                           (".claude.ai", "lastActiveOrg", "our-org", b"", 1))
        connection.commit()
        connection.close()
        self.key = "9d1c250a-e61b-44d9-88ed-5944d1962f5e:our-org:https://api.anthropic.com:user:profile user:inference"
        self.future = time.time() * 1000 + 3600000

    def read(self, v1, v2):
        config = {"lastKnownAccountUuid": "our-account"}
        for name, data in (("oauth:tokenCache", v1), ("oauth:tokenCacheV2", v2)):
            config[name] = base64.b64encode(json.dumps(data).encode()).decode()
        (self.root / "config.json").write_text(json.dumps(config))
        with patch.object(probe.sys, "platform", "darwin"), patch.object(probe.Path, "home", return_value=self.home), \
                patch.object(probe, "keychain", return_value=b"synthetic-password"), \
                patch.object(probe, "desktop_decrypt", side_effect=lambda data, key: data):
            return probe.desktop_token()

    def entry(self, token, expiry=None):
        return {"token": token, "expiresAt": self.future if expiry is None else expiry}

    def test_scoped_current_account_wins_over_legacy_and_foreign(self):
        other_org = self.key.replace(":our-org:", ":other-org:")
        v2 = {self.key: self.entry("legacy"),
              "acct:our-account|" + self.key: self.entry("expected"),
              "acct:foreign-account|" + self.key: self.entry("wrong-account", self.future + 100000),
              other_org: self.entry("wrong-org", self.future + 100000)}
        self.assertEqual(self.read({}, v2), "expected")

    def test_v2_deletion_does_not_resurrect_old_login(self):
        with self.assertRaisesRegex(probe.ProbeError, "desktop_login_expired_or_missing"):
            self.read({self.key: self.entry("old")}, {"acct:our-account|" + self.key: None})

    def test_expired_login_is_not_used(self):
        with self.assertRaisesRegex(probe.ProbeError, "desktop_login_expired_or_missing"):
            self.read({}, {self.key: self.entry("expired", 1)})


if __name__ == "__main__":
    unittest.main()
