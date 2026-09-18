"""Pure text rendering, independent of HTTP, preferences, and shell integration."""

from datetime import datetime
import math
import re

from .metrics import clean, reading, row_for

STALE_SECONDS = 600
ICONS = {"claude": ("✳", "CL"), "codex": ("◇", "CX"),
         "antigravity": ("△", "AG"), "gemini": ("✦", "GM"),
         "cursor": ("▸", "CU"), "copilot": ("⌘", "CP")}


def provider_icon(provider, icons, custom=None):
    family = re.split(r"[.:]", provider["providerId"], maxsplit=1)[0]
    custom = custom or {}
    if provider["providerId"] in custom:
        return custom[provider["providerId"]]
    if family in custom:
        label = custom[family]
        return (label + " " + clean(provider["displayName"])) if label and family != provider["providerId"] else label
    symbol = ICONS.get(family)
    label = symbol[icons == "ascii"] if symbol else clean(provider["displayName"])
    # Keep account names when OpenUsage exposes multiple accounts of one service.
    if symbol and family != provider["providerId"]:
        label += " " + clean(provider["displayName"])
    return label


def outdated(timestamp, now):
    try:
        instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
        return now - instant > STALE_SECONDS or instant - now > 60
    except (ValueError, TypeError, AttributeError):
        return True


def render(providers, settings, now, offline=False, *, style="text", icons="unicode", custom_icons=None,
           metric_labels="auto", mode_label=True, separator=" | ", metric_limit=2):
    by_id = {p["providerId"]: p for p in providers}
    order = list(dict.fromkeys((*settings.providers, *by_id)))
    groups = []
    bar_count = 0
    for provider_id in order:
        if provider_id not in settings.enabled or provider_id not in by_id:
            continue
        provider = by_id[provider_id]
        values = []
        for descriptor in settings.ordered_pins(provider_id, metric_limit):
            row = row_for(descriptor, provider)
            value = reading(row, settings.remaining) if row else None
            if value is None:
                continue
            text, fraction = value
            if style == "icons":
                if fraction is not None:
                    text = str(math.floor(fraction * 100 + 0.5)) + "%"
            elif settings.bars:
                if fraction is None or (metric_limit is not None and bar_count >= 4):
                    continue
                filled = int(fraction * 5 + 0.5)
                text = "[" + "#" * filled + "-" * (5 - filled) + "] " + text
                bar_count += 1
            label = clean(row["label"])
            if style == "icons":
                label = {"session": "S", "weekly": "W"}.get(label.lower(), label)
                values.append((label, text))
            else:
                values.append((label + " " if metric_labels != "off" else "") + text)
        if values:
            stale = "~" if outdated(provider["fetchedAt"], now) or provider.get("status", "ok") != "ok" else ""
            if style == "icons":
                # Keep periods identifiable when more than one metric is pinned.
                labels = metric_labels == "on" or (metric_labels == "auto" and len(values) > 1)
                texts = [label + ":" + text if labels else text for label, text in values]
                icon = provider_icon(provider, icons, custom_icons) + stale
                groups.append((icon + " " if icon else "") + "/".join(texts))
            else:
                groups.append(clean(provider["displayName"]) + stale + " " + "/".join(values))
    if not groups:
        return "OpenUsage: no pinned data" + (" [offline]" if offline else "")
    mode = "left" if settings.remaining else "used"
    return separator.join(groups) + (" (" + mode + ")" if mode_label else "") + (" [offline]" if offline else "")
