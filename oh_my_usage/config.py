"""One saved inline preference; read as data, never as shell code."""

import os
from pathlib import Path

from .files import atomic_write


def directory():
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return Path(os.environ.get("OH_MY_USAGE_CONFIG_DIR") or base / "oh-my-usage").expanduser()


def inline():
    try:
        with (directory() / "inline").open(encoding="utf-8") as stream:
            saved = stream.readline().rstrip("\n")
        if saved in ("on", "off"):
            return saved, "saved"
    except (OSError, UnicodeError):
        pass
    value = os.environ.get("OH_MY_USAGE_INLINE")
    return (value, "environment") if value in ("on", "off") else ("off", "default")


def save_inline(value):
    if value not in ("on", "off"):
        raise ValueError("inline must be on or off")
    root = directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    atomic_write(root / "inline", value + "\n")
