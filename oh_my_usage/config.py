"""Small account-wide preferences; read as data, never as shell code."""

import os
import re
from dataclasses import replace
from pathlib import Path

from .files import atomic_write

COLORS = {"gray": 245, "cyan": 109, "green": 108, "blue": 110,
          "purple": 139, "yellow": 180, "red": 174, "white": 250}


def read(name, default="auto"):
    try:
        with (directory() / name).open(encoding="utf-8") as stream:
            return stream.readline().rstrip("\n")
    except (OSError, UnicodeError):
        return default


def validate(name, value):
    value = value.strip().lower()
    if name == "mode" and value in ("auto", "used", "left"):
        return value
    if name == "order":
        if value == "auto":
            return value
        ids = [part.strip() for part in value.split(",")]
        if (all(re.fullmatch(r"[a-z][a-z0-9_-]*", part) for part in ids)
                and len(ids) == len(set(ids))):
            return ",".join(ids)
    if name == "color":
        if value == "auto":
            return value
        if value in COLORS:
            return str(COLORS[value])
        if value.isascii() and value.isdigit() and 0 <= int(value) <= 255:
            return str(int(value))
    raise ValueError({"mode": "mode: used, left, or auto",
                      "order": "order: comma-separated provider IDs, e.g. claude,codex, or auto",
                      "color": "color: gray, cyan, green, blue, purple, yellow, red, white, 0–255, or auto"
                      }.get(name, "Unknown setting: " + name))


def value(name):
    try:
        return validate(name, read(name))
    except ValueError:
        return "auto"


def save(name, setting):
    setting = validate(name, setting)
    root = directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    atomic_write(root / name, setting + "\n")


def reset():
    for name in ("mode", "order", "color"):
        (directory() / name).unlink(missing_ok=True)


def view_key():
    # Kept in the display file so every tab notices a changed presentation.
    return read("mode") + "|" + read("order")


def apply(prefs):
    mode, order = value("mode"), value("order")
    providers = prefs.providers if order == "auto" else tuple(dict.fromkeys(
        (*order.split(","), *prefs.providers)))
    return replace(prefs, remaining=prefs.remaining if mode == "auto" else mode == "left",
                   providers=providers)


def directory():
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return Path(os.environ.get("OH_MY_USAGE_CONFIG_DIR") or base / "oh-my-usage").expanduser()


def inline():
    saved = read("inline")
    if saved in ("on", "off"):
        return saved, "saved"
    value = os.environ.get("OH_MY_USAGE_INLINE")
    return (value, "environment") if value in ("on", "off") else ("off", "default")


def save_inline(value):
    if value not in ("on", "off"):
        raise ValueError("inline must be on or off")
    root = directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    atomic_write(root / "inline", value + "\n")
