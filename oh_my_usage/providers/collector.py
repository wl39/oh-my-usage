"""Discovery, per-provider backoff and a bounded history of successful snapshots."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time

from ..files import atomic_write
from . import adapters, native
from .common import Detection, ProviderError, iso

TTL = 300
AUTH_ERRORS = {"authentication_required", "access_denied", "login_expired", "subscription_required"}


def load(root):
    try:
        value = json.loads((root / "direct/state.json").read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def discover():
    def one(provider):
        try:
            return native.detect(provider)
        except ProviderError as error:
            return Detection(True, status=error.code)
        except (OSError, ValueError, TypeError, sqlite3.Error):
            return Detection(True, status="credentials_unreadable")
    with ThreadPoolExecutor(max_workers=4) as pool:
        return dict(zip(adapters.PROVIDERS, pool.map(one, adapters.PROVIDERS)))


def collect(root, force=False, now=None, detections=None):
    """Caller holds the shared cache lock. Credentials exist in memory only."""
    root = Path(root)
    instant = time.time() if now is None else now
    previous = load(root)
    detected = discover() if detections is None else detections
    states, jobs = {}, []
    for provider in adapters.PROVIDERS:
        detection = detected.get(provider, Detection())
        state = {**detection.public(), "displayName": adapters.PROVIDERS[provider], "checkedAt": iso(instant)}
        credential = detection.credential
        if credential:
            state["binding"] = credential.fingerprint
            old = previous.get(provider, {})
            same = old.get("binding") == state["binding"]
            # A changed or removed login must never display the previous account's usage.
            if same:
                for key in ("snapshot", "lastSuccess", "nextAttempt", "failures", "status"):
                    if key in old:
                        state[key] = old[key]
            next_attempt = state.get("nextAttempt", 0)
            cooled_down = instant >= next_attempt
            forced = force and (state["status"] != "rate_limited" or cooled_down)
            if not same or cooled_down or forced:
                jobs.append((provider, credential))
        states[provider] = state

    def query(job):
        provider, credential = job
        try:
            return provider, adapters.fetch(provider, credential), None
        except ProviderError as error:
            return provider, None, error
        except Exception:
            # Never interpolate unknown exception messages, which may include a credential.
            return provider, None, ProviderError("invalid_response")

    successes = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for provider, lines, error in pool.map(query, jobs):
            state = states[provider]
            if error:
                failures = min(8, state.get("failures", 0) + 1)
                delay = max(error.retry_after, min(3600, 60 * 2 ** (failures - 1)))
                if error.code in AUTH_ERRORS:
                    delay = max(delay, 900)
                    state.pop("snapshot", None)
                state.update(status=error.code, failures=failures, nextAttempt=instant + delay)
            else:
                snapshot = {"providerId": provider, "displayName": adapters.PROVIDERS[provider],
                            "fetchedAt": iso(instant), "lines": lines}
                state.update(status="ok", failures=0, lastSuccess=iso(instant), nextAttempt=instant + TTL, snapshot=snapshot)
                successes.append((provider, state["binding"], snapshot))
    directory = root / "direct"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write(directory / "state.json", json.dumps(states, ensure_ascii=False))
    record(directory, successes, instant)
    return [{**state["snapshot"], "status": state["status"]} for state in states.values() if "snapshot" in state]


def record(root, snapshots, instant):
    path = root / "history.sqlite3"
    if not path.exists():
        path.touch(mode=0o600)
    with closing(sqlite3.connect(path, timeout=2)) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            provider TEXT NOT NULL, binding TEXT NOT NULL, recorded REAL NOT NULL, metrics TEXT NOT NULL,
            PRIMARY KEY (provider, binding, recorded))""")
        db.executemany("INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?, ?)",
                       [(id, binding, instant, json.dumps(snapshot["lines"], ensure_ascii=False))
                        for id, binding, snapshot in snapshots])
        db.execute("DELETE FROM snapshots WHERE recorded < ?", (instant - 30 * 86400,))
        # Also bound forced manual refreshes: at most 100,000 records, including all providers.
        db.execute("DELETE FROM snapshots WHERE rowid IN (SELECT rowid FROM snapshots ORDER BY recorded DESC LIMIT -1 OFFSET 100000)")


def history(root, provider=None, days=7, now=None):
    path = Path(root) / "direct/history.sqlite3"
    if not path.exists():
        return []
    states = load(Path(root))
    since = (time.time() if now is None else now) - days * 86400
    result = []
    with closing(sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True)) as db:
        for id, binding, stamp, metrics in db.execute(
                "SELECT provider, binding, recorded, metrics FROM snapshots WHERE recorded >= ? ORDER BY recorded", (since,)):
            # By default/history CLI, show only the current credential's records.
            if (provider is None or provider == id) and states.get(id, {}).get("binding") == binding:
                result.append({"providerId": id, "fetchedAt": iso(stamp), "lines": json.loads(metrics)})
    return result


def statuses(root):
    states = load(Path(root))
    return [{"providerId": id, "displayName": name,
             **{key: states.get(id, {}).get(key) for key in ("installed", "status", "credentialSource", "checkedAt", "lastSuccess", "nextAttempt")}}
            for id, name in adapters.PROVIDERS.items()]
