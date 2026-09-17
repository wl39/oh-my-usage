"""One shared cache and file lock for all terminal tabs."""

import base64
import fcntl
import json
import os
import time
from pathlib import Path

from . import config, settings, source
from .files import atomic_write
from .render import render


def directory():
    return Path(os.environ.get("OH_MY_USAGE_CACHE_DIR",
                str(Path.home() / "Library/Caches/oh-my-usage"))).expanduser()


def display(root):
    try:
        lines = (root / "display").read_text(encoding="utf-8").splitlines()
        return int(lines[0]), lines[1]
    except (OSError, ValueError, IndexError):
        return 0, "OpenUsage: waiting for first read"


def view_key(root):
    try:
        lines = (root / "display").read_text(encoding="utf-8").splitlines()
        return lines[3] if len(lines) > 3 else "auto|auto"
    except (OSError, UnicodeError):
        return "auto|auto"


def refresh(force=False, interval=30, root=None, preferences=None, fetch=source.fetch, now=None):
    root = root or directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Keep this inode: deleting lock files can permit two concurrent lock holders.
    fd = os.open(root / "lock", os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, "w") as lock:
        deadline = time.monotonic() + 10
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                # With no cache yet, let the first reader finish. Otherwise a
                # second new tab would receive EOF before there is text to draw.
                if (root / "display").exists() or time.monotonic() >= deadline:
                    return display(root)[1]
                time.sleep(0.05)
        instant = time.time() if now is None else now
        last, text = display(root)
        fresh = not force and 0 <= instant - last < interval
        key = config.view_key()
        if fresh and key == view_key(root):
            return text
        try:
            prefs = config.apply(settings.load(preferences))
        except settings.SettingsError as error:
            text = "OpenUsage: " + error.summary + "; run oh-my-usage doctor"
        else:
            # A presentation change can reuse a fresh snapshot without an HTTP call.
            offline = fresh and text.endswith(" [offline]")
            try:
                if fresh:
                    providers = source.validate(json.loads((root / "usage.json").read_text()))
                else:
                    providers = fetch()
                    atomic_write(root / "usage.json", json.dumps(providers, ensure_ascii=False))
            except (OSError, ValueError, source.http.client.HTTPException):
                offline = True
                try:
                    providers = source.validate(json.loads((root / "usage.json").read_text()))
                except (OSError, ValueError):
                    providers = []
            text = render(providers, prefs, instant, offline)
        encoded = base64.b64encode(text.encode()).decode("ascii")
        stamp = last if fresh else int(instant)
        atomic_write(root / "display", f"{stamp}\n{text}\n{encoded}\n{key}\n")
        return text
