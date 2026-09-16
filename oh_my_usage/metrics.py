"""Small compatibility table: OpenUsage descriptor IDs to public UI row labels."""

import math
import re

# Only names that cannot be inferred from the descriptor's camelCase suffix.
LABELS = {
    "antigravity.geminiPro": ("Session",),
    "antigravity.geminiWeekly": ("Weekly",),
    "antigravity.claude": ("Claude",),
    "claude.extra": ("Extra usage spent", "Extra Usage"),
    "cursor.usage": ("Total Usage",),
    "cursor.auto": ("Cursor Models", "Auto Usage"),
    "cursor.api": ("Other Models", "API Usage"),
    "cursor.grokBot": ("Grok Bot usage",),
    "cursor.onDemand": ("On-demand",),
    "copilot.premium": ("Credits", "Premium Requests"),
    "copilot.extra": ("Extra Usage",),
    "devin.daily": ("Daily quota",),
    "devin.weekly": ("Weekly quota",),
    "devin.extra": ("Extra usage balance",),
    "openrouter.week": ("This Week",),
    "openrouter.month": ("This Month",),
}
PERIODS = {"today": "Today", "yesterday": "Yesterday", "last30": "Last 30 Days"}


def clean(value, limit=100):
    """Never let API labels inject terminal controls, newlines, or bidi controls."""
    return "".join(c for c in str(value) if c.isprintable())[:limit]


def row_for(descriptor, provider):
    suffix = descriptor[len(provider["providerId"]) + 1:]
    family = re.split(r"[.:]", provider["providerId"], maxsplit=1)[0]
    labels = LABELS.get(family + "." + suffix)
    if labels is None:
        labels = (PERIODS.get(suffix, re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", suffix)),)
    for row in provider["lines"]:
        if str(row.get("label", "")).lower() in (label.lower() for label in labels):
            return row
    return None


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def compact(value, dollars=False):
    prefix = "$" if dollars else ""
    for size, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= size:
            return prefix + f"{value / size:.1f}".rstrip("0").rstrip(".") + suffix
    return prefix + (f"{value:.2f}" if dollars else f"{value:.1f}".rstrip("0").rstrip("."))


def reading(row, remaining):
    """Return text + optional bounded fraction. Missing data never becomes zero."""
    kind = row.get("type")
    if kind == "progress":
        used, limit = row.get("used"), row.get("limit")
        if not number(used) or not number(limit) or limit <= 0:
            return None
        value = max(0, limit - used) if remaining else used
        fraction = min(1, max(0, value / limit))
        fmt = row.get("format")
        if not isinstance(fmt, dict):
            return None
        unit = fmt.get("kind")
        if unit == "percent":
            return str(math.floor(fraction * 100 + 0.5)) + "%", fraction
        if unit in ("dollars", "count"):
            return compact(value, unit == "dollars"), fraction
        return None
    if kind in ("text", "badge"):
        text = row.get("value" if kind == "text" else "text")
        if not isinstance(text, str) or row.get("label") in ("Error", "Status"):
            return None
        # The API fuses numeric values with ' · '. The tray uses the first value.
        text = clean(text.split(" · ", 1)[0])
        return (text, None) if text else None
    return None
