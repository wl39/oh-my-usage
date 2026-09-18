"""Installer regressions: real pipless venvs, ownership, rollback and startup."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import install


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.prefix = Path(self.temp.name) / "install with spaces"
        self.prefix.mkdir()
        (self.prefix / "requirements.txt").write_text("cryptography>=43\n")
        self.environment = self.prefix / ".venv"
        self.python = self.environment / "bin/python"
        self.run = subprocess.run

    def offline_run(self, command, **kwargs):
        # Exercise real Python/venv/ensurepip; downloads and crypto are covered by Ubuntu integration.
        if "install" in command and "pip" in command or command[-1] == "import cryptography":
            return subprocess.CompletedProcess(command, 0)
        return self.run(command, **kwargs)

    def test_repairs_real_pipless_environment_in_place(self):
        self.run([sys.executable, "-m", "venv", "--without-pip", str(self.environment)], check=True)
        sentinel = self.environment / "existing-environment"
        sentinel.touch()
        self.assertFalse(install.python_check(self.python, "-m", "pip", "--version"))
        with patch.object(install.subprocess, "run", side_effect=self.offline_run):
            self.assertEqual(install.prepare_runtime(self.prefix), str(self.python))
        self.assertTrue(install.python_check(self.python, "-m", "pip", "--version"))
        self.assertTrue(sentinel.exists())
        self.assertFalse(list(self.prefix.glob(".venv-backup-*")))

    def test_rebuilds_broken_interpreter(self):
        self.python.parent.mkdir(parents=True)
        self.python.symlink_to("/missing/python")
        with patch.object(install.subprocess, "run", side_effect=self.offline_run):
            install.prepare_runtime(self.prefix)
        self.assertTrue(install.python_check(self.python, "-m", "pip", "--version"))
        self.assertFalse(list(self.prefix.glob(".venv-backup-*")))

    def test_failed_rebuild_restores_original_environment(self):
        self.environment.mkdir()
        sentinel = self.environment / "original"
        sentinel.write_text("preserve")
        def fail(command, **kwargs):
            if "install" in command and "pip" in command:
                raise subprocess.CalledProcessError(1, command)
            return self.offline_run(command, **kwargs)
        with patch.object(install.subprocess, "run", side_effect=fail):
            with self.assertRaises(subprocess.CalledProcessError):
                install.prepare_runtime(self.prefix)
        self.assertEqual(sentinel.read_text(), "preserve")
        self.assertFalse(self.python.exists())
        self.assertFalse(list(self.prefix.glob(".venv-backup-*")))

    def test_venv_symlink_is_not_modified(self):
        external = self.prefix / "external"
        external.mkdir()
        self.environment.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "symlink"):
            install.prepare_runtime(self.prefix)
        self.assertTrue(self.environment.is_symlink())
        self.assertEqual(list(external.iterdir()), [])


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.prefix = self.home / "private install"
        self.launcher = self.home / ".local/bin/oh-my-usage"
        env = patch.dict(os.environ, {"HOME": str(self.home), "ZDOTDIR": str(self.home),
                                     "OH_MY_USAGE_CONFIG_DIR": str(self.home / "config")})
        env.start()
        self.addCleanup(env.stop)

    def test_launcher_runs_from_other_shell_and_uninstalls(self):
        install.install(self.prefix, self.home, shell=False)
        output = subprocess.check_output(["sh", "-c", '"$HOME/.local/bin/oh-my-usage" --version'],
                                         cwd="/", text=True)
        self.assertTrue(output.strip())
        install.install(self.prefix, self.home, shell=False)
        install.uninstall(self.prefix)
        self.assertFalse(self.launcher.exists())

    def test_unrelated_launcher_is_preserved(self):
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_text("user's command")
        with self.assertRaisesRegex(ValueError, "unrelated command"):
            install.install(self.prefix, self.home, shell=False)
        self.assertFalse(self.prefix.exists())
        self.assertEqual(self.launcher.read_text(), "user's command")

    def test_modified_launcher_survives_uninstall(self):
        install.install(self.prefix, self.home, shell=False)
        self.launcher.write_text("replacement")
        install.uninstall(self.prefix)
        self.assertEqual(self.launcher.read_text(), "replacement")

    def test_startup_is_explicit_and_skipped_for_legacy_modes(self):
        with patch.object(install, "first_read") as read:
            install.install(self.prefix, self.home, shell=False, start=True)
            read.assert_called_once_with(self.prefix)
            read.reset_mock()
            install.install(self.prefix, self.home, shell=False, start=False)
            install.install(self.prefix, self.home, shell=False, mode="existing", start=True)
            read.assert_not_called()

    def test_usage_timeout_does_not_fail_installation(self):
        with patch.object(install.subprocess, "run", side_effect=subprocess.TimeoutExpired("start", 90)), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            install.first_read(self.prefix)
        self.assertIn("Installation is complete", output.getvalue())
