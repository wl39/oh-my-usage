import base64
import fcntl
import contextlib
import io
import json
import os
import plistlib
import pty
import select
import subprocess
import tempfile
import threading
import time
import unittest
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from oh_my_usage import __version__, cache, config, metrics, settings, source
from oh_my_usage.diagnostics import doctor
from oh_my_usage.render import render
from scripts import install

ROOT = Path(__file__).resolve().parent.parent
NOW = 1789473600


def usage():
    return [{"providerId": "codex", "displayName": "Codex",
             "fetchedAt": "2026-09-15T12:00:00Z", "lines": [
                 {"type": "progress", "label": "Session", "used": 42, "limit": 100,
                  "format": {"kind": "percent"}},
                 {"type": "progress", "label": "Weekly", "used": 10, "limit": 100,
                  "format": {"kind": "percent"}},
             ]}]


def prefs():
    return settings.Settings(("codex.session", "codex.weekly"), ("codex",),
                             ("codex",), {"codex": ("codex.weekly", "codex.session")}, ())


def write_prefs(path, value=None):
    value = value or prefs()
    path.write_bytes(plistlib.dumps({
        "openusage.layout.v1.menuBarPins": list(value.pins),
        "openusage.enabledProviders.v1": list(value.enabled),
        "openusage.layout.v1.providerOrder": json.dumps(value.providers).encode(),
        "openusage.layout.v1.metricOrderByProvider": json.dumps(value.metric_order).encode(),
        "openusage.layout.v1.expandedMetrics": list(value.expanded),
        "meterStyle": "remaining" if value.remaining else "used",
        "openusage.layout.v1.menuBarStyle": "bars" if value.bars else "text",
    }))


class RenderingTests(unittest.TestCase):
    def test_icons_show_remaining_percent_and_identify_multiple_periods(self):
        self.assertEqual(render(usage(), replace(prefs(), remaining=True, bars=True), NOW,
                                style="icons"), "◇ W:90%/S:58% (left)")
        self.assertEqual(render(usage(), replace(prefs(), pins=("codex.session",), remaining=True),
                                NOW, style="icons", icons="ascii"), "CX 58% (left)")

    def test_icons_preserve_staleness_unknown_providers_and_nonpercentage_data(self):
        data = usage()
        data[0].update(providerId="new", displayName="New\x1b\nProvider")
        p = replace(prefs(), pins=("new.session",), enabled=("new",), remaining=True, bars=True)
        data[0]["lines"][0].update(used=25, limit=50, format={"kind": "dollars"})
        self.assertEqual(render(data, p, NOW + 601, True, style="icons"),
                         "NewProvider~ 50% (left) [offline]")
        data[0]["lines"][0] = {"type": "text", "label": "Session", "value": "$5.00"}
        self.assertEqual(render(data, p, NOW, style="icons"), "NewProvider $5.00 (left)")
        data[0]["lines"][0] = {"type": "progress", "label": "Session", "used": None, "limit": 100}
        self.assertEqual(render(data, p, NOW, style="icons"), "OpenUsage: no pinned data")

    def test_provider_label_aliases(self):
        for descriptor, label in (("claude.extra", "Extra usage spent"),
                                  ("cursor.auto", "Cursor Models"),
                                  ("cursor.auto", "Auto Usage"),
                                  ("devin.daily", "Daily quota"),
                                  ("openrouter.week", "This Week")):
            p = {"providerId": descriptor.split(".")[0], "lines": [{"label": label}]}
            self.assertEqual(metrics.row_for(descriptor, p), {"label": label})

    def test_order_and_left_mode(self):
        self.assertEqual(render(usage(), replace(prefs(), remaining=True), NOW),
                         "Codex Weekly 90%/Session 58% (left)")

    def test_expand_partition_precedes_metric_order(self):
        self.assertIn("Session 42%/Weekly 10%", render(
            usage(), replace(prefs(), expanded=("codex.weekly",)), NOW))

    def test_disabled_or_unpinned_is_never_shown(self):
        for p in (replace(prefs(), enabled=()), replace(prefs(), pins=())):
            self.assertEqual(render(usage(), p, NOW), "OpenUsage: no pinned data")

    def test_missing_pin_has_no_fabricated_zero(self):
        data = usage()
        data[0]["lines"] = data[0]["lines"][:1]
        self.assertEqual(render(data, prefs(), NOW), "Codex Session 42% (used)")

    def test_stale_and_offline_are_visible(self):
        text = render(usage(), prefs(), NOW + 601, offline=True)
        self.assertIn("Codex~", text)
        self.assertTrue(text.endswith("[offline]"))

    def test_control_characters_are_removed(self):
        self.assertEqual(metrics.clean("ok\x1b\a\n\r\u202ebad"), "okbad")

    def test_units_and_zero(self):
        row = {"type": "progress", "used": 12.5, "limit": 20, "format": {"kind": "dollars"}}
        self.assertEqual(metrics.reading(row, True)[0], "$7.50")
        row["format"] = {"kind": "count"}
        self.assertEqual(metrics.reading(row, True)[0], "7.5")
        row.update(used=0, limit=100, format={"kind": "percent"})
        self.assertEqual(metrics.reading(row, False)[0], "0%")
        row["used"] = 200
        self.assertEqual(metrics.reading(row, True)[0], "0%")
        self.assertEqual(metrics.reading(row, False)[0], "100%")

    def test_bad_numbers_and_formats(self):
        for invalid in (None, "42", True, float("nan"), float("inf")):
            row = {"type": "progress", "used": invalid, "limit": 100}
            self.assertIsNone(metrics.reading(row, False))
        self.assertIsNone(metrics.reading({"type": "progress", "used": 1, "limit": 0}, False))

    def test_text_uses_first_value_and_preserves_empty_balance(self):
        row = {"type": "text", "label": "Today", "value": "$5.17 · 9.2M tokens"}
        self.assertEqual(metrics.reading(row, False)[0], "$5.17")
        row["value"] = "0 credits"
        self.assertEqual(metrics.reading(row, False)[0], "0 credits")

    def test_bars_have_global_four_metric_cap(self):
        data, p = [], prefs()
        for name in ("codex", "claude", "opencode"):
            provider = usage()[0]
            provider.update(providerId=name, displayName=name)
            data.append(provider)
        p = replace(p, providers=(), enabled=tuple(d["providerId"] for d in data), bars=True,
                    pins=tuple(d["providerId"] + "." + m for d in data for m in ("session", "weekly")))
        result = render(data, p, NOW)
        self.assertEqual(result.count("["), 4)
        self.assertNotIn("opencode", result)


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "cache"
        self.preferences = Path(self.temp.name) / "preferences.plist"
        write_prefs(self.preferences)
        self.fetch = Mock(return_value=usage())
        env = patch.dict(os.environ, {"OH_MY_USAGE_CONFIG_DIR": str(Path(self.temp.name) / "config"), "OH_MY_USAGE_SOURCE": "openusage"})
        env.start()
        self.addCleanup(env.stop)

    def refresh(self, **kw):
        return cache.refresh(root=self.root, preferences=self.preferences, fetch=self.fetch, **kw)

    def test_plist_data_is_decoded(self):
        self.assertEqual(settings.load(self.preferences), prefs())

    def test_absent_pins_use_app_defaults_without_writing_preferences(self):
        data = plistlib.loads(self.preferences.read_bytes())
        del data[settings.LAYOUT + ".menuBarPins"]
        self.preferences.write_bytes(plistlib.dumps(data))
        before = self.preferences.read_bytes()
        self.assertEqual(self.refresh(now=NOW), "Codex Weekly 10%/Session 42% (used)")
        self.assertTrue(settings.load(self.preferences).pins_from_defaults)
        self.assertEqual(self.preferences.read_bytes(), before)

    def test_explicit_empty_and_malformed_pins_never_fall_back(self):
        for pins in ([], None, "codex.session"):
            with patch("oh_my_usage.settings.read_preferences", return_value={
                    settings.LAYOUT + ".menuBarPins": pins,
                    "openusage.enabledProviders.v1": ["codex"]}):
                if pins == []:
                    parsed = settings.load()
                    self.assertFalse(parsed.pins_from_defaults)
                    self.assertEqual(render(usage(), parsed, NOW), "OpenUsage: no pinned data")
                else:
                    with self.assertRaises(settings.SettingsError):
                        settings.load()

    def test_shared_ttl_and_force(self):
        self.refresh(now=NOW)
        self.refresh(now=NOW + 29)
        self.assertEqual(self.fetch.call_count, 1)
        self.refresh(now=NOW + 29, force=True)
        self.assertEqual(self.fetch.call_count, 2)

    def test_saved_mode_reformats_fresh_cache_without_fetch_or_extending_ttl(self):
        self.refresh(now=NOW)
        before = self.preferences.read_bytes()
        config.save("mode", "left")
        self.assertEqual(self.refresh(now=NOW + 1), "Codex Weekly 90%/Session 58% (left)")
        self.assertEqual(self.fetch.call_count, 1)
        self.assertEqual(cache.display(self.root)[0], NOW)
        self.assertEqual(self.preferences.read_bytes(), before)
        config.reset()
        self.assertIn("(used)", self.refresh(now=NOW + 2))
        self.assertEqual(self.fetch.call_count, 1)
        self.refresh(now=NOW + 30)
        self.assertEqual(self.fetch.call_count, 2)

    def test_icon_cache_is_separate_from_status_and_reformats_without_fetch(self):
        self.refresh(now=NOW)
        config.save("style", "icons")
        config.save("mode", "left")
        self.assertEqual(self.refresh(now=NOW + 1), "Codex Weekly 90%/Session 58% (left)")
        lines = (self.root / "display").read_text().splitlines()
        self.assertEqual(base64.b64decode(lines[2]).decode(), lines[1])
        self.assertEqual(lines[3], "left|auto|icons|unicode")
        self.assertEqual(lines[4], "◇ W:90%/S:58% (left)")
        config.save("icons", "ascii")
        self.refresh(now=NOW + 2)
        self.assertIn("CX W:90%/S:58%", (self.root / "display").read_text())
        self.assertEqual(self.fetch.call_count, 1)
        self.assertEqual(cache.display(self.root)[0], NOW)

    def test_saved_order_keeps_other_enabled_providers_and_offline_marker(self):
        providers = []
        for name in ("codex", "claude", "other"):
            provider = usage()[0]
            provider.update(providerId=name, displayName=name.title())
            providers.append(provider)
        self.fetch.return_value = providers
        write_prefs(self.preferences, replace(prefs(), enabled=("codex", "claude", "other"),
                    providers=("codex", "other", "claude"),
                    pins=("codex.session", "claude.session", "other.session")))
        self.refresh(now=NOW)
        config.save("order", "claude,codex")
        text = self.refresh(now=NOW + 1)
        self.assertLess(text.index("Claude"), text.index("Codex"))
        self.assertLess(text.index("Codex"), text.index("Other"))
        self.assertEqual(self.fetch.call_count, 1)
        self.fetch.side_effect = OSError("offline")
        self.refresh(now=NOW + 40)
        config.save("mode", "left")
        self.assertIn("(left) [offline]", self.refresh(now=NOW + 41))
        self.assertEqual(self.fetch.call_count, 2)

    def test_clock_rollback_refreshes(self):
        self.refresh(now=NOW)
        self.refresh(now=NOW - 3600)
        self.assertEqual(self.fetch.call_count, 2)

    def test_failure_keeps_last_success_and_throttles_retries(self):
        self.refresh(now=NOW)
        self.fetch.side_effect = OSError("offline")
        self.assertIn("Weekly 10%", self.refresh(now=NOW + 40))
        self.assertIn("[offline]", self.refresh(now=NOW + 41))
        self.assertEqual(self.fetch.call_count, 2)
        self.assertEqual(json.loads((self.root / "usage.json").read_text()), usage())

    def test_empty_response_clears_previous_reading(self):
        self.refresh(now=NOW)
        self.fetch.return_value = []
        self.assertEqual(self.refresh(now=NOW + 40), "OpenUsage: no pinned data")

    def test_settings_change_applies_to_offline_data(self):
        self.refresh(now=NOW)
        write_prefs(self.preferences, replace(prefs(), pins=()))
        self.fetch.side_effect = OSError("offline")
        self.assertNotIn("Codex", self.refresh(now=NOW + 40))

    def test_lock_prevents_overlapping_fetch(self):
        self.refresh(now=NOW)
        with (self.root / "lock").open("w") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            self.refresh(now=NOW + 40)
        self.assertEqual(self.fetch.call_count, 1)

    def test_simultaneous_cold_read_waits_for_shared_first_display(self):
        self.root.mkdir()
        with (self.root / "lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            def first_reader():
                time.sleep(0.1)
                (self.root / "display").write_text(f"{NOW}\nReady\nUmVhZHk=\nauto|auto\n")
                fcntl.flock(lock, fcntl.LOCK_UN)
            worker = threading.Thread(target=first_reader)
            worker.start()
            try:
                self.assertEqual(self.refresh(now=NOW), "Ready")
                self.fetch.assert_not_called()
            finally:
                worker.join()

    def test_corrupt_or_missing_settings_do_not_expose_all_providers(self):
        for body, reason in ((b"garbage", "unsupported settings format"),
                             (plistlib.dumps({}), "menu-bar settings not saved")):
            self.preferences.write_bytes(body)
            self.assertIn(reason, self.refresh(now=NOW, force=True))
        self.fetch.assert_not_called()

    def test_private_cache_and_shell_payload(self):
        text = self.refresh(now=NOW)
        stamp, plain, encoded, key, inline = (self.root / "display").read_text().splitlines()
        self.assertEqual(key, "auto|auto")
        self.assertEqual(plain, text)
        self.assertEqual(inline, text)
        self.assertEqual(base64.b64decode(encoded).decode(), text)
        self.assertEqual(int(stamp), NOW)
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        for name in ("display", "usage.json", "lock"):
            self.assertEqual((self.root / name).stat().st_mode & 0o777, 0o600)


class SettingsDiagnosticsTests(unittest.TestCase):
    def test_live_preferences_service_resolves_unflushed_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "prefs.plist"
            write_prefs(path)
            output = path.read_bytes()
        with patch.dict(os.environ, {"OH_MY_USAGE_PREFERENCES": ""}), \
             patch("oh_my_usage.settings.subprocess.run", return_value=Mock(returncode=0, stdout=output)) as run, \
             patch("pathlib.Path.open", side_effect=FileNotFoundError):
            self.assertEqual(settings.load(), prefs())
        run.assert_called_once_with(["/usr/bin/defaults", "export", settings.DOMAIN, "-"],
                                    capture_output=True, timeout=2)

    def test_preferences_service_failure_falls_back_to_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "prefs.plist"
            write_prefs(path)
            with patch.dict(os.environ, {"OH_MY_USAGE_PREFERENCES": ""}), \
                 patch("oh_my_usage.settings.preferences_path", return_value=path), \
                 patch("oh_my_usage.settings.subprocess.run", side_effect=subprocess.TimeoutExpired("defaults", 2)):
                self.assertEqual(settings.load(), prefs())

    def test_error_reasons_are_distinct(self):
        for error, reason in ((FileNotFoundError(), "settings not found"),
                              (PermissionError(), "settings not readable"),
                              (KeyError("openusage.layout.v1.menuBarPins"), "menu-bar settings not saved"),
                              (ValueError(), "unsupported settings format")):
            with patch("oh_my_usage.settings.read_preferences", side_effect=error):
                with self.assertRaises(settings.SettingsError) as caught:
                    settings.load()
            self.assertEqual(caught.exception.summary, reason)

    def test_doctor_probes_api_even_when_settings_fail(self):
        output = io.StringIO()
        error = settings.SettingsError("settings not found", "No preferences in this account.")
        with patch("oh_my_usage.settings.load", side_effect=error), \
             patch("oh_my_usage.source.fetch", return_value=usage()) as fetch, \
             patch("oh_my_usage.cache.atomic_write") as write, contextlib.redirect_stdout(output):
            self.assertEqual(doctor(), 1)
        fetch.assert_called_once()
        write.assert_not_called()
        self.assertIn("Settings: ERROR", output.getvalue())
        self.assertIn("Local API: OK", output.getvalue())
        self.assertNotIn("42", output.getvalue())


class TransportTests(unittest.TestCase):
    def test_http_is_loopback_bounded_and_closed(self):
        response = Mock(status=200)
        response.read.return_value = json.dumps(usage()).encode()
        connection = Mock()
        connection.getresponse.return_value = response
        with patch("oh_my_usage.source.http.client.HTTPConnection", return_value=connection) as factory:
            self.assertEqual(source.fetch(), usage())
        factory.assert_called_once_with("127.0.0.1", 6736, timeout=1.5)
        connection.request.assert_called_once_with("GET", "/v1/usage")
        connection.close.assert_called_once()
        response.read.assert_called_once_with(source.MAX_BYTES + 1)

    def test_bad_http_json_and_oversized_response(self):
        for status, body in ((503, b"[]"), (200, b"broken"), (200, b"x" * (source.MAX_BYTES + 1))):
            connection = Mock()
            connection.getresponse.return_value = Mock(status=status, read=Mock(return_value=body))
            with patch("oh_my_usage.source.http.client.HTTPConnection", return_value=connection):
                with self.assertRaises(ValueError):
                    source.fetch()
            connection.close.assert_called_once()

    def test_malformed_shape_fails(self):
        for value in ({}, [{"providerId": "codex"}], [None]):
            with self.assertRaises(ValueError):
                source.validate(value)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.prefix = self.home / "directory with spaces" / "oh_my_usage"
        self.rc = self.home / ".zshrc"
        self.rc.write_text("# existing user config\nplugins=(git)\n")
        self.env = patch.dict(os.environ, {"ZDOTDIR": str(self.home), "OH_MY_USAGE_CONFIG_DIR": str(self.home / "config")})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_install_reinstall_uninstall_preserves_user_content(self):
        original = self.rc.read_text()
        install.install(self.prefix, self.home)
        install.install(self.prefix, self.home)
        self.assertEqual(self.rc.read_text().count(install.START), 1)
        self.assertTrue(list(self.home.glob(".zshrc.oh-my-usage-backup-*")))
        self.rc.write_text(self.rc.read_text() + "# later user change\n")
        install.install(self.prefix, self.home, shell=False)
        install.uninstall(self.prefix)
        self.assertEqual(self.rc.read_text(), original + "# later user change\n")
        self.assertFalse(self.prefix.exists())
        self.assertFalse((self.home / "Library/Application Support/iTerm2/DynamicProfiles/oh_my_usage.json").exists())

    def test_installed_commands_and_only_public_guides(self):
        install.install(self.prefix, self.home)
        result = subprocess.run([str(self.prefix / "bin/oh-my-usage"), "--version"],
                                cwd=self.home, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), __version__)
        result = subprocess.run(["zsh", "-di", "-c",
                                 'oh-my-usage --version; oh-my-usage inline status'],
                                env=dict(os.environ, PLUGIN=str(self.prefix / "oh-my-usage.plugin.zsh"),
                                         OH_MY_USAGE_INLINE="off", OH_MY_USAGE_DISPLAY="off"),
                                cwd=self.home, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, __version__ + "\ninline: on (saved)\n")
        self.assertEqual({p.name for p in (self.prefix / "docs").iterdir()},
                         {"README.ko.md", "README.zh-CN.md", "providers.md"})
        self.assertFalse((self.prefix / "scripts/check.sh").exists())
        self.assertFalse((self.prefix / "tests").exists())

    def test_legacy_uninstall_preserves_new_shell_block_and_other_cache_files(self):
        legacy = self.home / "legacy-install"
        legacy.mkdir()
        cache_dir = self.home / "legacy-cache"
        cache_dir.mkdir()
        for name in ("display", "usage.json", "lock", "unrelated"):
            (cache_dir / name).write_text("test")
        current_block = install.START + "\n# new plugin\n" + install.END + "\n"
        self.rc.write_text("# user config\n# >>> OUIterm >>>\n# old plugin\n# <<< OUIterm <<<\n"
                           + current_block)
        (legacy / ".ouiterm-install").write_text(json.dumps(
            {"shell": True, "rc": str(self.rc), "cache": str(cache_dir)}))
        result = subprocess.run([str(ROOT / "install.sh"), "uninstall", "--prefix", str(legacy)],
                                env=dict(os.environ, OH_MY_USAGE_PYTHON=sys.executable),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(legacy.exists())
        self.assertEqual(self.rc.read_text(), "# user config\n" + current_block)
        self.assertEqual([p.name for p in cache_dir.iterdir()], ["unrelated"])
        self.assertIn("ouiterm_unload", result.stdout)

    def test_symlink_dotfile_and_permissions_survive(self):
        target = self.home / "actual-zshrc"
        self.rc.rename(target)
        target.chmod(0o640)
        self.rc.symlink_to(target)
        install.install(self.prefix, self.home)
        self.assertTrue(self.rc.is_symlink())
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        install.uninstall(self.prefix)
        self.assertIn("plugins=(git)", target.read_text())

    def test_install_does_not_create_or_modify_iterm_profiles(self):
        p = self.home / "Library/Preferences/com.googlecode.iterm2.plist"
        p.parent.mkdir(parents=True)
        original = plistlib.dumps({"New Bookmarks": [{"Name": "My theme", "Guid": "mine"}]})
        p.write_bytes(original)
        install.install(self.prefix, self.home)
        self.assertEqual(p.read_bytes(), original)
        self.assertFalse((self.home / "Library/Application Support/iTerm2/DynamicProfiles").exists())

    def test_upgrade_removes_only_owned_legacy_profile(self):
        install.install(self.prefix, self.home)
        p = self.home / "old-profile.json"
        p.write_text(json.dumps({"Profiles": [{"Name": "oh-my-usage", "Guid": install.PROFILE_GUID}]}))
        marker = self.prefix / ".oh-my-usage-install"
        manifest = json.loads(marker.read_text())
        manifest.update(iterm=True, profile=str(p))
        marker.write_text(json.dumps(manifest))
        install.install(self.prefix, self.home)
        self.assertFalse(p.exists())
        self.assertNotIn("profile", json.loads(marker.read_text()))
        # A file subsequently changed into another user's profile must survive.
        p.write_text(json.dumps({"Profiles": [{"Guid": "unrelated"}]}))
        install.remove_legacy_profile(manifest)
        self.assertTrue(p.exists())

    def test_installed_uninstaller_and_cache_cleanup(self):
        install.install(self.prefix, self.home)
        directory = Path(json.loads((self.prefix / ".oh-my-usage-install").read_text())["cache"])
        directory.mkdir(parents=True)
        for name in ("display", "usage.json", "lock", "unrelated"):
            (directory / name).write_text("test")
        env = dict(os.environ, OH_MY_USAGE_PYTHON="", PATH="/usr/bin:/bin")
        result = subprocess.run([str(self.prefix / "install.sh"), "uninstall"], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.prefix.exists())
        self.assertEqual(self.rc.read_text(), "# existing user config\nplugins=(git)\n")
        self.assertEqual([p.name for p in directory.iterdir()], ["unrelated"])

    def test_refuse_unrelated_directory_and_broken_markers(self):
        self.prefix.mkdir(parents=True)
        (self.prefix / "mine").write_text("keep me")
        with self.assertRaises(ValueError):
            install.install(self.prefix, self.home)
        self.assertEqual((self.prefix / "mine").read_text(), "keep me")
        self.rc.write_text(install.START + "\n")
        with self.assertRaises(ValueError):
            install.install(self.home / "new", self.home)
        self.assertFalse((self.home / "new").exists())


class ShellTests(unittest.TestCase):
    def test_iterm_escape_sequence_and_off_mode(self):
        script = r'''
source "$PLUGIN"
_oh_my_usage_emit Q2xhdWRlIDQyJQ==
OH_MY_USAGE_DISPLAY=off
_oh_my_usage_precmd
TMUX=fake
_oh_my_usage_emit U0hPVUxELU5PVC1TSF9PVw==
'''
        master, slave = pty.openpty()
        try:
            env = dict(os.environ, PLUGIN=str(ROOT / "oh-my-usage.plugin.zsh"),
                       TERM_PROGRAM="iTerm.app", TMUX="", STY="")
            result = subprocess.run(["zsh", "-dfi", "-c", script], env=env,
                                    stdout=slave, stderr=subprocess.PIPE, timeout=5)
            output = b""
            # macOS can discard unread PTY bytes when the final slave FD closes.
            while select.select([master], [], [], 0.1)[0]:
                output += os.read(master, 8192)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output, b"\x1b]1337;SetUserVar=oh_my_usage=Q2xhdWRlIDQyJQ==\x07"
                             b"\x1b]1337;SetUserVar=oh_my_usage=\x07")
        finally:
            os.close(master)
            if slave is not None:
                os.close(slave)

    def test_full_installs_app_and_existing_reuses_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            appdir = root / "Applications"
            binaries = root / "bin"
            binaries.mkdir()
            log = root / "calls"
            stubs = {
                "uname": '#!/bin/sh\necho Darwin\n',
                "sw_vers": '#!/bin/sh\necho 15.0\n',
                "brew": '#!/bin/zsh\nprint -r -- "$*" >> "$CALLS"\nmkdir -p "$OH_MY_USAGE_APP_DIR/OpenUsage.app"\n',
                "open": '#!/bin/zsh\nprint -r -- "open $*" >> "$CALLS"\n',
            }
            for name, content in stubs.items():
                (binaries / name).write_text(content)
                (binaries / name).chmod(0o755)
            env = dict(os.environ, OH_MY_USAGE_APP_DIR=str(appdir), OH_MY_USAGE_PYTHON=sys.executable,
                       OH_MY_USAGE_CACHE_DIR=str(root / "cache"),
                       OH_MY_USAGE_CONFIG_DIR=str(root / "config"),
                       ZDOTDIR=str(root), CALLS=str(log), PATH=str(binaries) + ":" + os.environ["PATH"])
            prefix = root / "install"
            args = ["--no-shell", "--no-profile", "--prefix", str(prefix)]
            # Missing-app existing mode must not invoke brew or create files.
            missing = subprocess.run([str(ROOT / "install-existing.sh"), *args], env=env,
                                     capture_output=True, text=True)
            self.assertNotEqual(missing.returncode, 0)
            self.assertFalse(log.exists())
            for script in ("install-full.sh", "install-full.sh", "install-existing.sh"):
                result = subprocess.run([str(ROOT / script), *args], env=env,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            calls = log.read_text()
            self.assertEqual(calls.count("install --cask"), 1)
            self.assertEqual(calls.count("open "), 3)
            self.assertTrue((prefix / "oh-my-usage.plugin.zsh").exists())
            self.assertTrue((prefix / "zsh/inline.zsh").exists())

    def run_pty(self, script, root, **extra):
        master, slave = pty.openpty()
        env = dict(os.environ, PLUGIN=str(ROOT / "oh-my-usage.plugin.zsh"),
                   OH_MY_USAGE_CACHE_DIR=str(root), OH_MY_USAGE_CONFIG_DIR=str(root / "config"), OH_MY_USAGE_SOURCE="openusage", TERM_PROGRAM="iTerm.app", TMUX="", STY="")
        env.update(extra)
        try:
            result = subprocess.run(["zsh", "-dfi", "-c", script], env=env, cwd=root,
                                    stdout=slave, stderr=subprocess.PIPE, timeout=10)
            output = b""
            while select.select([master], [], [], 0.1)[0]:
                output += os.read(master, 8192)
            self.assertEqual(result.returncode, 0, output + result.stderr)
            return output
        finally:
            os.close(master)
            os.close(slave)

    def test_status_only_hot_path_and_legacy_display_option(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "display").write_text(
                str(int(time.time())) + "\n" + 'Codex 42% $(touch INJECTED) `touch INJECTED2` %F{red}' + "\nQQ==\n")
            script = r'''
setopt promptsubst
RPROMPT='theme'
PROMPT='left theme'
OH_MY_USAGE_DISPLAY=prompt
source "$PLUGIN"
oh-my-usage() { print worker >> "$OH_MY_USAGE_CACHE_DIR/worker"; }
for i in {1..100}; do _oh_my_usage_precmd; done
[[ $OH_MY_USAGE_TEXT == 'Codex 42%'* ]] || exit 2
[[ $RPROMPT == theme && $PROMPT == 'left theme' ]] || exit 3
[[ ! -e INJECTED && ! -e INJECTED2 ]] || exit 4
[[ ! -e "$OH_MY_USAGE_CACHE_DIR/worker" ]] || exit 5
source "$PLUGIN"
[[ ${#${(M)precmd_functions:#_oh_my_usage_precmd}} == 1 ]] || exit 6
oh-my-usage-unload
[[ $RPROMPT == theme ]] || exit 7
[[ ${#${(M)precmd_functions:#_oh_my_usage_precmd}} == 0 ]] || exit 8
'''
            output = self.run_pty(script, root)
            self.assertEqual(output, b"\x1b]1337;SetUserVar=oh_my_usage=QQ==\x07"
                             + b"\x1b]1337;SetUserVar=oh_my_usage=\x07")

    def test_cold_read_publishes_without_second_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = r'''
source "$PLUGIN"
oh-my-usage() {
  print -rl -- "$EPOCHSECONDS" 'Claude 42%' Q2xhdWRlIDQyJQ== > "$OH_MY_USAGE_CACHE_DIR/display"
  print -r -- 'This CLI output must be suppressed'
}
_oh_my_usage_precmd
zmodload zsh/zselect
repeat 40; do
  [[ -r "$OH_MY_USAGE_CACHE_DIR/display" ]] && break
  zselect -t 5
done
zselect -t 5
[[ -r "$OH_MY_USAGE_CACHE_DIR/display" ]]
'''
            self.assertEqual(self.run_pty(script, root),
                             b"\x1b]1337;SetUserVar=oh_my_usage=Q2xhdWRlIDQyJQ==\x07")

    def test_start_publishes_immediately_and_reenables_this_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bin").mkdir()
            executable = root / "bin/oh-my-usage"
            executable.write_text('#!/bin/zsh\n[[ $1 == start ]] || exit 2\n'
                                  'print -rl -- "$EPOCHSECONDS" "Ready" UmVhZHk= > "$OH_MY_USAGE_CACHE_DIR/display"\n')
            executable.chmod(0o755)
            script = r'''
OH_MY_USAGE_DISPLAY=off
source "$PLUGIN"
_OH_MY_USAGE_ROOT=$OH_MY_USAGE_CACHE_DIR
oh-my-usage start
[[ $OH_MY_USAGE_DISPLAY == status && $OH_MY_USAGE_TEXT == Ready ]]
'''
            self.assertEqual(self.run_pty(script, root),
                             b"\x1b]1337;SetUserVar=oh_my_usage=UmVhZHk=\x07")

    def test_no_refresh_or_status_output_in_other_terminals_with_inline_off(self):
        script = r'''
source "$PLUGIN"
_oh_my_usage_refresh() { print worker > "$OH_MY_USAGE_CACHE_DIR/worker"; }
_oh_my_usage_precmd
_oh_my_usage_emit QQ==
[[ ${_OH_MY_USAGE_INLINE_ACTIVE:-0} == 0 ]]
'''
        with tempfile.TemporaryDirectory() as temp:
            for env in ({"TERM_PROGRAM": "Apple_Terminal"}, {"TMUX": "fake"}, {"STY": "fake"}):
                self.assertEqual(self.run_pty(script, Path(temp), **env), b"")
            self.assertFalse((Path(temp) / "worker").exists())

    def test_ssh_can_fetch_missing_cache_without_iterm_transport(self):
        script = r'''
source "$PLUGIN"
oh-my-usage() {
  print -rl -- "$EPOCHSECONDS" 'Codex 42%' Q29kZXggNDIl > "$OH_MY_USAGE_CACHE_DIR/display"
}
_oh_my_usage_precmd
zmodload zsh/zselect
repeat 40; do
  [[ -r "$OH_MY_USAGE_CACHE_DIR/display" ]] && break
  zselect -t 5
done
[[ -r "$OH_MY_USAGE_CACHE_DIR/display" ]] || exit 3
_oh_my_usage_precmd
[[ $OH_MY_USAGE_TEXT == 'Codex 42%' ]]
'''
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(self.run_pty(script, Path(temp), TERM_PROGRAM="", OH_MY_USAGE_INLINE="on"), b"")

    def test_upgrading_loaded_legacy_plugin_restores_theme(self):
        script = r'''
_OH_MY_USAGE_LOADED=1
RPROMPT='old usage + theme'
oh-my-usage-unload() { RPROMPT=theme; unset _OH_MY_USAGE_LOADED; }
source "$PLUGIN"
[[ $RPROMPT == theme && $_OH_MY_USAGE_VERSION == 0.7.0 ]]
'''
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(self.run_pty(script, Path(temp)), b"")


if __name__ == "__main__":
    unittest.main()
