"""Fault-injection checks in a disposable Ubuntu container with prerequisites ready.

Run as an ordinary user with sudo. Pass a wheel directory populated by
python3 -m pip download --only-binary=:all: -r /src/requirements.txt -d DIR.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SRC = Path('/src')
WHEELS = str(Path(sys.argv[1]).resolve())


def run(command, env, success=True):
    result = subprocess.run([str(part) for part in command], env=env, cwd=SRC,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=210)
    if (result.returncode == 0) != success:
        raise AssertionError(result.stdout)
    return result.stdout


def environment(home):
    home.mkdir(parents=True)
    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
               XDG_CACHE_HOME=str(home / '.cache'), PYTHONDONTWRITEBYTECODE='1',
               PIP_NO_INDEX='1', PIP_FIND_LINKS=WHEELS)
    for key in ('ZDOTDIR', 'OH_MY_USAGE_PYTHON', 'OH_MY_USAGE_CONFIG_DIR',
                'OH_MY_USAGE_CACHE_DIR', 'OH_MY_USAGE_SOURCE', 'PYTHONHOME',
                'PIP_USER', 'PIP_TARGET', 'PIP_PREFIX'):
        env.pop(key, None)
    return env


with tempfile.TemporaryDirectory(prefix='omu-recovery-') as temp:
    root = Path(temp)
    home = root / 'home with spaces'
    env = environment(home)
    prefix = home / '.local/share/oh-my-usage'
    rc = home / 'my zsh/.zshrc'
    rc.parent.mkdir()
    rc.write_text('# keep this user configuration\n')
    (home / '.zshenv').write_text('ZDOTDIR="$HOME/my zsh"\n')
    # Poison common inherited settings while preserving the offline package index.
    dirty = dict(env, PYTHONHOME='/missing/foreign-python', PYTHONUSERBASE='/missing/user-base',
                 PIP_USER='1', PIP_TARGET=str(root / 'wrong target'), PIP_PREFIX=str(root / 'wrong prefix'))
    run([SRC / 'install.sh', '--no-start'], dirty)
    assert not (root / 'wrong target').exists()
    assert not (root / 'wrong prefix').exists()
    assert not (home / '.zshrc').exists()
    assert json.loads((prefix / '.oh-my-usage-install').read_text())['rc'] == str(rc)
    assert 'function' in run(['zsh', '-di', '-c', 'whence -w oh-my-usage'], env)
    assert run([prefix / 'bin/oh-my-usage', '--version'], dirty).strip()
    print('PASS: inherited Python/pip settings, paths with spaces and .zshenv redirection', flush=True)

    # The selected Python shim must not send a healthy host through package setup.
    stubs = root / 'bin'
    stubs.mkdir()
    for name in ('python3', 'apt-get'):
        (stubs / name).write_text('#!/bin/sh\nexit 97\n')
        (stubs / name).chmod(0o755)
    output = run([SRC / 'install.sh', '--no-start'], dict(env, PATH=str(stubs) + ':' + env['PATH']))
    assert 'Using /usr/bin/python3' in output
    output = run([SRC / 'install.sh', '--no-start'], dict(env, OH_MY_USAGE_PYTHON='/missing/python'), success=False)
    assert 'Correct or unset it' in output
    print('PASS: broken PATH shim falls back; invalid explicit Python fails early', flush=True)

    # Importing only the package root used to overlook a missing native binding.
    python = prefix / '.venv/bin/python'
    binding = next((prefix / '.venv').glob('lib/python*/site-packages/cryptography/hazmat/bindings/_rust*.so'))
    binding.rename(binding.with_suffix('.damaged'))
    run([python, '-c', 'import cryptography'], env)
    run([python, '-c', 'from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey'], env, success=False)
    output = run([prefix / 'install.sh', '--no-start'], env)
    assert 'Repairing damaged signing dependencies' in output
    run([python, '-c', 'from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; Ed25519PrivateKey.generate()'], env)
    print('PASS: installed-directory repair detects and replaces corrupted signing bindings', flush=True)

    # Rebuilding must restore the old private environment if its download fails.
    sentinel = prefix / '.venv/preserve-after-failure'
    sentinel.write_text('preserve')
    python.unlink()
    python.symlink_to('/missing/deleted-python')
    (home / '.config/oh-my-usage/inline').write_text('off\n')
    no_packages = dict(env, PIP_FIND_LINKS=str(root / 'empty-wheel-directory'))
    output = run([SRC / 'install.sh', '--no-start'], no_packages, success=False)
    assert 'Python dependency installation failed' in output
    assert sentinel.read_text() == 'preserve'
    assert not list(prefix.glob('.venv-backup-*'))
    run([SRC / 'install.sh', '--no-start'], env)
    assert (home / '.config/oh-my-usage/inline').read_text() == 'off\n'
    print('PASS: failed rebuild rolls back; retry repairs a removed interpreter and keeps preferences', flush=True)

    # No settings/content changes should occur before a permission error is caught.
    before = rc.read_text()
    rc.chmod(0o400)
    try:
        output = run([SRC / 'install.sh', '--no-start'], env, success=False)
        assert 'zsh configuration is not writable' in output
        assert 'Preparing the private Python environment' not in output
        assert rc.read_text() == before
    finally:
        rc.chmod(0o600)
    run(['sudo', 'chown', 'root:root', prefix], env)
    try:
        output = run([SRC / 'install.sh', '--no-start'], env, success=False)
        assert 'Installation directory is not writable' in output
    finally:
        run(['sudo', 'chown', f'{os.getuid()}:{os.getgid()}', prefix], env)
    print('PASS: read-only rc and root-owned install directory fail before dependency changes', flush=True)

    # A refused package-index connection must fail clearly and remain retryable.
    network_env = environment(root / 'network home')
    network_env.pop('PIP_NO_INDEX')
    network_env.pop('PIP_FIND_LINKS')
    network_env['PIP_INDEX_URL'] = 'http://127.0.0.1:9/simple'
    output = run([SRC / 'install.sh', '--no-start'], network_env, success=False)
    assert 'Python dependency installation failed' in output and 'Ready to use' not in output
    network_prefix = Path(network_env['HOME']) / '.local/share/oh-my-usage'
    assert not (network_prefix / '.venv').exists()
    assert not (Path(network_env['HOME']) / '.zshrc').exists()
    network_env.update(PIP_NO_INDEX='1', PIP_FIND_LINKS=WHEELS)
    run([SRC / 'install.sh', '--no-start'], network_env)
    run([network_prefix / 'install.sh', 'uninstall'], network_env)
    print('PASS: unavailable index fails without claiming readiness; retry completes normally', flush=True)

    # Removal must not depend on the damaged environment being executable.
    (prefix / 'python-path').write_text('/missing/private/python\n')
    run([prefix / 'install.sh', 'uninstall'], env)
    assert not prefix.exists()
    assert not (home / '.local/bin/oh-my-usage').exists()
    assert rc.read_text() == '# keep this user configuration\n'
    print('PASS: uninstall works without private Python and restores the user rc', flush=True)

    # Exercise the actual APT lock-wait option while a controlled owner holds it.
    holder_code = ('import fcntl,time; f=open("/var/lib/dpkg/lock-frontend", "w"); '
                   'fcntl.lockf(f, fcntl.LOCK_EX); print("locked", flush=True); time.sleep(3)')
    holder = subprocess.Popen(['sudo', '/usr/bin/python3', '-c', holder_code], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == 'locked'
        run(['sudo', 'apt-get', '-o', 'DPkg::Lock::Timeout=10', 'install', '-y', '--no-install-recommends', 'zsh'], env)
    finally:
        holder.wait(timeout=10)
        holder.stdout.close()
    print('PASS: APT waits for the package lock and succeeds after its owner releases it', flush=True)
