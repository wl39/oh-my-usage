import http.client
import plistlib
import subprocess
import sys

from . import __version__, cache, config
from .terminal import Console, HelpParser


def main(argv=None):
    parser = HelpParser(prog="oh-my-usage", description="OpenUsage in your terminal. No additional daemon.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", metavar="command")
    commands.add_parser("help", help="show this help")
    commands.add_parser("start", help="open OpenUsage and refresh the display")
    inline = commands.add_parser("inline", help="enable/disable inline display; saved by default")
    inline.add_argument("state", nargs="?", choices=("on", "off", "status"), default="status")
    inline.add_argument("--session", action="store_true", help="only this shell (requires the loaded zsh plugin)")
    preferences = commands.add_parser("config", help="open settings: meter, order, and inline color")
    preferences.add_argument("setting", nargs="?", choices=("show", "mode", "order", "color", "reset"),
                             help="omit to open the menu; auto follows OpenUsage or the default color")
    preferences.add_argument("value", nargs="?", help="used/left/auto, claude,codex, or a color name / 0–255")
    for name, help_text in (("show", "print usage, using the cache"), ("refresh", "force a fresh read")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--interval", type=int, default=30, help="cache lifetime in seconds (minimum 5)")
    commands.add_parser("cached", help="print the last cached display")
    commands.add_parser("doctor", help="diagnose OpenUsage settings and API access")
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
            if args.setting in ("mode", "order", "color"):
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
                menu.show(Console())
            else:
                menu.run()
        elif args.command == "start":
            from .start import start
            print(start())
        elif args.command == "cached":
            print(cache.display(cache.directory())[1])
        elif args.command == "doctor":
            from .diagnostics import doctor
            return doctor()
        else:
            print(cache.refresh(force=args.command == "refresh", interval=max(5, args.interval)))
    except (OSError, ValueError, KeyError, TypeError, plistlib.InvalidFileException,
            http.client.HTTPException, subprocess.SubprocessError) as error:
        print("oh-my-usage: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
