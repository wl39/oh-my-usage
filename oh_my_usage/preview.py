"""Read-only settings preview; never fetch usage or change the user's prompt."""

from datetime import datetime, timezone
import json
import os
import time
import unicodedata

from . import cache, config, customize, settings, source


def snapshot():
    now = time.time()
    try:
        marker = cache.directory() / "usage-source"
        origin_source = marker.read_text().strip() if marker.exists() else "openusage"
        if origin_source != config.source():
            raise ValueError("cached source changed")
        providers = source.validate(json.loads((cache.directory() / "usage.json").read_text(encoding="utf-8")))
        prefs = settings.direct(providers) if config.source() == "direct" else settings.load()
        origin = "cached usage"
        offline = cache.display(cache.directory())[1].endswith(" [offline]")
    except (OSError, ValueError):
        # A first-run preview must work before OpenUsage or its API is available.
        providers = [{"providerId": provider, "displayName": provider.title(),
                      "fetchedAt": datetime.fromtimestamp(now, timezone.utc).isoformat(),
                      "lines": [{"type": "progress", "label": label, "used": amount,
                                 "limit": 100, "format": {"kind": "percent"}}
                                for label, amount in (("Session", used), ("Weekly", used // 2))]}
                     for provider, used in (("claude", 28), ("codex", 42))]
        prefs = settings.Settings(("claude.session", "codex.session"), ("claude", "codex"),
                                  ("claude", "codex"), {}, ())
        origin, offline = "sample data", False
    return providers, prefs, now, offline, origin


def content():
    providers, prefs, now, offline, origin = snapshot()
    return customize.render_inline(providers, config.apply(prefs), now, offline), origin


def cells(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
               for c in text)


def truncate(text, width):
    if cells(text) <= width:
        return text
    result = ""
    for char in text:
        if cells(result + char) > width - 1:
            break
        result += char
    return result + "…"


def show(console):
    text, origin = content()
    width = console.width - 6
    position = config.value("position")
    above = console.width < 80 or position == "above"
    indent = int(config.value("indent")) if above or position == "left" else 0
    gap = " " * int(config.value("gap"))
    limit = console.width - 2 - indent if above else console.width // 2 - indent
    custom = config.value("width")
    if custom == "auto":
        custom = os.environ.get("OH_MY_USAGE_INLINE_WIDTH", "")
    if custom.isascii() and custom.isdigit() and len(custom) <= 4:
        limit = max(1, min(limit, int(custom)))
    indent = min(indent, width - 1)
    hint = truncate(text, max(1, min(width - indent, limit)))
    color = "38;5;" + config.color()
    prompt = "~/project > "
    placement = "above input" if above else "after prompt" if position == "after" else "left" if position == "left" else "right"
    console.section("PREVIEW · " + origin + " · " + placement)
    border = "  +" + "-" * (width + 2) + "+"
    console.line(border, "2")

    def row(before="", usage="", after=""):
        padding = " " * max(0, width - cells(before + usage + after))
        console.line("  | " + before + console.paint(usage, color) + after + padding + " |")

    if not text:
        row(before=prompt)
    elif above:
        row(before=" " * indent, usage=hint)
        row(before=prompt)
    elif position == "left":
        row(before=" " * indent, usage=hint, after=gap + prompt)
    elif position == "after":
        row(before=prompt + gap, usage=hint, after=gap)
    else:
        row(before=prompt + " " * max(1, width - cells(prompt + hint)), usage=hint)
    console.line(border, "2")
    if not text:
        console.note("All selected providers or metrics are hidden; no inline hint will appear.", "2")
    if config.inline()[0] == "off":
        console.note("Preview only: inline display is off. Enable option 1 or use preset 9.", "2")
    console.note("Example prompt; your shell theme is preserved. Usage hides while typing.", "2")
    if config.value("style") == "icons":
        legend = "CL = Claude; CX = Codex" if config.value("icons") == "ascii" else "✳ = Claude; ◇ = Codex"
        if customize.mapping("icon"):
            console.note("Custom icons: " + ", ".join(f"{key} = {value}" for key, value in customize.mapping("icon").items()), "2")
        else:
            console.note(legend + ". S = Session; W = Weekly.", "2")
        console.note("Symbols are text, not brand logos. If glyphs look wrong, choose ASCII in option 8.", "2")
