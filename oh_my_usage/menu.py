"""A numbered settings menu, with the same validation as direct CLI commands."""

import sys

from . import cache, config, customize, preview
from .terminal import Console


def show(console, detailed=False):
    mode = config.value("mode")
    order = config.value("order")
    color = config.value("color")
    console.section("SETTINGS · saved for this account")
    console.note(f"1. Inline: {config.inline()[0]}")
    console.note(f"2. Meter: {mode if mode != 'auto' else 'auto (source default)'}")
    console.note(f"3. Order: {order if order != 'auto' else 'auto (source default)'}")
    console.note(f"4. Inline color: {color if color != 'auto' else 'auto (environment / gray 245)'}")
    console.note("5. Reset display settings")
    console.note(f"6. Inline position: {config.value('position')} (narrow screens: above input)")
    console.note(f"7. Inline style: {config.value('style')}")
    console.note(f"8. Icon characters: {config.value('icons')}")
    console.note("9. Preset: left + icons + remaining % (enables inline)")
    console.note(f"10. Providers & metrics: {len(customize.mapping('provider'))} provider / "
                 f"{len(customize.mapping('metric'))} metric overrides")
    console.note(f"11. Custom provider icons: {len(customize.mapping('icon'))} overrides")
    console.note(f"12. Spacing & width: gap {config.value('gap')}, indent {config.value('indent')}, width {config.value('width')}")
    console.note(f"13. Text details: labels {config.value('metric-labels')}, mode {config.value('mode-label')}, "
                 f"separator {config.value('separator')}")
    console.note(f"14. Usage source: {config.source()}")
    console.note("15. Service discovery & connection status")
    console.note("0. Done")
    console.note("Changes save immediately. Other tabs adopt them at the next prompt.", "2")
    preview.show(console)
    if detailed:
        for kind in customize.MAPS:
            overrides = customize.mapping(kind)
            if overrides:
                console.section(kind.upper() + " OVERRIDES")
                for key, value in overrides.items():
                    console.note(f"{key}: {value}")


def change(name, value=None, detail=None):
    if name == "reset":
        config.reset()
    elif name == "preset":
        config.save_inline("on")
        for setting, selected in (("position", "left"), ("style", "icons"), ("mode", "left")):
            config.save(setting, selected)
    elif name == "inline":
        config.save_inline(value)
    elif name in customize.MAPS:
        customize.save(name, value, detail)
    else:
        config.save(name, value)
    if name in ("mode", "order", "style", "icons", "reset", "preset", *customize.MAPS,
                "metric-labels", "mode-label", "separator"):
        cache.refresh(offline=True)


def choose(console, title, choices):
    console.section(title)
    for index, (label, value) in enumerate(choices, 1):
        code = f"38;5;{config.COLORS[value]}" if value in config.COLORS else None
        console.note(f"{index}. {label}", code)
    console.note("Enter: cancel")
    selected = input("  > ").strip()
    if not selected:
        return None
    if not selected.isascii() or not selected.isdigit() or not 1 <= int(selected) <= len(choices):
        raise ValueError("Choose one of the numbers above.")
    return choices[int(selected) - 1][1]


def run():
    console = Console()
    console.title("Settings")
    if not sys.stdin.isatty():
        show(console, detailed=True)
        console.note("Use config SETTING VALUE, or config icon/provider/metric ID VALUE. "
                     "See config --help, or open an interactive terminal.")
        return
    try:
        while True:
            show(console)
            selected = input("  > ").strip()
            if selected in ("", "0"):
                break
            try:
                if selected == "1":
                    value = choose(console, "INLINE DISPLAY", [("On", "on"), ("Off", "off")])
                    name = "inline"
                elif selected == "2":
                    value = choose(console, "METER", [("Used", "used"), ("Left", "left"),
                                                         ("Source default", "auto")])
                    name = "mode"
                elif selected == "3":
                    value = choose(console, "PROVIDER ORDER", [("Claude, Codex", "claude,codex"),
                        ("Codex, Claude", "codex,claude"), ("Source default", "auto"),
                        ("Custom provider IDs", "custom")])
                    if value == "custom":
                        value = input("  Provider IDs, separated by commas (Enter: cancel): ").strip() or None
                    name = "order"
                elif selected == "4":
                    console.note("Colors affect inline text. Set status-bar colors in iTerm2's component settings.", "2")
                    value = choose(console, "INLINE COLOR", [(name.title(), name) for name in config.COLORS]
                                   + [("256-color index", "custom"), ("Use environment / default", "auto")])
                    if value == "custom":
                        value = input("  Color index 0–255 (Enter: cancel): ").strip() or None
                    name = "color"
                elif selected == "5":
                    change("reset")
                    console.note("Display defaults restored. Inline on/off is unchanged.", "32")
                    continue
                elif selected == "6":
                    value = choose(console, "INLINE POSITION", [("Left, before your prompt", "left"),
                        ("Right, beside your right prompt", "right"), ("Auto (right; above on narrow screens)", "auto"),
                        ("Left, after your prompt", "after"), ("Own line above your prompt", "above")])
                    name = "position"
                elif selected == "7":
                    value = choose(console, "INLINE STYLE", [("Full provider and metric names", "text"),
                        ("Icons + compact percentages", "icons")])
                    name = "style"
                elif selected == "8":
                    value = choose(console, "ICON CHARACTERS", [("Unicode symbols: ✳ Claude / ◇ Codex", "unicode"),
                        ("ASCII labels: CL Claude / CX Codex (font fallback)", "ascii")])
                    name = "icons"
                elif selected == "9":
                    change("preset")
                    console.note("Saved: inline on, left, icons, remaining %.", "32")
                    continue
                elif selected in ("10", "11", "12", "13"):
                    from . import custom_menu
                    {"10": custom_menu.visibility, "11": custom_menu.icons,
                     "12": custom_menu.spacing, "13": custom_menu.details}[selected](console)
                    continue
                elif selected == "14":
                    value = choose(console, "USAGE SOURCE", [("Direct (macOS / Linux)", "direct"),
                                                              ("OpenUsage local API (macOS)", "openusage")])
                    name = "source"
                elif selected == "15":
                    from .provider_status import show as show_services
                    show_services()
                    continue
                else:
                    raise ValueError("Choose 0–15.")
                if value is not None:
                    change(name, value)
                    console.note("Saved.", "32")
            except ValueError as error:
                console.note(str(error), "33")
    except (EOFError, KeyboardInterrupt):
        console.line()
