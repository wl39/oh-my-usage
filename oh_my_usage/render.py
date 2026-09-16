"""Pure text rendering, independent of HTTP, preferences, and shell integration."""

from datetime import datetime

from .metrics import clean, reading, row_for

STALE_SECONDS = 600


def outdated(timestamp, now):
    try:
        instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
        return now - instant > STALE_SECONDS or instant - now > 60
    except (ValueError, TypeError, AttributeError):
        return True


def render(providers, settings, now, offline=False):
    by_id = {p["providerId"]: p for p in providers}
    order = list(dict.fromkeys((*settings.providers, *by_id)))
    groups = []
    bar_count = 0
    for provider_id in order:
        if provider_id not in settings.enabled or provider_id not in by_id:
            continue
        provider = by_id[provider_id]
        values = []
        for descriptor in settings.ordered_pins(provider_id):
            row = row_for(descriptor, provider)
            value = reading(row, settings.remaining) if row else None
            if value is None:
                continue
            text, fraction = value
            if settings.bars:
                if fraction is None or bar_count >= 4:
                    continue
                filled = int(fraction * 5 + 0.5)
                text = "[" + "#" * filled + "-" * (5 - filled) + "] " + text
                bar_count += 1
            values.append(clean(row["label"]) + " " + text)
        if values:
            stale = "~" if outdated(provider["fetchedAt"], now) else ""
            groups.append(clean(provider["displayName"]) + stale + " " + "/".join(values))
    if not groups:
        return "OpenUsage: no pinned data" + (" [offline]" if offline else "")
    mode = "left" if settings.remaining else "used"
    return " | ".join(groups) + " (" + mode + ")" + (" [offline]" if offline else "")
