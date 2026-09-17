#!/usr/bin/env python3
"""Render real zsh output with sample data into README media (macOS).

Developer-only dependencies: python -m pip install pillow pyte
Run from the repository: python scripts/record_demo.py
The installed program does not include this script or its dependencies.
"""

import base64
import codecs
import copy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import plistlib
import pty
import select
import shlex
import signal
import struct
import sys
import tempfile
import termios
import time

import pyte
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from oh_my_usage import __version__, settings  # noqa: E402
from oh_my_usage.render import render  # noqa: E402

OUTPUT = ROOT / "docs/assets"
COLS = 104
CELL, LINE, TOP = 11, 26, 120
MONO = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 18)
BOLD = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 18, index=1)
LABEL = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
TITLE = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 24)
BG, FG, MUTED, ACCENT = "#111923", "#d9e2ef", "#8292a7", "#7ac8c3"
COLORS = dict(black="#111923", red="#df8e93", green="#a5c49f", brown="#d9c293",
              blue="#92b8d3", magenta="#bba1c8", cyan=ACCENT, white=FG)


class Session:
    """An isolated PTY; no personal dotfiles, credentials, or network access."""

    def __init__(self, rows=8, configured=False):
        self.temp = tempfile.TemporaryDirectory(prefix="oh-my-usage-demo-")
        self.root = root = Path(self.temp.name)
        self.screen = pyte.Screen(COLS, rows)
        self.stream = pyte.ByteStream(self.screen)
        self.decoder = codecs.getincrementaldecoder("utf-8")()
        self.events = []
        self.started = time.monotonic()
        prefs = {"openusage.enabledProviders.v1": ["codex", "claude"],
                 "openusage.layout.v1.menuBarPins": ["codex.session", "claude.session"],
                 "openusage.layout.v1.providerOrder": ["codex", "claude"]}
        providers = [{"providerId": name.lower(), "displayName": name,
                      "fetchedAt": datetime.now(timezone.utc).isoformat(),
                      "lines": [{"type": "progress", "label": "Session", "used": used,
                                 "limit": 100, "format": {"kind": "percent"}}]}
                     for name, used in (("Codex", 42), ("Claude", 28))]
        (root / "prefs.plist").write_bytes(plistlib.dumps(prefs))
        (root / "usage.json").write_text(json.dumps(providers))
        text = render(providers, settings.parse(prefs), time.time())
        encoded = base64.b64encode(text.encode()).decode()
        (root / "display").write_text(f"{int(time.time())}\n{text}\n{encoded}\nauto|auto\n")
        (root / "config").mkdir()
        (root / "config/inline").write_text("on\n")
        if configured:
            for name, value in (("mode", "left"), ("order", "claude,codex"), ("color", "109")):
                (root / "config" / name).write_text(value + "\n")
        (root / "sitecustomize.py").write_text(
            'import socket\ndef blocked(*args, **kwargs):\n'
            '    raise OSError("Network is disabled in the documentation demo")\n'
            'socket.socket.connect = blocked\n')
        plugin = shlex.quote(str(ROOT / "oh-my-usage.plugin.zsh"))
        (root / ".zshrc").write_text(
            "HISTFILE=''\nsetopt promptsubst\n"
            "PROMPT='%F{108}demo%f %F{245}~/oh-my-usage%f > '\n"
            f"source {plugin}\nbindkey -e\n")
        env = dict(PATH=os.environ["PATH"], HOME=str(root), ZDOTDIR=str(root),
                   USER="demo", LOGNAME="demo", TERM="xterm-256color", TERM_PROGRAM="demo",
                   LC_ALL="en_US.UTF-8", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(root),
                   OH_MY_USAGE_PYTHON=sys.executable, OH_MY_USAGE_CACHE_DIR=str(root),
                   OH_MY_USAGE_CONFIG_DIR=str(root / "config"), OH_MY_USAGE_INTERVAL="3600",
                   OH_MY_USAGE_PREFERENCES=str(root / "prefs.plist"))
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.chdir(root)
            fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", rows, COLS, 0, 0))
            os.execvpe("zsh", ["zsh", "-di"], env)
        self.read(0.3)

    def read(self, seconds=0.12):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if select.select([self.fd], [], [], 0.02)[0]:
                data = os.read(self.fd, 65536)
                self.stream.feed(data)
                text = self.decoder.decode(data)
                if text:
                    self.events.append([round(time.monotonic() - self.started, 4), "o", text])

    def send(self, text):
        os.write(self.fd, text.encode())
        self.read()

    def expect(self, text):
        deadline = time.monotonic() + 3
        while text not in "\n".join(self.screen.display):
            if time.monotonic() > deadline:
                raise RuntimeError(f"Expected {text!r}: {self.screen.display!r}")
            self.read()

    def close(self):
        # Interactive zsh ignores SIGTERM; reap only this isolated demo shell.
        os.kill(self.pid, signal.SIGKILL)
        os.waitpid(self.pid, 0)
        os.close(self.fd)
        self.temp.cleanup()


def color(value, default):
    return default if value == "default" else COLORS.get(value, "#" + value)


def frame(screen, caption):
    width, height = COLS * CELL + 64, TOP + screen.lines * LINE + 56
    image = Image.new("RGB", (width, height), "#0c1218")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((12, 12, width - 12, height - 12), 12, fill=BG, outline="#263447")
    draw.text((32, 26), "oh-my-usage", font=TITLE, fill=FG)
    draw.text((width - 230, 33), f"zsh  /  v{__version__}", font=LABEL, fill=MUTED)
    draw.line((32, 68, width - 32, 68), fill="#263447")
    draw.text((32, 84), caption, font=LABEL, fill=ACCENT)
    for row in range(screen.lines):
        for col in range(screen.columns):
            cell = screen.buffer[row][col]
            fg, bg = color(cell.fg, FG), color(cell.bg, BG)
            if cell.reverse:
                fg, bg = bg, fg
            x, y = 32 + col * CELL, TOP + row * LINE
            if bg != BG:
                draw.rectangle((x, y, x + CELL, y + LINE), fill=bg)
            if cell.data.strip():
                draw.text((x, y), cell.data, font=BOLD if cell.bold else MONO, fill=fg)
            if cell.underscore:
                draw.line((x, y + 22, x + CELL, y + 22), fill=fg)
    if not screen.cursor.hidden:
        x, y = 32 + min(screen.cursor.x, COLS - 1) * CELL, TOP + screen.cursor.y * LINE
        draw.rectangle((x, y + 2, x + CELL - 1, y + 23), outline=ACCENT)
    draw.text((32, height - 34), "Real zsh output  /  example data  /  no account connection", font=LABEL, fill=MUTED)
    return image


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scenes = []
    session = Session()
    def snap(caption, duration):
        scenes.append((copy.deepcopy(session.screen), caption, duration))
    try:
        session.expect("Codex Session 42%")
        snap("01  /  Ready on the first prompt", 2200)
        for character in "echo hello":
            session.send(character)
            snap("02  /  Start typing: the inline hint disappears", 100)
        assert "Session" not in session.screen.display[session.screen.cursor.y]
        snap("02  /  Start typing: the inline hint disappears", 1500)
        session.send("\x15")
        session.expect("Codex Session 42%")
        snap("03  /  Clear the input: the hint returns", 2000)
        for command, expected, caption in (
            ("mode left", "(left)", "04  /  Choose remaining allowance"),
            ("order claude,codex", "Claude Session 72%", "05  /  Put Claude before Codex"),
            ("color cyan", "color: 109 (saved)", "06  /  Save a muted color for future sessions"),
        ):
            session.send("oh-my-usage config " + command + "\r")
            session.expect(expected)
            session.read(0.2)
            snap(caption, 2400)
        cast = [{"version": 2, "width": COLS, "height": 8,
                 "title": "oh-my-usage — real zsh session with sample data",
                 "env": {"TERM": "xterm-256color", "SHELL": "/bin/zsh"}}] + session.events
        (OUTPUT / "inline-demo.cast").write_text("\n".join(json.dumps(item) for item in cast) + "\n")
    finally:
        session.close()
    frames = [frame(screen, caption) for screen, caption, _ in scenes]
    # One palette across all frames avoids flashing and keeps the GIF small.
    palette = frames[-1].quantize(colors=128)
    indexed = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image in frames]
    indexed[0].save(OUTPUT / "inline-demo.gif", save_all=True, append_images=indexed[1:],
                    duration=[duration for _, _, duration in scenes], loop=0, optimize=True)
    session = Session(rows=17, configured=True)
    try:
        session.expect("Claude Session 72%")
        session.send("oh-my-usage config\r")
        session.expect("0. Done")
        frame(session.screen, "SETTINGS  /  One command, saved for the next session").save(
            OUTPUT / "settings.png", optimize=True)
        session.send("0\r")
    finally:
        session.close()
    for artifact in sorted(OUTPUT.iterdir()):
        print(f"{artifact.relative_to(ROOT)}: {artifact.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
