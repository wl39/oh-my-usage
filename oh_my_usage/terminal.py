"""Small, dependency-free styling for human-facing help and installation output."""

import argparse
import os
import sys
import textwrap

from . import __version__


class Console:
    def __init__(self, stream=None):
        self.stream = stream if stream is not None else sys.stdout
        self.color = (self.stream.isatty() and "NO_COLOR" not in os.environ
                      and os.environ.get("TERM") != "dumb")
        try:
            self.width = max(20, min(96, os.get_terminal_size(self.stream.fileno()).columns))
        except (OSError, ValueError, AttributeError):
            self.width = 80

    def paint(self, text, code):
        return f"\033[{code}m{text}\033[0m" if self.color else text

    def line(self, text="", code=None):
        print(self.paint(text, code) if code else text, file=self.stream)

    def title(self, subtitle):
        self.line()
        self.line("  oh-my-usage", "1;36")
        self.line(f"  v{__version__}  ·  {subtitle}", "2")

    def section(self, label):
        self.line()
        self.line("  " + label, "1;36")

    def note(self, text, code=None, indent=2):
        for line in textwrap.wrap(text, width=self.width - indent, break_long_words=False,
                                  break_on_hyphens=False):
            self.line(" " * indent + line, code)

    def command(self, command, description=""):
        padding = max(2, 35 - len(command))
        if description and 4 + len(command) + padding + len(description) <= self.width:
            self.line("    " + self.paint(command, "36") + " " * padding + description)
        else:
            self.line("    " + self.paint(command, "36"))
            if description:
                self.note(description, indent=6)


def help_screen(console):
    console.title("OpenUsage in your terminal")
    console.section("GET STARTED")
    console.command("oh-my-usage start", "Open the app and refresh usage.")
    console.command("oh-my-usage help", "Help; bare oh-my-usage works too.")
    console.note("After installing, open a new zsh tab. Run from any folder.", "2")
    console.section("INLINE DISPLAY")
    console.command("oh-my-usage inline on", "Turn on and remember.")
    console.command("oh-my-usage inline off", "Turn off and remember.")
    console.command("oh-my-usage inline status", "Show the setting and its source.")
    console.command("oh-my-usage inline on --session", "This shell only; off works too.")
    console.note("Saved choices apply to future tabs and SSH sessions in this account.", "2")
    console.section("SETTINGS")
    console.command("oh-my-usage config", "Choose used/left, order, and color.")
    console.command("oh-my-usage config show", "Show saved display choices.")
    console.command("oh-my-usage config --help", "Set individual options from a command.")
    console.section("TOOLS")
    console.command("oh-my-usage doctor", "Check settings and the local API.")
    console.command("oh-my-usage show", "Print usage using the cache.")
    console.command("oh-my-usage refresh", "Read fresh usage.")
    console.command("oh-my-usage cached", "Print the last saved display.")
    console.command("oh-my-usage --version", "Show the version.")
    console.section("ITERM2 STATUS BAR · ONCE")
    console.note("Add an Interpolated String component with this value:")
    console.command(r"\(user.oh_my_usage)")
    console.note("Inline also works in other terminals and SSH into the same Mac.", "2")
    console.line()
    console.note("https://github.com/wl39/oh-my-usage", "2")
    console.line()


def installed_screen(prefix, shell):
    console = Console()
    console.title("Ready to use")
    console.line("  Installed successfully", "1;32")
    console.note(str(prefix), "2")
    console.section("NEXT")
    console.note("1. Open a new zsh terminal tab." if shell else
                 "1. Load oh-my-usage with your plugin manager.")
    console.note("2. Run from any folder:")
    console.command("oh-my-usage start")
    console.section("MAKE IT YOURS")
    console.command("oh-my-usage inline on", "Enable inline; saved for next time.")
    console.command("oh-my-usage inline off", "Disable inline; saved for next time.")
    console.command("oh-my-usage config", "Choose used/left, order, and color.")
    console.command("oh-my-usage", "Show all commands and help.")
    console.section("ITERM2 STATUS BAR · ONCE")
    console.note("Settings > Profiles > Session > Configure Status Bar")
    console.note("Enable the status bar and add Interpolated String:")
    console.command(r"\(user.oh_my_usage)")
    console.line()


class HelpParser(argparse.ArgumentParser):
    def print_help(self, file=None):
        console = Console(file)
        if self.prog == "oh-my-usage":
            help_screen(console)
        else:
            # Keep argparse's option descriptions and wrapping for subcommands.
            for line in self.format_help().splitlines():
                heading = line and (line.endswith(":") or line.startswith("usage:"))
                console.line(line, "1;36" if heading else None)
