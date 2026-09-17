import contextlib
import fcntl
import io
import os
from pathlib import Path
import pty
import re
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from unittest.mock import patch

from oh_my_usage import config
from oh_my_usage.__main__ import main
from oh_my_usage.start import start
from oh_my_usage.terminal import installed_screen

ROOT = Path(__file__).resolve().parent.parent


class CommandTests(unittest.TestCase):
    def test_config_cli_saves_validated_values_and_rejects_invalid_ones(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"OH_MY_USAGE_CONFIG_DIR": temp}), \
             patch("oh_my_usage.cache.refresh") as refresh, contextlib.redirect_stdout(io.StringIO()):
            for name, value, saved in (("mode", "left", "left"), ("order", "Claude, Codex", "claude,codex"),
                                        ("color", "cyan", "109")):
                self.assertEqual(main(["config", name, value]), 0)
                self.assertEqual(config.value(name), saved)
                self.assertEqual((Path(temp) / name).stat().st_mode & 0o777, 0o600)
            self.assertEqual(refresh.call_count, 2)
            for name, value in (("mode", "remaining"), ("order", "claude,,codex"), ("order", "codex,codex"),
                                ("color", "256"), ("color", "$(touch INJECTED)"), ("color", "-1")):
                before = (Path(temp) / name).read_text()
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(["config", name, value]), 1)
                self.assertEqual((Path(temp) / name).read_text(), before)
            config.save_inline("on")
            self.assertEqual(main(["config", "reset"]), 0)
            self.assertEqual(config.inline(), ("on", "saved"))
            self.assertEqual(config.view_key(), "auto|auto")
            self.assertEqual(config.value("color"), "auto")

    def test_config_menu_choices_cancellation_and_noninteractive_output(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"OH_MY_USAGE_CONFIG_DIR": temp}), \
             patch("oh_my_usage.cache.refresh"), contextlib.redirect_stdout(io.StringIO()) as output:
            with patch("sys.stdin.isatty", return_value=True), \
                 patch("builtins.input", side_effect=["2", "2", "3", "1", "4", "2", "0"]):
                self.assertEqual(main(["config"]), 0)
            self.assertEqual(config.value("mode"), "left")
            self.assertEqual(config.value("order"), "claude,codex")
            self.assertEqual(config.value("color"), "109")
            self.assertIn("Saved.", output.getvalue())
            for inputs in (["2", "", "0"], ["3", "4", "", "0"], [KeyboardInterrupt()], [EOFError()]):
                with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=inputs):
                    self.assertEqual(main(["config"]), 0)
                self.assertEqual(config.value("mode"), "left")
                self.assertEqual(config.value("order"), "claude,codex")
            with patch("sys.stdin.isatty", return_value=False), patch("builtins.input") as read:
                self.assertEqual(main(["config"]), 0)
                read.assert_not_called()

    def test_help_color_in_terminal_and_plain_output_when_redirected_or_disabled(self):
        env = dict(os.environ, TERM="xterm-256color")
        env.pop("NO_COLOR", None)
        command = [sys.executable, "-m", "oh_my_usage", "help"]
        plain = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, check=True).stdout
        self.assertNotIn(b"\x1b", plain)
        for extra, colored, width in (({}, True, 80), ({}, True, 40), ({"NO_COLOR": "1"}, False, 80),
                                      ({"NO_COLOR": ""}, False, 80), ({"TERM": "dumb"}, False, 80)):
            master, slave = pty.openpty()
            process = None
            try:
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, width, 0, 0))
                process = subprocess.Popen(command, cwd=ROOT, env=dict(env, **extra),
                                           stdout=slave, stderr=slave)
                output = b""
                deadline = time.monotonic() + 5
                while True:
                    # Drain while the process writes: a PTY can have a small buffer.
                    if select.select([master], [], [], 0.1)[0]:
                        output += os.read(master, 8192)
                    elif process.poll() is not None:
                        break
                    self.assertLess(time.monotonic(), deadline, "help output timed out")
                self.assertEqual(process.wait(), 0, output)
                self.assertEqual(b"\x1b[" in output, colored)
                clean = re.sub(rb"\x1b\[[0-9;]*m", b"", output).replace(b"\r\n", b"\n")
                if width == 80:
                    self.assertEqual(clean, plain)
                else:
                    self.assertEqual(clean.split(), plain.split())
                    self.assertTrue(all(len(line) <= width for line in clean.decode().splitlines()))
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)
                os.close(slave)

    def test_install_help_explains_normal_and_manual_loading_without_colors_in_logs(self):
        for shell in (True, False):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                installed_screen(Path("/example/oh-my-usage"), shell)
            text = output.getvalue()
            self.assertNotIn("\x1b", text)
            self.assertIn("oh-my-usage start", text)
            self.assertIn("new zsh terminal tab" if shell else "plugin manager", text)

    def test_default_and_explicit_help_do_not_read_usage_or_write_settings(self):
        for args in ([], ["help"], ["--help"]):
            with self.subTest(args=args), patch("oh_my_usage.cache.refresh") as refresh, \
                 patch("oh_my_usage.config.save_inline") as save, \
                 patch("oh_my_usage.config.inline") as read:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    if args == ["--help"]:
                        with self.assertRaises(SystemExit) as exit_status:
                            main(args)
                        self.assertEqual(exit_status.exception.code, 0)
                    else:
                        self.assertEqual(main(args), 0)
                self.assertIn("oh-my-usage start", output.getvalue())
                self.assertIn("--session", output.getvalue())
                refresh.assert_not_called()
                save.assert_not_called()
                read.assert_not_called()

    def test_inline_persists_across_separate_cli_processes(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, OH_MY_USAGE_CONFIG_DIR=temp, OH_MY_USAGE_INLINE="on")
            for state in ("off", "on"):
                for args in (["inline", state], ["inline", "status"]):
                    result = subprocess.run([sys.executable, "-m", "oh_my_usage", *args],
                                            env=env, cwd=ROOT, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, f"inline: {state} (saved)\n")
                self.assertEqual((Path(temp) / "inline").stat().st_mode & 0o777, 0o600)

    def test_bad_arguments_or_external_session_flag_do_not_save(self):
        for args in (["inline", "oops"], ["inline", "on", "--session"], ["inline", "on", "extra"]):
            with patch("oh_my_usage.config.save_inline") as save, \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(args)
            self.assertEqual(caught.exception.code, 2)
            save.assert_not_called()

    def test_save_failure_is_reported(self):
        with patch("oh_my_usage.config.save_inline", side_effect=PermissionError("read only")), \
             contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(main(["inline", "on"]), 1)
        self.assertIn("read only", output.getvalue())

    def test_settings_path_defaults_and_invalid_data(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
                "HOME": temp, "XDG_CONFIG_HOME": "", "OH_MY_USAGE_CONFIG_DIR": "",
                "OH_MY_USAGE_INLINE": "on"}):
            self.assertEqual(config.directory(), Path(temp) / ".config/oh-my-usage")
            config.save_inline("off")
            self.assertEqual(config.inline(), ("off", "saved"))
            self.assertEqual(config.directory().stat().st_mode & 0o777, 0o700)
            (config.directory() / "inline").write_text('$(touch INJECTED)\n')
            self.assertEqual(config.inline(), ("on", "environment"))
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": temp}):
                self.assertEqual(config.directory(), Path(temp) / "oh-my-usage")

    def test_start_opens_app_and_retries_api_startup(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"OH_MY_USAGE_APP_DIR": temp}):
            app = Path(temp) / "OpenUsage.app"
            app.mkdir()
            def refresh(**kwargs):
                self.assertTrue(kwargs["force"])
                self.assertEqual(kwargs["fetch"](), [])
                return "ready"
            with patch("oh_my_usage.start.subprocess.run") as launch, \
                 patch("oh_my_usage.start.source.fetch", side_effect=[OSError(), []]) as fetch, \
                 patch("oh_my_usage.start.time.sleep") as sleep, \
                 patch("oh_my_usage.start.cache.refresh", side_effect=refresh):
                self.assertEqual(start(), "ready")
            self.assertEqual(launch.call_args.args[0], ["/usr/bin/open", "-g", str(app)])
            self.assertEqual(fetch.call_count, 2)
            sleep.assert_called_once_with(0.2)

    def test_start_missing_app_reports_install_instruction(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"OH_MY_USAGE_APP_DIR": temp}), \
             contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(main(["start"]), 1)
        self.assertIn("./install.sh", output.getvalue())


if __name__ == "__main__":
    unittest.main()
