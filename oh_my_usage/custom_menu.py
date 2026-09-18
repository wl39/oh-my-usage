"""Interactive editors for inline providers, metrics, icons, and layout."""

from . import config, customize, metrics, preview


def provider_choices():
    providers, prefs, _, _, origin = preview.snapshot()
    by_id = {p["providerId"]: p for p in providers}
    ids = dict.fromkeys((*prefs.providers, *prefs.enabled, *by_id, *customize.mapping("provider"),
                        *customize.mapping("icon")))
    ids.update(dict.fromkeys(key.rsplit(".", 1)[0] for key in customize.mapping("metric")))
    choices = [(f"{metrics.clean(by_id[p]['displayName']) if p in by_id else metrics.clean(p)} ({metrics.clean(p)})", p)
               for p in ids]
    return choices, providers, prefs, origin


def select_provider(console):
    from .menu import choose
    choices, _, _, origin = provider_choices()
    console.note("Available providers: " + origin + ". Saved overrides also appear here.", "2")
    provider = choose(console, "PROVIDER", choices + [("Enter a provider ID", "__custom__")])
    if provider == "__custom__":
        provider = input("  Provider ID (Enter: cancel): ").strip() or None
        if provider:
            customize.validate("provider", provider, "auto")
    return provider


def visibility(console):
    from .menu import change, choose
    provider_id = select_provider(console)
    if provider_id is None:
        return
    while True:
        _, providers, prefs, _ = provider_choices()
        provider = next((p for p in providers if p["providerId"] == provider_id), None)
        rows = customize.available(provider, prefs.pins) if provider else []
        known = dict(rows)
        for descriptor in (*prefs.pins, *customize.mapping("metric")):
            if descriptor.startswith(provider_id + ".") and descriptor not in known:
                rows.append((descriptor, descriptor[len(provider_id) + 1:] + " (no cached data)"))
                known[descriptor] = True
        selected = customize.apply(prefs, providers)
        active = provider_id in selected.enabled
        state = customize.mapping("provider").get(provider_id, "auto")
        choices = [(f"Provider: {'on' if active else 'off'} ({state})", "provider")]
        for descriptor, label in rows:
            state = customize.mapping("metric").get(descriptor, "auto")
            visible = descriptor in selected.ordered_pins(provider_id, None if customize.mapping("metric") else 2)
            choices.append((f"{label}: {'on' if visible else 'off'} ({state})", descriptor))
        console.note("Metric switches apply when the provider is on. On can include unstarred cached metrics.", "2")
        preview.show(console)
        target = choose(console, "VISIBILITY · " + metrics.clean(provider_id), choices)
        if target is None:
            return
        state = choose(console, "DISPLAY", [("On", "on"), ("Off", "off"), ("Source default", "auto")])
        if state is not None:
            change("provider" if target == "provider" else "metric",
                   provider_id if target == "provider" else target, state)


def icons(console):
    from .menu import change
    provider = select_provider(console)
    if provider is None:
        return
    current = customize.mapping("icon").get(provider, "auto")
    console.note(f"Current icon for {provider}: {current}")
    console.note("Enter a symbol or short label (1–12 characters). none hides the icon; auto restores it.")
    console.note("Custom icons override the Unicode/ASCII choice in icon style.", "2")
    value = input("  Icon (Enter: cancel): ").strip()
    if value:
        change("icon", provider, value)
        change("style", "icons")


def spacing(console):
    from .menu import change, choose
    while True:
        preview.show(console)
        name = choose(console, "SPACING & WIDTH", [
            (f"Prompt gap: {config.value('gap')} spaces (0–8)", "gap"),
            (f"Left/above indent: {config.value('indent')} spaces (0–20)", "indent"),
            (f"Maximum usage width: {config.value('width')} columns (1–240 or auto)", "width")])
        if name is None:
            return
        value = input("  Value (Enter: cancel; auto: default): ").strip()
        if value:
            change(name, value)


def details(console):
    from .menu import change, choose
    while True:
        preview.show(console)
        name = choose(console, "TEXT DETAILS", [
            (f"Metric labels: {config.value('metric-labels')}", "metric-labels"),
            (f"Used/left label: {config.value('mode-label')}", "mode-label"),
            (f"Provider separator: {config.value('separator')}", "separator")])
        if name is None:
            return
        choices = [("On", "on"), ("Off", "off")]
        if name == "metric-labels":
            choices.append(("Auto (labels for multiple compact metrics)", "auto"))
        elif name == "separator":
            choices = [("Pipe: |", "pipe"), ("Dot: ·", "dot"), ("Spaces", "space")]
        value = choose(console, name.upper(), choices)
        if value is not None:
            change(name, value)
