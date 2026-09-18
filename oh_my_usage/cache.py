"""One shared cache and file lock for all terminal tabs."""

import base64
import fcntl
import json
import os
import time
from pathlib import Path

from . import config, customize, settings, source
from .files import atomic_write
from .render import render
from .paths import cache_directory


def directory():
    return cache_directory()


def display(root):
    try:
        lines = (root / "display").read_text(encoding="utf-8").splitlines()
        return int(lines[0]), lines[1]
    except (OSError, ValueError, IndexError):
        return 0, "Oh My Usage: waiting for first read"


def view_key(root):
    try:
        lines = (root / "display").read_text(encoding="utf-8").splitlines()
        return lines[3] if len(lines) > 3 else "auto|auto"
    except (OSError, UnicodeError):
        return "auto|auto"


def refresh(force=False, interval=30, root=None, preferences=None, fetch=None, now=None, offline=False):
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
        direct = fetch is None and preferences is None and config.source() == "direct"
        backend = "direct" if direct else "openusage"
        try:
            previous_backend = (root / "usage-source").read_text().strip()
        except OSError:
            previous_backend = "openusage"
        if previous_backend != backend:
            fresh = False
        if fresh and key == view_key(root):
            return text
        try:
            prefs = None if direct else config.apply(settings.load(preferences))
        except settings.SettingsError as error:
            text = "OpenUsage: " + error.summary + "; run oh-my-usage doctor"
            inline_text = text
        else:
            # A presentation change can reuse a fresh snapshot without an HTTP call.
            reuse = fresh or offline
            failed = fresh and text.endswith(" [offline]")
            try:
                if reuse and previous_backend == backend:
                    providers = source.validate(json.loads((root / "usage.json").read_text()))
                elif offline:
                    providers = []
                else:
                    if direct:
                        from .providers.collector import collect
                        providers = collect(root, force=force, now=instant)
                    else:
                        providers = (fetch or source.fetch)()
                    atomic_write(root / "usage.json", json.dumps(providers, ensure_ascii=False))
                    atomic_write(root / "usage-source", backend)
            except (OSError, ValueError, source.http.client.HTTPException):
                failed = True
                try:
                    providers = source.validate(json.loads((root / "usage.json").read_text())) if previous_backend == backend else []
                except (OSError, ValueError):
                    providers = []
            if direct:
                prefs = config.apply(settings.direct(providers))
            text = render(providers, prefs, instant, failed)
            inline_text = customize.render_inline(providers, prefs, instant, failed)
            if direct and not providers:
                text = inline_text = "Oh My Usage: no connected services; run oh-my-usage providers"
        encoded = base64.b64encode(text.encode()).decode("ascii")
        stamp = last if fresh or offline else int(instant)
        atomic_write(root / "display", f"{stamp}\n{text}\n{encoded}\n{key}\n{inline_text}\n")
        return text
