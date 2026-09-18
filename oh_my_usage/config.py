"""Small account-wide preferences; read as data, never as shell code."""

import os
import re
from dataclasses import replace
from pathlib import Path

from .files import atomic_write

COLORS = {"gray": 245, "cyan": 109, "green": 108, "blue": 110,
          "purple": 139, "yellow": 180, "red": 174, "white": 250}
DEFAULTS = {"position": "auto", "style": "text", "icons": "unicode",
            "gap": "1", "indent": "0", "width": "auto", "metric-labels": "auto",
            "mode-label": "on", "separator": "pipe"}
MAP_DEFAULTS = {"icon-map": "{}", "providers": "{}", "metrics": "{}"}
RENDER_DEFAULTS = {"metric-labels": "auto", "mode-label": "on", "separator": "pipe", **MAP_DEFAULTS}


def read(name, default="auto"):
    try:
        with (directory() / name).open(encoding="utf-8") as stream:
            return stream.readline().rstrip("\n")
    except (OSError, UnicodeError):
        return default


def validate(name, value):
    value = value.strip().lower()
    choices = {"position": ("auto", "left", "right", "after", "above"),
               "source": ("direct", "openusage"),
               "style": ("text", "icons"), "icons": ("unicode", "ascii"),
               "metric-labels": ("auto", "on", "off"), "mode-label": ("on", "off"),
               "separator": ("pipe", "dot", "space")}
    if name in choices:
        if value == "auto":
            return DEFAULTS.get(name, "direct")
        if value in choices[name]:
            return value
        raise ValueError(name + ": " + ", ".join(choices[name]))
    if name in ("gap", "indent", "width"):
        if value == "auto":
            return DEFAULTS[name]
        low, high = {"gap": (0, 8), "indent": (0, 20), "width": (1, 240)}[name]
        if value.isascii() and value.isdigit() and low <= int(value) <= high:
            return str(int(value))
        raise ValueError(f"{name}: {low}–{high}, or auto")
    if name == "mode" and value in ("auto", "used", "left"):
        return value
    if name == "order":
        if value == "auto":
            return value
        ids = [part.strip() for part in value.split(",")]
        if (all(re.fullmatch(r"[a-z][a-z0-9_.:-]*", part) for part in ids)
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
    if name == "source":
        return source()
    try:
        return validate(name, read(name, DEFAULTS.get(name, "auto")))
    except ValueError:
        return DEFAULTS.get(name, "auto")


def save(name, setting):
    setting = validate(name, setting)
    root = directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    atomic_write(root / name, setting + "\n")


def reset():
    for name in ("mode", "order", "color", *DEFAULTS, *MAP_DEFAULTS):
        (directory() / name).unlink(missing_ok=True)


def view_key():
    # Kept in the display file so every tab notices a changed presentation.
    key = read("mode") + "|" + read("order")
    if source() == "direct":
        key += "|source=direct"
    if value("style") == "icons":
        key += "|icons|" + value("icons")
    for name, default in RENDER_DEFAULTS.items():
        setting = read(name, default)
        if setting != default:
            key += "|" + name + "=" + setting
    return key


def color():
    saved = value("color")
    if saved != "auto":
        return saved
    fallback = os.environ.get("OH_MY_USAGE_INLINE_COLOR", "245")
    if fallback.isascii() and fallback.isdigit() and len(fallback) <= 3 and int(fallback) <= 255:
        return str(int(fallback))
    return "245"


def apply(prefs):
    mode, order = value("mode"), value("order")
    providers = prefs.providers if order == "auto" else tuple(dict.fromkeys(
        (*order.split(","), *prefs.providers)))
    return replace(prefs, remaining=prefs.remaining if mode == "auto" else mode == "left",
                   providers=providers)


def directory():
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return Path(os.environ.get("OH_MY_USAGE_CONFIG_DIR") or base / "oh-my-usage").expanduser()


def source():
    override = os.environ.get("OH_MY_USAGE_SOURCE")
    saved = read("source", "")
    if override in ("direct", "openusage"):
        return override
    if saved in ("direct", "openusage"):
        return saved
    # An explicitly supplied legacy preference file is also an explicit legacy source.
    return "openusage" if os.environ.get("OH_MY_USAGE_PREFERENCES") else "direct"


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
