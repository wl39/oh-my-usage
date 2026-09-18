"""Per-provider inline preferences and available metric discovery."""

from dataclasses import replace
import json
import re

from . import config, metrics, settings
from .files import atomic_write
from .render import render

MAPS = {"icon": "icon-map", "provider": "providers", "metric": "metrics"}


def validate(kind, key, value):
    if kind not in MAPS:
        raise ValueError("Choose icon, provider, or metric")
    if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-zA-Z0-9_.:-]{0,119}", key):
        raise ValueError("Use a provider ID or a provider.metric ID")
    if kind == "metric" and "." not in key:
        raise ValueError("Use a metric ID, e.g. codex.weekly")
    if not isinstance(value, str):
        raise ValueError("Setting must be text")
    if kind != "icon":
        if value not in ("on", "off", "auto"):
            raise ValueError("Choose on, off, or auto")
    elif value not in ("auto", "none") and not (1 <= len(value) <= 12 and value.isprintable() and value.strip()):
        raise ValueError("Icon: 1–12 printable characters, none to hide, or auto to reset")
    return value


def mapping(kind):
    try:
        data = json.loads(config.read(MAPS[kind], "{}"))
        if not isinstance(data, dict):
            return {}
        result = {}
        for key, value in data.items():
            try:
                validate(kind, key, value)
            except ValueError:
                continue
            if value != "auto":
                result[key] = value
        return result
    except (ValueError, TypeError):
        return {}


def save(kind, key, value):
    value = validate(kind, key, value)
    data = mapping(kind)
    if value == "auto":
        data.pop(key, None)
    else:
        data[key] = value
    root = config.directory()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    atomic_write(root / MAPS[kind], json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")


def available(provider, pins=()):
    """Reuse known descriptor aliases; infer only IDs that resolve back to the row."""
    provider_id = provider["providerId"]
    family = re.split(r"[.:]", provider_id, maxsplit=1)[0]
    candidates = [p for p in pins if p.startswith(provider_id + ".")]
    candidates += [provider_id + p[len(family):] for p in (*settings.DEFAULT_PINS, *metrics.LABELS)
                   if p.startswith(family + ".")]
    candidates += [provider_id + "." + suffix for suffix in metrics.PERIODS]
    result = []
    for row in provider["lines"]:
        if metrics.reading(row, False) is None:
            continue
        label = metrics.clean(row.get("label", ""))
        words = re.findall(r"[A-Za-z0-9]+", label)
        inferred = words[0].lower() + "".join(w.title() for w in words[1:]) if words else ""
        choices = ([provider_id + "." + row["id"]] if isinstance(row.get("id"), str) else [])
        choices += [*candidates, provider_id + "." + inferred]
        descriptor = next((p for p in choices if metrics.row_for(p, provider) is row), None)
        if descriptor and descriptor not in dict(result):
            result.append((descriptor, label))
    return result


def apply(prefs, providers):
    enabled = list(prefs.enabled)
    for provider, state in mapping("provider").items():
        if state == "on" and provider not in enabled:
            enabled.append(provider)
        elif state == "off" and provider in enabled:
            enabled.remove(provider)
    overrides = mapping("metric")
    pins = list(prefs.pins)
    if overrides:
        ids = dict.fromkeys((*prefs.providers, *prefs.enabled, *(p["providerId"] for p in providers)))
        pins = [pin for provider in ids for pin in prefs.ordered_pins(provider)]
        pins = [pin for pin in pins if overrides.get(pin) != "off"]
        pins += [pin for pin, state in overrides.items() if state == "on" and pin not in pins]
    return replace(prefs, enabled=tuple(enabled), pins=tuple(pins))


def render_inline(providers, prefs, now, offline=False):
    selected = apply(prefs, providers)
    metric_overrides = mapping("metric")
    metric_limit = None if metric_overrides else 2
    # Deliberately hiding everything should remove the hint, not display an error.
    if mapping("provider") or metric_overrides:
        def has_data(selection, limit):
            for provider in providers:
                if provider["providerId"] not in selection.enabled:
                    continue
                for pin in selection.ordered_pins(provider["providerId"], limit):
                    row = metrics.row_for(pin, provider)
                    if row and metrics.reading(row, selection.remaining) is not None:
                        return True
            return False

        has_pins = any(pin.startswith(provider + ".") for provider in selected.enabled for pin in selected.pins)
        if not has_pins or (has_data(prefs, 2) and not has_data(selected, metric_limit)):
            return ""
    custom = {key: "" if value == "none" else value for key, value in mapping("icon").items()}
    return render(providers, selected, now, offline, style=config.value("style"), icons=config.value("icons"),
                  custom_icons=custom, metric_labels=config.value("metric-labels"),
                  mode_label=config.value("mode-label") == "on",
                  separator={"pipe": " | ", "dot": " · ", "space": "  "}[config.value("separator")],
                  metric_limit=metric_limit)
