import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from oh_my_usage import config
from oh_my_usage.__main__ import main
from oh_my_usage.start import start

ROOT = Path(__file__).resolve().parent.parent


class CommandTests(unittest.TestCase):
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
