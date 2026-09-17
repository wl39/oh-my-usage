"""A numbered settings menu, with the same validation as direct CLI commands."""

import sys

from . import cache, config
from .terminal import Console


def show(console):
    mode = config.value("mode")
    order = config.value("order")
    color = config.value("color")
    console.section("SETTINGS · saved for this account")
    console.note(f"1. Inline: {config.inline()[0]}")
    console.note(f"2. Meter: {mode if mode != 'auto' else 'auto (OpenUsage)'}")
    console.note(f"3. Order: {order if order != 'auto' else 'auto (OpenUsage)'}")
    console.note(f"4. Inline color: {color if color != 'auto' else 'auto (environment / gray 245)'}")
    console.note("5. Reset meter, order, and color")
    console.note("0. Done")
    console.note("Changes save immediately. Other tabs adopt them at the next prompt.", "2")


def change(name, value=None):
    if name == "reset":
        config.reset()
    elif name == "inline":
        config.save_inline(value)
    else:
        config.save(name, value)
    if name in ("mode", "order", "reset"):
        cache.refresh()


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
        show(console)
        console.note("Use config mode/order/color VALUE to change a setting, or open an interactive terminal.")
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
                                                         ("Follow OpenUsage", "auto")])
                    name = "mode"
                elif selected == "3":
                    value = choose(console, "PROVIDER ORDER", [("Claude, Codex", "claude,codex"),
                        ("Codex, Claude", "codex,claude"), ("Follow OpenUsage", "auto"),
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
                else:
                    raise ValueError("Choose 0–5.")
                if value is not None:
                    change(name, value)
                    console.note("Saved.", "32")
            except ValueError as error:
                console.note(str(error), "33")
    except (EOFError, KeyboardInterrupt):
        console.line()
