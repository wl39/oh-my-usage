import argparse
import http.client
import plistlib
import sys

from . import __version__, cache


def main():
    parser = argparse.ArgumentParser(prog="oh-my-usage", description="Read OpenUsage's menu-bar pins; no daemon.")
    parser.add_argument("command", nargs="?", choices=("show", "refresh", "cached", "doctor"), default="show")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--interval", type=int, default=30, help="cache lifetime in seconds (minimum 5)")
    args = parser.parse_args()
    try:
        if args.command == "cached":
            print(cache.display(cache.directory())[1])
        elif args.command == "doctor":
            from .diagnostics import doctor
            return doctor()
        else:
            print(cache.refresh(force=args.command == "refresh", interval=max(5, args.interval)))
    except (OSError, ValueError, KeyError, TypeError, plistlib.InvalidFileException,
            http.client.HTTPException) as error:
        print("oh-my-usage: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
