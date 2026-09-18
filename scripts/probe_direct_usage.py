#!/usr/bin/env python3
"""Opt-in, one-shot feasibility probes; independent of the OpenUsage runtime.

No inference requests, manual token refreshes, credential writes, or raw responses.
Codex app-server manages its own authentication. Only allowlisted usage fields are
emitted. This is not the production backend.
Protocol references and limitations: docs/standalone-feasibility.md.
Claude Desktop decoding/selection adapts the OpenUsage format implementation;
see scripts/third_party/OpenUsage-LICENSE.txt for its MIT notice.
"""

import argparse
import base64
import ctypes
import getpass
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

MAX_BYTES = 2 * 1024 * 1024


class ProbeError(Exception):
    """Only fixed, non-sensitive diagnostic codes may be passed here."""


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def identifier(value):
    if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", value):
        return value
    return None


def timestamp(value):
    try:
        if isinstance(value, str):
            instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if instant.tzinfo is None:
                return None
        elif finite(value):
            instant = datetime.fromtimestamp(value, timezone.utc)
        else:
            return None
        return instant.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def request(host, path, *, headers=None, body=None, port=None):
    # Only the Antigravity loopback server uses its self-signed certificate.
    context = ssl._create_unverified_context() if host == "127.0.0.1" else ssl.create_default_context()
    connection = http.client.HTTPSConnection(host, port=port, timeout=12, context=context)
    try:
        connection.request("POST" if body is not None else "GET", path,
                           json.dumps(body) if body is not None else None, headers or {})
        response = connection.getresponse()
        payload = response.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ProbeError("response_too_large")
        if response.status != 200:
            # Never expose response bodies: they can contain account or token data.
            raise ProbeError("http_" + str(response.status))
        return json.loads(payload)
    finally:
        connection.close()


def keychain(service, account=None):
    if sys.platform != "darwin":
        return None
    command = ["/usr/bin/security", "find-generic-password", "-s", service]
    if account:
        command += ["-a", account]
    try:
        result = subprocess.run(command + ["-w"], capture_output=True, timeout=20)
    except subprocess.TimeoutExpired:
        raise ProbeError("keychain_read_timeout") from None
    if result.returncode:
        return None
    return result.stdout.rstrip(b"\r\n")


def decode_json(raw):
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        return json.loads(bytes.fromhex(raw.decode().strip()))


def codex_metrics(result):
    buckets = result.get("rateLimitsByLimitId")
    if not isinstance(buckets, dict) or not buckets:
        buckets = {"codex": result.get("rateLimits")}
    metrics = []
    for bucket_id, bucket in buckets.items():
        if not identifier(bucket_id) or not isinstance(bucket, dict):
            continue
        for slot in ("primary", "secondary"):
            window = bucket.get(slot)
            if not isinstance(window, dict) or not finite(window.get("usedPercent")):
                continue
            duration = window.get("windowDurationMins")
            # A weekly-only plan can put its weekly window in the primary slot.
            period = {300: "session", 10080: "weekly"}.get(duration, slot)
            used = window["usedPercent"]
            metrics.append({"id": bucket_id + "." + period, "used_percent": used,
                            "remaining_percent": max(0, min(100, 100 - used)),
                            "window_minutes": duration if finite(duration) else None,
                            "resets_at": timestamp(window.get("resetsAt"))})
    return metrics


def probe_codex():
    executable = shutil.which("codex")
    if not executable:
        raise ProbeError("cli_not_installed")
    # No thread/start or turn/start: this only initializes and reads account limits.
    process = subprocess.Popen([executable, "app-server", "--listen", "stdio://"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, cwd=tempfile.gettempdir())
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    pending = bytearray()

    def send(message):
        process.stdin.write(json.dumps(message).encode() + b"\n")
        process.stdin.flush()

    def receive(wanted):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            while b"\n" in pending:
                line, _, rest = pending.partition(b"\n")
                pending[:] = rest
                if not line:
                    continue
                message = json.loads(line)
                if message.get("id") == wanted:
                    if "error" in message:
                        raise ProbeError("app_server_rpc_error")
                    return message.get("result", {})
            if not selector.select(max(0, deadline - time.monotonic())):
                break
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                raise ProbeError("app_server_closed")
            pending.extend(chunk)
            if len(pending) > MAX_BYTES:
                raise ProbeError("response_too_large")
        raise ProbeError("app_server_timeout")

    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {
            "name": "oh_my_usage_probe", "title": "Oh My Usage direct usage probe", "version": "0.1.0"}}})
        receive(1)
        send({"method": "initialized", "params": {}})
        send({"id": 2, "method": "account/rateLimits/read"})
        metrics = codex_metrics(receive(2))
        return {"transport": "codex_app_server", "metrics": metrics}
    finally:
        selector.close()
        process.stdin.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdout.close()


def antigravity_metrics(payload):
    root = payload.get("response", payload)
    metrics = []
    for group in root.get("groups", []):
        for bucket in group.get("buckets", []):
            name, remaining = bucket.get("bucketId"), bucket.get("remainingFraction")
            if not identifier(name) or not finite(remaining) or not 0 <= remaining <= 1:
                continue
            metrics.append({"id": name, "used_percent": round((1 - remaining) * 100, 6),
                            "remaining_percent": round(remaining * 100, 6),
                            "resets_at": timestamp(bucket.get("resetTime"))})
    return metrics


def probe_antigravity():
    processes = subprocess.run(["ps", "-axo", "pid=,args="], capture_output=True, text=True,
                               check=True, timeout=5)
    failures = []
    for line in processes.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        pid, command = parts
        # Do not mistake a shell containing this script for the language-server process.
        expected_app = command.startswith("/Applications/Antigravity.app/Contents/Resources/bin/language_server ")
        expected_ide = (re.match(r"\S*language_server[^\s]*\s", command)
                        and re.search(r"--(?:app_data_dir|override_ide_name)(?:=|\s+)[^\s]*antigravity", command, re.I))
        if not pid.isdigit() or not (expected_app or expected_ide):
            continue
        csrf = re.search(r"--csrf_token(?:=|\s+)(\S+)", command)
        if not csrf:
            continue
        # --https_server_port=0 means the OS selected a port; discover the actual listener.
        sockets = subprocess.run(["lsof", "-nP", "-a", "-p", pid, "-iTCP", "-sTCP:LISTEN", "-Fn"],
                                 capture_output=True, text=True, timeout=5)
        ports = sorted({int(x.rsplit(":", 1)[1]) for x in sockets.stdout.splitlines()
                        if re.fullmatch(r"n127\.0\.0\.1:\d+", x)})
        for port in ports:
            try:
                payload = request("127.0.0.1", "/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary",
                                  port=port, body={"metadata": {"ideName": "antigravity", "extensionName": "antigravity",
                                                               "ideVersion": "unknown", "locale": "en"}},
                                  headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1",
                                           "x-codeium-csrf-token": csrf.group(1)})
                return {"transport": "antigravity_local_rpc", "metrics": antigravity_metrics(payload)}
            except (ProbeError, OSError, ValueError, http.client.HTTPException) as error:
                failures.append(str(error) if isinstance(error, ProbeError) else type(error).__name__)
    raise ProbeError("local_rpc_unavailable" if failures else "running_language_server_not_found")


def desktop_decrypt(encrypted, key):
    if not encrypted.startswith(b"v10"):
        raise ProbeError("desktop_encryption_format_unsupported")
    # Keep the key out of subprocess arguments. CommonCrypto is supplied by macOS.
    library = ctypes.CDLL("/usr/lib/system/libcommonCrypto.dylib")
    crypt = library.CCCrypt
    crypt.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_size_t,
                      ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                      ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    crypt.restype = ctypes.c_int
    payload = encrypted[3:]
    output = ctypes.create_string_buffer(len(payload) + 16)
    length = ctypes.c_size_t()
    result = crypt(1, 0, 1, key, len(key), b" " * 16, payload, len(payload), output, len(output), ctypes.byref(length))
    if result:
        raise ProbeError("desktop_decryption_failed")
    return output.raw[:length.value]


def desktop_token():
    if sys.platform != "darwin":
        raise ProbeError("desktop_probe_macos_only")
    root = Path.home() / "Library/Application Support/Claude"
    config = json.loads((root / "config.json").read_text())
    if not any(isinstance(config.get(k), str) for k in ("oauth:tokenCache", "oauth:tokenCacheV2")):
        raise ProbeError("desktop_login_not_found")
    password = keychain("Claude Safe Storage", "Claude Key")
    if not password:
        raise ProbeError("desktop_keychain_unavailable")
    key = hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, dklen=16)
    organization = None
    # Read only the active-organization marker, not session cookies or browsing data.
    for relative in ("Cookies", "Network/Cookies"):
        path = root / relative
        if not path.exists():
            continue
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            rows = connection.execute("SELECT host_key, value, encrypted_value FROM cookies "
                                      "WHERE name = 'lastActiveOrg' AND host_key IN ('.claude.ai', 'claude.ai') "
                                      "ORDER BY last_update_utc DESC").fetchall()
        finally:
            connection.close()
        for host, plain, encrypted in rows:
            if plain:
                organization = plain.lower()
            else:
                decoded = desktop_decrypt(encrypted, key)
                digest = hashlib.sha256(host.encode()).digest()
                if decoded.startswith(digest):
                    organization = decoded[len(digest):].decode().lower()
            if organization:
                break
        if organization:
            break
    if not organization:
        raise ProbeError("desktop_active_organization_missing")
    active_account = str(config.get("lastKnownAccountUuid", "")).lower()
    entries = {}
    for version in ("oauth:tokenCache", "oauth:tokenCacheV2"):
        if not isinstance(config.get(version), str):
            continue
        cache = json.loads(desktop_decrypt(base64.b64decode(config[version], validate=True), key))
        legacy, scoped = {}, {}
        for name, entry in cache.items():
            if name.startswith("acct:"):
                owner, separator, name = name[5:].partition("|")
                if separator and owner.lower() == active_account:
                    scoped[name] = entry
            else:
                legacy[name] = entry
        # Scoped entries and V2 deletion markers suppress obsolete fallback entries.
        legacy.update(scoped)
        entries.update(legacy)
    candidates = []
    for name, entry in entries.items():
        prefix, marker, scope_text = name.partition(":https://api.anthropic.com:")
        client, separator, org = prefix.partition(":")
        scopes = scope_text.split()
        if not marker or not separator or org.lower() != organization or "user:profile" not in scopes:
            continue
        if not isinstance(entry, dict) or not isinstance(entry.get("token"), str):
            continue
        expires = entry.get("expiresAt")
        if not finite(expires) or expires <= time.time() * 1000 + 120000:
            continue
        full = "user:inference" in scopes
        rank = (client == "9d1c250a-e61b-44d9-88ed-5944d1962f5e" and full, full, len(scopes), expires)
        candidates.append((rank, entry["token"]))
    if not candidates:
        raise ProbeError("desktop_login_expired_or_missing")
    return max(candidates, key=lambda item: item[0])[1]


def claude_metrics(payload):
    metrics = []
    for name, value in payload.items():
        if not identifier(name) or not isinstance(value, dict):
            continue
        # Extra usage has a different unit; never call it a subscription percentage.
        if name == "extra_usage":
            metrics.append({"id": name, **{k: value[k] for k in ("is_enabled", "monthly_limit", "used_credits")
                                           if k in value and (finite(value[k]) or isinstance(value[k], bool))}})
            continue
        if not finite(value.get("utilization")):
            continue
        used = value["utilization"]
        metrics.append({"id": name, "used_percent": used,
                        "remaining_percent": max(0, min(100, 100 - used)),
                        "resets_at": timestamp(value.get("resets_at"))})
    return metrics


def probe_claude(use_desktop=False):
    observations, candidates = [], []
    custom = os.environ.get("CLAUDE_CONFIG_DIR")
    if sys.platform == "darwin" and not custom:
        raw = keychain("Claude Code-credentials", getpass.getuser())
        if raw:
            candidates.append(("claude_code_keychain", decode_json(raw)))
    path = Path(custom).expanduser() if custom else Path.home() / ".claude"
    if (path / ".credentials.json").exists():
        candidates.append(("claude_code_file", json.loads((path / ".credentials.json").read_text())))
    tokens = []
    for source, data in candidates:
        auth = data.get("claudeAiOauth", {})
        expires = auth.get("expiresAt")
        expired = finite(expires) and expires < time.time() * 1000
        observations.append({"source": source, "expired": expired,
                             "refresh_token_present": bool(auth.get("refreshToken"))})
        scopes = auth.get("scopes")
        if expired or (isinstance(scopes, list) and scopes and "user:profile" not in scopes):
            continue
        if isinstance(auth.get("accessToken"), str) and auth["accessToken"]:
            tokens.append((source, auth["accessToken"]))
    if use_desktop and not tokens:
        try:
            tokens.append(("claude_desktop_read_only", desktop_token()))
        except ProbeError as error:
            observations.append({"source": "claude_desktop", "status": str(error)})
    if not tokens:
        return {"status": "authentication_required", "observations": observations, "metrics": []}
    last_error = None
    for source, token in tokens:
        try:
            payload = request("api.anthropic.com", "/api/oauth/usage", headers={
                "Authorization": "Bearer " + token, "Accept": "application/json",
                "anthropic-beta": "oauth-2025-04-20", "User-Agent": "oh-my-usage-probe/0.1.0"})
            return {"transport": "anthropic_oauth_usage", "credential_source": source,
                    "observations": observations, "metrics": claude_metrics(payload)}
        except ProbeError as error:
            last_error = str(error)
            if last_error not in ("http_401", "http_403"):
                break
    return {"status": last_error, "observations": observations, "metrics": []}


def run_probe(name, probe):
    started = time.monotonic()
    try:
        result = probe()
        result.setdefault("status", "ok" if result.get("metrics") else "no_metrics")
    except ProbeError as error:
        result = {"status": str(error), "metrics": []}
    except Exception as error:
        # Exception messages can embed raw subprocess output, URLs, or response data.
        result = {"status": "probe_error", "error_type": type(error).__name__, "metrics": []}
    return {"provider": name, "checked_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.monotonic() - started, 3), **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("codex", "claude", "antigravity"), action="append")
    parser.add_argument("--claude-desktop", action="store_true", help="Allow a read-only macOS Claude Desktop login fallback")
    parser.add_argument("--output", type=Path, help="Also write sanitized results to a private JSON file")
    args = parser.parse_args()
    probes = {"codex": probe_codex, "claude": lambda: probe_claude(args.claude_desktop),
              "antigravity": probe_antigravity}
    results = [run_probe(name, probes[name]) for name in dict.fromkeys(args.provider or probes)]
    report = {"schema_version": 1, "openusage_runtime_used": False, "results": results}
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary = tempfile.mkstemp(prefix=".usage-probe-", dir=args.output.parent)
        try:
            with os.fdopen(descriptor, "w") as stream:
                stream.write(encoded)
            os.replace(temporary, args.output)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print(encoded, end="")
    return 0 if all(item["status"] == "ok" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
