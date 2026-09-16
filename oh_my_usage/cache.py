"""One shared cache and nonblocking file lock for all terminal tabs."""

import base64
import fcntl
import json
import os
import tempfile
import time
from pathlib import Path

from . import settings, source
from .render import render


def directory():
    return Path(os.environ.get("OH_MY_USAGE_CACHE_DIR",
                str(Path.home() / "Library/Caches/oh-my-usage"))).expanduser()


def atomic_write(path, text):
    fd, name = tempfile.mkstemp(prefix=".oh-my-usage-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def display(root):
    try:
        lines = (root / "display").read_text(encoding="utf-8").splitlines()
        return int(lines[0]), lines[1]
    except (OSError, ValueError, IndexError):
        return 0, "OpenUsage: waiting for first read"


def refresh(force=False, interval=30, root=None, preferences=None, fetch=source.fetch, now=None):
    root = root or directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    instant = time.time() if now is None else now
    # Keep this inode: deleting lock files can permit two concurrent lock holders.
    fd = os.open(root / "lock", os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return display(root)[1]
        last, text = display(root)
        if not force and 0 <= instant - last < interval:
            return text
        try:
            prefs = settings.load(preferences)
        except settings.SettingsError as error:
            text = "OpenUsage: " + error.summary + "; run oh-my-usage doctor"
        else:
            offline = False
            try:
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
        atomic_write(root / "display", f"{int(instant)}\n{text}\n{encoded}\n")
        return text
