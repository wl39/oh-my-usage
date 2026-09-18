import http.client
import json
import plistlib
import subprocess
import sys

from . import __version__, cache, config
from .terminal import Console, HelpParser


def main(argv=None):
    parser = HelpParser(prog="oh-my-usage", description="AI usage in your terminal. Independent discovery on macOS and Linux.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", metavar="command")
    commands.add_parser("help", help="show this help")
    commands.add_parser("start", help="discover signed-in services and refresh the display")
    inline = commands.add_parser("inline", help="enable/disable inline display; saved by default")
    inline.add_argument("state", nargs="?", choices=("on", "off", "status"), default="status")
    inline.add_argument("--session", action="store_true", help="only this shell (requires the loaded zsh plugin)")
    preferences = commands.add_parser("config", help="open settings and preview the inline display")
    preferences.add_argument("setting", nargs="?", choices=("show", "mode", "order", "color", "source", *config.DEFAULTS,
                                                            "icon", "provider", "metric", "reset"),
                             help="omit to open the menu; auto restores the source's defaults")
    preferences.add_argument("value", nargs="?", help="meter: used/left/auto; order: claude,codex; color: name/0–255; "
                             "position: left/right/after/above/auto; style: text/icons; icons: unicode/ascii; "
                             "icon/provider/metric: provider or metric ID; gap/indent/width: columns")
    preferences.add_argument("detail", nargs="?", help="icon: symbol/none/auto; provider/metric: on/off/auto")
    for name, help_text in (("show", "print usage, using the cache"), ("refresh", "force a fresh read")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--interval", type=int, default=30, help="cache lifetime in seconds (minimum 5)")
    commands.add_parser("cached", help="print the last cached display")
    commands.add_parser("doctor", help="diagnose service connections and usage access")
    services = commands.add_parser("providers", aliases=["discover"], help="list all services and auto-detected connections")
    services.add_argument("--refresh", action="store_true", help="fetch usage now")
    services.add_argument("--json", action="store_true", help="print redacted connection status as JSON")
    history = commands.add_parser("history", help="read successful usage snapshots from the last 30 days")
    from .providers.adapters import PROVIDERS
    history.add_argument("--provider", choices=tuple(PROVIDERS))
    history.add_argument("--days", type=int, choices=range(1, 31), default=7, metavar="1..30")
    connect = commands.add_parser("connect", help="save an API key using hidden interactive input")
    connect.add_argument("provider", choices=("openrouter", "zai", "opencode", "devin"))
    args = parser.parse_args(argv)
    if args.command in (None, "help"):
        parser.print_help()
        return 0
    try:
        if args.command == "inline":
            if args.session:
                inline.error("--session requires the loaded zsh plugin; open a new zsh tab after installing")
            if args.state != "status":
                config.save_inline(args.state)
            value, origin = config.inline()
            print(f"inline: {value} ({origin})")
        elif args.command == "config":
            from . import menu
            if args.setting in ("icon", "provider", "metric"):
                if args.value is None or args.detail is None:
                    preferences.error("use config icon PROVIDER SYMBOL, provider ID on/off/auto, or metric ID on/off/auto")
                menu.change(args.setting, args.value, args.detail)
                print(f"{args.setting} {args.value}: {args.detail} (saved)")
            elif args.detail is not None:
                preferences.error("this setting takes only one value")
            elif args.setting in ("mode", "order", "color", "source", *config.DEFAULTS):
                if args.value is None:
                    preferences.error("this setting requires a value; use auto to restore its default")
                menu.change(args.setting, args.value)
                print(f"{args.setting}: {config.value(args.setting)} (saved)")
            elif args.value is not None:
                preferences.error("show/reset do not take a value")
            elif args.setting == "reset":
                menu.change("reset")
                print("Display defaults restored. Inline on/off is unchanged.")
            elif args.setting == "show":
                menu.show(Console(), detailed=True)
            else:
                menu.run()
        elif args.command == "start":
            from .start import start
            print(start())
        elif args.command == "cached":
            print(cache.display(cache.directory())[1])
        elif args.command == "doctor":
            if config.source() == "direct":
                from .provider_status import show
                show(refresh=True)
                return 0
            from .diagnostics import doctor
            return doctor()
        elif args.command in ("providers", "discover"):
            from .provider_status import show
            show(args.refresh, args.json)
        elif args.command == "history":
            from .providers.collector import history
            print(json.dumps(history(cache.directory(), args.provider, args.days), ensure_ascii=False, indent=2))
        elif args.command == "connect":
            from .provider_status import connect
            connect(args.provider)
        else:
            print(cache.refresh(force=args.command == "refresh", interval=max(5, args.interval)))
    except (OSError, ValueError, KeyError, TypeError, plistlib.InvalidFileException,
            http.client.HTTPException, subprocess.SubprocessError) as error:
        print("oh-my-usage: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
