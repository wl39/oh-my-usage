"""Exercise the POSIX bootstrap with controlled APT exits, without root/network."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class AptBootstrapTests(unittest.TestCase):
    def run_apt(self, update=0, install=0):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apt = root / 'apt-get'
            apt.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$APT_LOG"
if [ "$1" = -o ]; then shift 2; fi
case $1 in
  update) exit "$UPDATE_STATUS" ;;
  install) test "$DEBIAN_FRONTEND" = noninteractive || exit 99; exit "$INSTALL_STATUS" ;;
  *) exit 98 ;;
esac
''')
            apt.chmod(0o755)
            result = subprocess.run(['sh', '-c', '''
set -eu
. "$BOOTSTRAP"
omu_as_root() { "$@"; }
omu_apt_install python3 python3-venv zsh
echo PREREQUISITES_READY
'''], capture_output=True, text=True, timeout=10,
                env=dict(os.environ, PATH=str(root) + ':' + os.environ['PATH'],
                         BOOTSTRAP=str(ROOT / 'scripts/bootstrap.sh'), APT_LOG=str(root / 'calls'),
                         UPDATE_STATUS=str(update), INSTALL_STATUS=str(install)))
            return result, (root / 'calls').read_text().splitlines()

    def test_normal_update_installs_only_requested_packages(self):
        result, calls = self.run_apt()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ['update', '-o DPkg::Lock::Timeout=60 install -y --no-install-recommends python3 python3-venv zsh'])
        self.assertIn('PREREQUISITES_READY', result.stdout)
        self.assertEqual(result.stderr, '')

    def test_failed_repository_update_still_installs_from_available_indexes(self):
        result, calls = self.run_apt(update=100)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ['update', '-o DPkg::Lock::Timeout=60 install -y --no-install-recommends python3 python3-venv zsh'])
        self.assertIn('could not refresh every repository', result.stderr)
        self.assertIn('PREREQUISITES_READY', result.stdout)

    def test_missing_packages_or_failed_download_cannot_report_success(self):
        for update in (0, 100):
            with self.subTest(update=update):
                result, calls = self.run_apt(update=update, install=100)
                self.assertEqual(result.returncode, 100)
                self.assertEqual(len(calls), 2)
                self.assertNotIn('PREREQUISITES_READY', result.stdout)
                self.assertIn('installation has not completed', result.stderr)

    def test_cancellation_and_sudo_failure_do_not_attempt_install(self):
        for status in (1, 130, 143):
            with self.subTest(status=status):
                result, calls = self.run_apt(update=status)
                self.assertEqual(result.returncode, status)
                self.assertEqual(calls, ['update'])
                self.assertNotIn('PREREQUISITES_READY', result.stdout)


class PythonSelectionTests(unittest.TestCase):
    def run_shell(self, body, **extra):
        return subprocess.run(['sh', '-c', 'set -eu\n. "$BOOTSTRAP"\n' + body],
            capture_output=True, text=True, timeout=10,
            env=dict(os.environ, BOOTSTRAP=str(ROOT / 'scripts/bootstrap.sh'), **extra))

    def test_bad_explicit_python_fails_without_package_changes(self):
        result = self.run_shell('''
python=$OH_MY_USAGE_PYTHON
platform=Linux
with_shell=yes
omu_as_root() { echo UNEXPECTED_PACKAGES; exit 98; }
omu_bootstrap
''', OH_MY_USAGE_PYTHON='/nonexistent/python')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Correct or unset it', result.stderr)
        self.assertNotIn('UNEXPECTED_PACKAGES', result.stdout)

    def test_bad_path_python_uses_healthy_system_python_before_installing(self):
        result = self.run_shell('''
python=/bad/shim
omu_python_ready() { [ "$python" = /usr/bin/python3 ]; }
omu_select_python
printf 'SELECTED=%s\\n' "$python"
''', OH_MY_USAGE_PYTHON='')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SELECTED=/usr/bin/python3', result.stdout)

    def test_valid_explicit_python_is_respected(self):
        result = self.run_shell('''
python=/custom/python
omu_python_base_ready() { [ "$python" = /custom/python ]; }
omu_select_python
printf 'SELECTED=%s\\n' "$python"
''', OH_MY_USAGE_PYTHON='/custom/python')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SELECTED=/custom/python', result.stdout)
