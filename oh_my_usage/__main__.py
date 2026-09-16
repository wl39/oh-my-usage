import argparse
import http.client
import plistlib
import subprocess
import sys

from . import __version__, cache, config


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="oh-my-usage", description="OpenUsage in your terminal. No additional daemon.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Quick start (after installing, open a new zsh tab):
  oh-my-usage start              Open OpenUsage and refresh the display
  oh-my-usage inline on          Save inline display ON for future sessions
  oh-my-usage inline off         Save inline display OFF for future sessions
  oh-my-usage inline on --session  Enable only in this shell

iTerm2 status bar (one-time setup): add Interpolated String with
  \\(user.oh_my_usage)
Inline works in other terminals and SSH into the same Mac account.
Guide: https://github.com/wl39/oh-my-usage""")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", metavar="command")
    commands.add_parser("help", help="show this help")
    commands.add_parser("start", help="open OpenUsage and refresh the display")
    inline = commands.add_parser("inline", help="enable/disable inline display; saved by default")
    inline.add_argument("state", nargs="?", choices=("on", "off", "status"), default="status")
    inline.add_argument("--session", action="store_true", help="only this shell (requires the loaded zsh plugin)")
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
