"""Exercise actual interactive ZLE input, rather than calling display hooks by hand."""

import base64
import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import struct
import tempfile
import termios
import time
import unittest


ROOT = Path(__file__).resolve().parent.parent


class Editor:
    def __init__(self, root, *, enabled="on", subst=True, text="Codex 42%",
                 term_program="iTerm.app", columns=240, ssh=False, extra_env=None):
        self.root = root
        self.output = b""
        self.state = root / "state"
        (root / "display").write_text(
            f"{int(time.time())}\n{text}\n{base64.b64encode(text.encode()).decode()}\n")
        (root / "setup.zsh").write_text(r'''
PROMPT='test> '
RPROMPT='theme'
PS2='more> '
HISTFILE=''
HISTSIZE=20
bindkey -e
bindkey '^?' backward-delete-char
[[ $TEST_SUBST == on ]] && setopt promptsubst || unsetopt promptsubst
# Verify an existing editor hook still runs after oh-my-usage installs its own.
_other_redraw() { (( ++_OTHER_CALLS )); return 0; }
zle -N zle-line-pre-redraw _other_redraw
source "$PLUGIN"
_test_observe() {
  builtin printf '%s\0' "$BUFFER" "$RPROMPT" "$PREBUFFER" "$CONTEXT" \
    "${_OH_MY_USAGE_INLINE_ACTIVE:-0}" "$options[promptsubst]" "${_OTHER_CALLS:-0}" \
    "$PROMPT" done > "$TEST_STATE"
}
zle -N _test_observe
bindkey '^X^T' _test_observe
# Cached editing must never launch the Python reader.
_oh_my_usage_refresh() { print unexpected-worker >> "$TEST_WORKER"; }
''')
        env = dict(os.environ, HOME=str(root), ZDOTDIR=str(root),
                   PLUGIN=str(ROOT / "oh-my-usage.plugin.zsh"),
                   OH_MY_USAGE_CACHE_DIR=str(root), OH_MY_USAGE_INLINE=enabled,
                   OH_MY_USAGE_CONFIG_DIR=str(root / "config"),
                   OH_MY_USAGE_DISPLAY="status", OH_MY_USAGE_INLINE_COLOR="245",
                   OH_MY_USAGE_INTERVAL="3600", TERM="xterm-256color",
                   TERM_PROGRAM=term_program, TMUX="", STY="", OH_MY_USAGE_INLINE_WIDTH="",
                   SSH_CONNECTION="127.0.0.1 50000 127.0.0.1 22" if ssh else "",
                   TEST_SUBST="on" if subst else "off", TEST_STATE=str(self.state),
                   TEST_WORKER=str(root / "worker"), TEST_SETUP=str(root / "setup.zsh"))
        env.update(extra_env or {})
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.chdir(root)
            os.execvpe("zsh", ["zsh", "-dfi"], env)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", 24, columns, 0, 0))
        self.send(b'source "$TEST_SETUP"\r')

    def send(self, data):
        os.write(self.fd, data)

    def drain(self):
        while select.select([self.fd], [], [], 0.02)[0]:
            try:
                chunk = os.read(self.fd, 65536)
            except OSError as error:
                if error.errno == errno.EIO:
                    break
                raise
            if not chunk:
                break
            self.output += chunk

    def wait(self, buffer="", *, visible=True, context="start", active="1", theme="theme", left="test> "):
        deadline = time.monotonic() + 5
        fields = []
        while time.monotonic() < deadline:
            # Let the edit redraw, then inspect it through an ordinary widget.
            self.drain()
            self.state.unlink(missing_ok=True)
            self.send(b"\x18\x14")
            self.drain()
            if self.state.exists():
                fields = self.state.read_bytes().decode().split("\0")
                if (len(fields) == 10 and fields[8] == "done" and fields[0] == buffer
                        and fields[3] == context and fields[4] == active
                        and (fields[1] != theme or fields[7] != left) == visible):
                    return fields
        raise AssertionError(f"ZLE did not reach expected state: {fields!r}\n{self.output[-3000:]!r}")

    def command(self, command):
        self.state.unlink(missing_ok=True)
        self.send(command.encode() + b"\r")

    def close(self):
        try:
            os.kill(self.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        os.waitpid(self.pid, 0)
        os.close(self.fd)


class InlineTests(unittest.TestCase):
    def editor(self, **options):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        editor = Editor(Path(temp.name), **options)
        self.addCleanup(editor.close)
        return editor

    def test_typing_space_delete_paste_history_and_multiline(self):
        editor = self.editor()
        first = editor.wait()
        self.assertIn(b"\x1b[38;5;245mCodex 42%", editor.output)
        editor.send(b" ")
        editor.wait(" ", visible=False)
        editor.send(b"\x7f")
        editor.wait()
        editor.send(b"x")
        editor.wait("x", visible=False)
        editor.send(b"\x7f")
        editor.wait()
        editor.send(b"\x1b[200~echo pasted\x1b[201~")
        editor.wait("echo pasted", visible=False)
        editor.send(b"\r")
        editor.wait()
        editor.send(b"\x10")  # Ctrl-P: recall previous command.
        editor.wait("echo pasted", visible=False)
        editor.send(b"\x15")  # Ctrl-U: erase the whole input.
        editor.wait()
        editor.send(b"echo '\r")
        state = editor.wait("", visible=False, context="cont")
        self.assertTrue(state[2])  # Empty continuation line is still part of a command.
        editor.send(b"\x03")
        final = editor.wait()
        self.assertGreater(int(final[6]), int(first[6]))
        self.assertFalse((editor.root / "worker").exists())

    def test_saved_choice_reaches_other_and_new_sessions_but_session_override_does_not(self):
        with tempfile.TemporaryDirectory() as temp:
            shared = {"OH_MY_USAGE_CONFIG_DIR": temp}
            first = self.editor(enabled="off", extra_env=shared)
            other = self.editor(enabled="off", extra_env=shared)
            first.wait(visible=False, active="0")
            other.wait(visible=False, active="0")
            first.command("oh-my-usage inline on")
            first.wait()
            self.assertEqual((Path(temp) / "inline").read_text(), "on\n")
            # Already-open shells adopt the saved value at their next prompt.
            other.command(":")
            other.wait()
            fresh = self.editor(enabled="off", extra_env=shared)
            fresh.wait()
            first.command("oh-my-usage inline off --session")
            first.wait(visible=False, active="0")
            self.assertEqual((Path(temp) / "inline").read_text(), "on\n")
            other.command(":")
            other.wait()
            first.command("oh-my-usage inline off")
            first.wait(visible=False, active="0")
            other.command(":")
            other.wait(visible=False, active="0")
            fresh.command(":")
            fresh.wait(visible=False, active="0")
            # Saving a new value also clears this shell's temporary override.
            first.command("oh-my-usage inline on --session")
            first.wait()
            first.command("oh-my-usage inline off")
            first.wait(visible=False, active="0")

    def test_invalid_saved_text_is_never_executed(self):
        editor = self.editor(enabled="off")
        editor.wait(visible=False, active="0")
        directory = editor.root / "config"
        directory.mkdir()
        (directory / "inline").write_text('$(touch INJECTED)\n')
        editor.command(":")
        editor.wait(visible=False, active="0")
        self.assertFalse((editor.root / "INJECTED").exists())

    def test_toggle_theme_changes_and_unload(self):
        editor = self.editor(enabled="off")
        editor.wait(visible=False, active="0")
        editor.command("oh-my-usage inline on")
        editor.wait()
        editor.command("oh-my-usage inline off")
        editor.wait(visible=False, active="0")
        editor.command("RPROMPT='new theme'; oh-my-usage inline on")
        editor.wait(theme="new theme")
        editor.send(b"x")
        state = editor.wait("x", visible=False, theme="new theme")
        self.assertEqual(state[1], "new theme")
        editor.send(b"\x15")
        editor.wait(theme="new theme")
        editor.command("oh-my-usage-unload")
        editor.wait(visible=False, active="0", theme="new theme")
        editor.send(b"x")
        editor.wait("x", visible=False, active="0", theme="new theme")

    def test_global_off_and_repeated_source(self):
        editor = self.editor()
        editor.wait()
        editor.command('source "$PLUGIN"; source "$PLUGIN"; OH_MY_USAGE_DISPLAY=off')
        editor.wait(visible=False, active="0")
        editor.command("OH_MY_USAGE_DISPLAY=status")
        editor.wait()
        editor.command("OH_MY_USAGE_INLINE=off")
        editor.wait(visible=False, active="0")

    def test_usage_is_literal_with_and_without_prompt_substitution(self):
        text = '42% $(touch INJECTED) `touch INJECTED2` %F{red} ${USER} \\test'
        for subst in (False, True):
            with self.subTest(promptsubst=subst):
                editor = self.editor(subst=subst, text=text)
                state = editor.wait()
                self.assertEqual(state[5], "on" if subst else "off")
                self.assertIn(text.encode(), editor.output)
                self.assertNotIn(b"\x1b[31m", editor.output)
                self.assertFalse((editor.root / "INJECTED").exists())
                self.assertFalse((editor.root / "INJECTED2").exists())

    def test_color_and_cache_update_when_input_becomes_empty(self):
        editor = self.editor()
        editor.wait()
        editor.command("OH_MY_USAGE_INLINE_COLOR=250")
        editor.wait()
        self.assertIn(b"\x1b[38;5;250mCodex 42%", editor.output)
        editor.send(b"x")
        editor.wait("x", visible=False)
        (editor.root / "display").write_text(f"{int(time.time())}\nUpdated 24%\nQQ==\n")
        editor.send(b"\x7f")
        editor.wait()
        self.assertIn(b"Updated 24%", editor.output)
        editor.command("OH_MY_USAGE_INLINE_COLOR='$(touch INJECTED)'")
        editor.wait()
        self.assertIn(b"\x1b[38;5;245mUpdated 24%", editor.output)
        self.assertFalse((editor.root / "INJECTED").exists())

    def test_ssh_inline_without_iterm_and_no_osc_output(self):
        for program in ("", "Termius"):
            with self.subTest(program=program):
                editor = self.editor(term_program=program, ssh=True, enabled="off")
                editor.wait(visible=False, active="0")
                editor.command("oh-my-usage inline on")
                editor.wait()
                self.assertIn(b"Codex 42%", editor.output)
                editor.send(b"x")
                editor.wait("x", visible=False)
                editor.send(b"\x7f")
                editor.wait()
                self.assertNotIn(b"\x1b]1337;", editor.output)

    def test_phone_width_and_resize_keep_a_short_hint_visible(self):
        editor = self.editor(term_program="", ssh=True, columns=40,
                             text="Codex Session 42% | Weekly 74% | Claude Session 92%")
        state = editor.wait()
        self.assertIn("Codex Session 42% | Weekly 74% | Clau…".encode(), editor.output)
        self.assertEqual(state[1], "theme")  # A phone's theme keeps its own right prompt.
        editor.command("PROMPT='a very long mobile prompt> '")
        editor.wait(left="a very long mobile prompt> ")
        offset = len(editor.output)
        editor.send(b"x")
        editor.wait("x", visible=False, left="a very long mobile prompt> ")
        self.assertNotIn(b"Codex Session", editor.output[offset:])
        editor.send(b"\x7f")
        editor.wait(left="a very long mobile prompt> ")
        fcntl.ioctl(editor.fd, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 120, 0, 0))
        os.kill(editor.pid, signal.SIGWINCH)
        editor.send(b"\x0c")
        editor.wait(left="a very long mobile prompt> ")
        self.assertIn(b"Weekly 74% | Claude Session 92%", editor.output)

    def test_inline_in_tmux_does_not_send_iterm_status_codes(self):
        editor = self.editor(extra_env={"TMUX": "test-session"})
        editor.wait()
        self.assertIn(b"Codex 42%", editor.output)
        self.assertNotIn(b"\x1b]1337;", editor.output)


if __name__ == "__main__":
    unittest.main()
