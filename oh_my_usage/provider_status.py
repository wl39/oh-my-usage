"""Safe service status and explicit API-key setup."""

import getpass
import json
import sys

from . import cache, config
from .files import atomic_write
from .providers import adapters, collector, native

HINTS = {
    "not_installed": "Install the service's client and sign in.",
    "ready": "Detected; run oh-my-usage refresh to fetch usage.",
    "api_key_required": "Set its API-key environment variable or use oh-my-usage connect ID.",
    "authentication_required": "Sign in again with the service's client.",
    "login_expired": "Open the client / CLI and sign in again; it owns token refresh.",
    "keychain_access_required": "The native keychain denied background access; sign in with the CLI or check Keychain Access.",
    "keychain_read_timeout": "The keychain did not respond within 5 seconds. Check the client login and Keychain Access, then retry.",
    "start_client_or_sign_in": "Start Antigravity and sign in.",
    "cli_required": "Install the Codex CLI and sign in.",
    "cryptography_required": "Install requirements.txt in the Python environment used by oh-my-usage.",
    "rate_limited": "Waiting for the service's retry window; refresh respects Retry-After.",
    "access_denied": "Check subscription and usage-read permission in the service.",
    "usage_scope_required": "Sign in using a client token with usage/profile permission.",
    "subscription_required": "Use a subscription login; API-key spending has different limits.",
    "no_usage_data": "No supported usage fields returned (not treated as zero).",
    "credentials_unreadable": "Check the native credentials file format and permissions.",
}


def show(refresh=False, as_json=False):
    root = cache.directory()
    if refresh:
        if config.source() != "direct":
            raise ValueError("Select config source direct before refreshing direct providers")
        cache.refresh(force=True)
    states = collector.statuses(root)
    # Opening a menu discovers local credentials but never makes a remote usage call.
    if not refresh:
        detections = collector.discover()
        saved = collector.load(root)
        for state in states:
            id = state["providerId"]
            detection = detections[id]
            same = detection.credential and detection.credential.fingerprint == saved.get(id, {}).get("binding")
            if not same or not state["status"]:
                state.update(detection.public())
    if as_json:
        print(json.dumps(states, ensure_ascii=False, indent=2))
        return
    print("Services · source: " + config.source())
    for state in states:
        status = state["status"] or "not_checked"
        print(f"  {state['providerId']:12} {status}" + (" · " + state["credentialSource"] if state.get("credentialSource") else ""))
        if status != "ok":
            print("    " + HINTS.get(status, "Run refresh to retry; doctor shows current service status."))
    print("Automatic discovery: each active prompt refresh. API polling: 5 minutes per service.")
    print("History: successful snapshots for 30 days; oh-my-usage history --provider ID")


def connect(provider):
    if not sys.stdin.isatty():
        raise ValueError("connect requires an interactive terminal (hidden key input); environment variables also work")
    key = getpass.getpass(adapters.PROVIDERS[provider] + " API key: ").strip()
    if not key or any(c.isspace() for c in key):
        raise ValueError("Enter a nonempty API key without whitespace")
    root = config.directory()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = native.read_json(root / "credentials.json")
    data[provider] = key
    atomic_write(root / "credentials.json", json.dumps(data))
    print(provider + ": saved privately; the next refresh will connect automatically.")
