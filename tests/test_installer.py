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
        if "install" in command and "pip" in command or command[-1] == install.CRYPTO_CHECK:
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
            with self.assertRaisesRegex(ValueError, "Python dependency installation failed"):
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


class AuditTests(unittest.TestCase):
    setUp = InstallationTests.setUp

    def test_zshenv_redirected_config_loads_in_a_new_shell(self):
        os.environ.pop('ZDOTDIR', None)
        actual = self.home / 'zsh config'
        actual.mkdir()
        (self.home / '.zshenv').write_text('ZDOTDIR="$HOME/zsh config"\n')
        (actual / '.zshrc').write_text('# keep my theme\n')
        install.install(self.prefix, self.home)
        self.assertFalse((self.home / '.zshrc').exists())
        self.assertIn('# keep my theme', (actual / '.zshrc').read_text())
        output = subprocess.check_output(['zsh', '-di', '-c', 'whence -w oh-my-usage'], text=True)
        self.assertIn('oh-my-usage: function', output)
        install.uninstall(self.prefix)
        self.assertEqual((actual / '.zshrc').read_text(), '# keep my theme\n')

    def test_no_shell_does_not_require_valid_zsh_config(self):
        rc = self.home / '.zshrc'
        rc.write_text(install.START + '\n')
        install.install(self.prefix, self.home, shell=False)
        self.assertEqual(rc.read_text(), install.START + '\n')

    def test_disabled_shell_rcs_stops_before_copying_files(self):
        (self.home / '.zshenv').write_text('unsetopt rcs\n')
        with self.assertRaisesRegex(ValueError, 'RCS is disabled'):
            install.install(self.prefix, self.home)
        self.assertFalse(self.prefix.exists())

    def test_non_directory_settings_path_stops_before_copying_files(self):
        (self.home / 'config').write_text('user data')
        with self.assertRaisesRegex(ValueError, 'Settings directory has the wrong file type'):
            install.install(self.prefix, self.home, shell=False)
        self.assertFalse(self.prefix.exists())
        self.assertEqual((self.home / 'config').read_text(), 'user data')

    def test_relative_settings_path_is_rejected_before_copying_files(self):
        with patch.dict(os.environ, {'OH_MY_USAGE_CONFIG_DIR': 'relative-settings'}):
            with self.assertRaisesRegex(ValueError, 'must be absolute paths'):
                install.install(self.prefix, self.home, shell=False)
        self.assertFalse(self.prefix.exists())

    @unittest.skipIf(os.geteuid() == 0, 'root bypasses filesystem permission bits')
    def test_readonly_shell_file_fails_before_copying_files(self):
        rc = self.home / '.zshrc'
        rc.write_text('# my config\n')
        rc.chmod(0o400)
        try:
            with self.assertRaisesRegex(ValueError, 'zsh configuration is not writable'):
                install.install(self.prefix, self.home)
            self.assertFalse(self.prefix.exists())
            self.assertEqual(rc.read_text(), '# my config\n')
        finally:
            rc.chmod(0o600)

    def test_repair_in_installed_directory_keeps_application_files(self):
        install.install(self.prefix, self.home, shell=False)
        before = (self.prefix / 'bin/oh-my-usage').read_bytes()
        with patch.object(install, 'ROOT', self.prefix):
            install.install(self.prefix, self.home, shell=False)
        self.assertEqual((self.prefix / 'bin/oh-my-usage').read_bytes(), before)

    def test_broken_record_is_rejected_without_changing_it(self):
        self.prefix.mkdir()
        marker = self.prefix / '.oh-my-usage-install'
        marker.write_text('[]')
        with self.assertRaisesRegex(ValueError, 'Invalid installation record'):
            install.install(self.prefix, self.home, shell=False)
        self.assertEqual(marker.read_text(), '[]')

    def test_uninstaller_falls_back_when_private_python_is_gone(self):
        install.install(self.prefix, self.home, shell=False)
        (self.prefix / 'python-path').write_text('/missing/private/python\n')
        result = subprocess.run([str(self.prefix / 'install.sh'), 'uninstall'],
            env=dict(os.environ, OH_MY_USAGE_PYTHON=''), capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.prefix.exists())

    def test_installed_cli_ignores_foreign_python_home(self):
        install.install(self.prefix, self.home, shell=False)
        result = subprocess.run([str(self.launcher), '--version'],
            env=dict(os.environ, PYTHONHOME='/not/a/python/runtime', PYTHONUSERBASE='/unused'),
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_installed_cli_uses_its_recorded_runtime_instead_of_bootstrap_override(self):
        install.install(self.prefix, self.home, shell=False)
        result = subprocess.run([str(self.launcher), '--version'],
            env=dict(os.environ, OH_MY_USAGE_PYTHON='/missing/bootstrap-python'),
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_quoted_tilde_paths_agree_between_shell_and_python(self):
        with patch.dict(os.environ, {'OH_MY_USAGE_CONFIG_DIR': '~/.config/oh-my-usage',
                                    'OH_MY_USAGE_CACHE_DIR': '~/.cache/oh-my-usage'}):
            install.install(self.prefix, self.home)
            result = subprocess.run(['zsh', '-di', '-c',
                'print -r -- "$_OH_MY_USAGE_CONFIG"; print -r -- "$_OH_MY_USAGE_CACHE"; oh-my-usage inline status'],
                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.home / '.config/oh-my-usage'), result.stdout)
        self.assertIn(str(self.home / '.cache/oh-my-usage'), result.stdout)
        self.assertIn('inline: on (saved)', result.stdout)

    def test_concurrent_installation_is_rejected_without_unlocking_owner(self):
        with install.installation_lock(self.home):
            with self.assertRaisesRegex(ValueError, 'Another oh-my-usage installation'):
                with install.installation_lock(self.home):
                    self.fail('second installer acquired the lock')
        with install.installation_lock(self.home):
            pass

    def test_pip_location_overrides_are_removed_but_network_settings_are_preserved(self):
        with patch.dict(os.environ, {'PYTHONHOME': '/wrong', 'PIP_TARGET': '/wrong',
                                    'PIP_PREFIX': '/wrong', 'PIP_USER': '1',
                                    'PIP_INDEX_URL': 'https://packages.example.test/simple',
                                    'HTTPS_PROXY': 'http://proxy.example.test',
                                    'PIP_CERT': '/company/cert.pem'}):
            env = install.runtime_environment()
        for name in ('PYTHONHOME', 'PIP_TARGET', 'PIP_PREFIX'):
            self.assertNotIn(name, env)
        self.assertEqual(env['PIP_USER'], '0')
        self.assertEqual(env['PIP_INDEX_URL'], 'https://packages.example.test/simple')
        self.assertEqual(env['HTTPS_PROXY'], 'http://proxy.example.test')
        self.assertEqual(env['PIP_CERT'], '/company/cert.pem')
