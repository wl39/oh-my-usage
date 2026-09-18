"""User-local installation. Back up shell config and touch only a marked block."""

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from oh_my_usage.terminal import installed_screen
from oh_my_usage.paths import cache_directory
from oh_my_usage.files import atomic_write

ROOT = Path(__file__).resolve().parent.parent
START = "# >>> oh-my-usage >>>"
END = "# <<< oh-my-usage <<<"
PROFILE_GUID = "3E42E713-38CF-4B51-B58D-50306D69E148"
LAUNCHER_MARKER = "# oh-my-usage managed launcher"
CRYPTO_CHECK = ("from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; "
                "key = Ed25519PrivateKey.generate(); data = b'oh-my-usage-install-check'; "
                "key.public_key().verify(key.sign(data), data)")


def runtime_environment():
    env = dict(os.environ)
    for name in ("PYTHONHOME", "PYTHONUSERBASE", "PIP_TARGET", "PIP_PREFIX"):
        env.pop(name, None)
    env.update(PYTHONNOUSERSITE="1", PIP_USER="0")
    # Keep index, proxy and certificate settings for managed/corporate networks.
    return env


def run_step(command, label, timeout=180):
    try:
        subprocess.run(command, check=True, timeout=timeout, env=runtime_environment())
    except subprocess.TimeoutExpired:
        raise ValueError(f"{label} timed out after {timeout}s. Check the network, proxy and package index, then rerun ./install.sh.") from None
    except subprocess.CalledProcessError:
        raise ValueError(f"{label} failed. See the command output above. For pip, check network/certificate/index settings and remove any global target override in pip.conf. Rerun ./install.sh after correcting it.") from None


def python_check(python, *args):
    try:
        return subprocess.run([str(python), *args], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=30,
                              env=runtime_environment()).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def prepare_runtime(prefix):
    """Repair pipless venvs; replace broken ones without touching system Python."""
    environment = prefix / ".venv"
    if environment.is_symlink() or (environment.exists() and not environment.is_dir()):
        raise ValueError(f"Refusing to replace a non-directory or symlink: {environment}")
    python = environment / "bin/python"
    healthy = python_check(python, "-c",
                           "import sys, ssl, sqlite3; from pathlib import Path; "
                           "sys.exit(not (sys.version_info >= (3, 9) and "
                           "sys.prefix != sys.base_prefix and "
                           "Path(sys.prefix).resolve() == Path(sys.argv[1]).resolve()))",
                           str(environment))
    if healthy and not python_check(python, "-m", "pip", "--version"):
        print("Repairing pip in the existing private Python environment...", flush=True)
        healthy = python_check(python, "-m", "ensurepip", "--upgrade")
        healthy = healthy and python_check(python, "-m", "pip", "--version")
    backup = None
    rebuilding = not healthy
    if rebuilding and environment.exists():
        print("Rebuilding the incomplete private Python environment...", flush=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = environment.with_name(".venv-backup-" + stamp)
        environment.rename(backup)
    try:
        if rebuilding:
            # Create at its final path: venv scripts contain absolute paths.
            base_python = getattr(sys, "_base_executable", sys.executable)
            run_step([base_python, "-m", "venv", str(environment)], "Private Python environment creation")
        pip_command = [str(python), "-m", "pip", "install", "--disable-pip-version-check",
                       "--no-user", "--prefix", str(environment), "--timeout", "15", "--retries", "2",
                       "-r", str(prefix / "requirements.txt")]
        run_step(pip_command, "Python dependency installation")
        if not python_check(python, "-c", CRYPTO_CHECK):
            print("Repairing damaged signing dependencies in the private environment...", flush=True)
            run_step([*pip_command, "--force-reinstall"], "Signing dependency repair")
            if not python_check(python, "-c", CRYPTO_CHECK):
                raise ValueError("Signing dependencies are still unusable after repair. Check Python/CPU compatibility and pip configuration; installation has not completed.")
    except BaseException:
        if rebuilding:
            if environment.exists():
                shutil.rmtree(environment)
            if backup:
                backup.rename(environment)
        raise
    if backup:
        shutil.rmtree(backup)
    return str(python)


def launcher_text(prefix):
    return f'#!/bin/sh\n{LAUNCHER_MARKER}\nexec {shlex.quote(str(prefix / "bin/oh-my-usage"))} "$@"\n'


def first_read(prefix):
    print("Discovering installed services and reading available usage...", flush=True)
    try:
        result = subprocess.run([str(prefix / "bin/oh-my-usage"), "start"],
                                env=dict(os.environ, OH_MY_USAGE_SOURCE="direct"), timeout=90)
        if result.returncode == 0:
            return
    except subprocess.TimeoutExpired:
        pass
    print("Installation is complete. Some usage could not be read yet; run oh-my-usage providers or doctor.")


def shell_config(home):
    """Ask zsh where it reads .zshrc after processing the user's .zshenv."""
    try:
        result = subprocess.run(["zsh", "-c",
            r'''print -rn -- $'\0oh-my-usage-zdotdir\0'"${ZDOTDIR-$HOME}"$'\0'"${options[rcs]}"$'\0' '''.strip()],
            env=dict(os.environ, HOME=str(home)), capture_output=True, text=True, timeout=5)
        fields = result.stdout.rsplit("\0oh-my-usage-zdotdir\0", 1)
        if result.returncode != 0 or len(fields) != 2:
            raise ValueError("zsh did not report its configuration directory")
        folder, rcs = fields[1].split("\0")[:2]
        if not folder or not Path(folder).is_absolute():
            raise ValueError("ZDOTDIR must be an absolute path")
        if rcs != "on":
            raise ValueError("RCS is disabled, so zsh will not load .zshrc")
        return Path(folder) / ".zshrc"
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"Cannot register zsh integration: {error}. Check .zshenv or use --no-shell for the CLI.") from None


def check_writable(path, label, directory=False):
    target = path.resolve()
    if target.exists():
        if target.is_dir() != directory:
            raise ValueError(f"{label} has the wrong file type: {path}")
        if not os.access(target, os.W_OK | (os.X_OK if directory else 0)):
            raise ValueError(f"{label} is not writable by this user: {path}. Check its ownership/permissions; do not run the whole installer with sudo.")
    parent = target if target.is_dir() else target.parent
    while not parent.exists():
        parent = parent.parent
    if not parent.is_dir() or not os.access(parent, os.W_OK | os.X_OK):
        raise ValueError(f"Cannot write {label} under {parent}. Check ownership/permissions or choose another --prefix.")


@contextmanager
def installation_lock(home):
    folder = home / ".local/share"
    check_writable(folder, "Installation lock directory", directory=True)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ".oh-my-usage-install.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another oh-my-usage installation or removal is running. Wait for it to finish, then retry.") from None
        yield
    finally:
        os.close(fd)


def without_block(text, start=START, end=END):
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == start]
    ends = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == end]
    if not starts and not ends:
        return text
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError("Malformed oh-my-usage block in shell config; fix the markers first")
    return "".join(lines[:starts[0]] + lines[ends[0] + 1:])


def write_shell(rc, block, start=START, end=END):
    # Follow a dotfile symlink and preserve the original file's permissions.
    target = rc.resolve()
    old = target.read_text() if target.exists() else ""
    text = without_block(old, start, end)
    if block:
        text += ("\n" if text and not text.endswith("\n") else "") + block
    if text == old:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(target, target.with_name(target.name + ".oh-my-usage-backup-" + stamp))
    target.write_text(text)


def remove_legacy_profile(manifest):
    """Only remove the dedicated profile owned by the 0.1 installer."""
    if not manifest.get("iterm"):
        return
    p = Path(manifest["profile"])
    if p.exists():
        data = json.loads(p.read_text())
        profiles = data.get("Profiles", [])
        if len(profiles) == 1 and profiles[0].get("Guid") == PROFILE_GUID:
            p.unlink()


def install(prefix, home, shell=True, mode="direct", dependencies=False, start=False, activate=False):
    if shell and not shutil.which("zsh"):
        raise ValueError("Install zsh for prompt integration, or use --no-shell for CLI-only installation")
    print("Checking installation paths and shell configuration...", flush=True)
    marker = prefix / ".oh-my-usage-install"
    if prefix.exists() and not marker.is_file():
        raise ValueError(f"Refusing to replace an unowned directory: {prefix}")
    previous = json.loads(marker.read_text()) if marker.exists() else {}
    if not isinstance(previous, dict) or (previous.get("shell") and not isinstance(previous.get("rc"), str)):
        raise ValueError(f"Invalid installation record: {marker}. Preserve this directory and inspect the record before reinstalling.")
    rc = shell_config(home) if shell else Path(previous.get("rc", str(home / ".zshrc")))
    if shell:
        without_block(rc.read_text() if rc.exists() else "")
    if previous.get("shell") and str(rc) != previous["rc"]:
        raise ValueError("ZDOTDIR changed; uninstall the previous installation first")
    launcher = home / ".local/bin/oh-my-usage"
    if launcher.is_symlink() or (launcher.exists() and
                                (not launcher.is_file() or launcher.read_text() != launcher_text(prefix))):
        raise ValueError(f"Refusing to replace an unrelated command: {launcher}")
    settings = Path(os.environ.get("OH_MY_USAGE_CONFIG_DIR") or
                    Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "oh-my-usage").expanduser()
    cache = cache_directory(home)
    if not settings.is_absolute() or not cache.is_absolute():
        raise ValueError("Settings and cache directories must be absolute paths (or ~/ paths), so commands work from any folder.")
    for path, label in ((prefix, "Installation directory"), (settings, "Settings directory"),
                        (cache, "Cache directory"), (launcher.parent, "Command directory")):
        check_writable(path, label, directory=True)
    check_writable(launcher, "Command launcher")
    if shell:
        check_writable(rc, "zsh configuration")
    remove_legacy_profile(previous)
    prefix.mkdir(parents=True, exist_ok=True)
    # A failed dependency download remains a recognized, retryable installation.
    if not marker.exists():
        atomic_write(marker, json.dumps({"rc": str(rc), "shell": False}))
    if prefix.resolve() != ROOT.resolve():
        for name in ("oh_my_usage", "bin", "zsh"):
            shutil.copytree(ROOT / name, prefix / name, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        # Explicit files keep local notes, previews, and test tools out of installations.
        for name in ("oh-my-usage.plugin.zsh", "install.sh", "README.md", "LICENSE",
                     "scripts/install.py", "scripts/bootstrap.sh", "requirements.txt", "docs/installation.md", "docs/providers.md", "docs/README.ko.md", "docs/README.zh-CN.md"):
            (prefix / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, prefix / name)
    python = sys.executable
    if dependencies:
        print("Preparing the private Python environment and dependencies...", flush=True)
        python = prepare_runtime(prefix)
    atomic_write(prefix / "python-path", python + "\n")
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(launcher_text(prefix))
    launcher.chmod(0o755)
    atomic_write(marker, json.dumps({"rc": str(rc), "cache": str(cache), "launcher": str(launcher),
                                  "shell": shell or previous.get("shell", False)}))
    if shell:
        quoted = shlex.quote(str(prefix / "oh-my-usage.plugin.zsh"))
        write_shell(rc, f'{START}\nexport PATH={shlex.quote(str(launcher.parent))}:"$PATH"\n'
                    f"[[ -r {quoted} ]] && source {quoted}\n{END}\n")
    settings.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write(settings / "source", ("direct" if mode == "direct" else "openusage") + "\n")
    if mode == "direct" and not (settings / "inline").exists():
        atomic_write(settings / "inline", "on\n")
    if start and mode == "direct":
        first_read(prefix)
    installed_screen(prefix, shell or previous.get("shell", False), activate=activate)


def uninstall(prefix):
    marker = prefix / ".oh-my-usage-install"
    legacy = not marker.is_file() and (prefix / ".ouiterm-install").is_file()
    if legacy:
        marker = prefix / ".ouiterm-install"
    if not marker.is_file():
        raise ValueError(f"No oh-my-usage installation at {prefix}")
    manifest = json.loads(marker.read_text())
    if manifest["shell"]:
        if legacy:
            write_shell(Path(manifest["rc"]), "", "# >>> OUIterm >>>", "# <<< OUIterm <<<")
        else:
            write_shell(Path(manifest["rc"]), "")
    remove_legacy_profile(manifest)
    if manifest.get("launcher"):
        launcher = Path(manifest["launcher"])
        if not launcher.is_symlink() and launcher.is_file() and launcher.read_text() == launcher_text(prefix):
            launcher.unlink()
    if manifest.get("cache"):
        cache = Path(manifest["cache"])
        # Custom cache directories may contain unrelated files; only remove ours.
        for name in ("display", "usage.json", "usage-source", "lock"):
            (cache / name).unlink(missing_ok=True)
        try:
            cache.rmdir()
        except OSError:
            pass
    shutil.rmtree(prefix)
    name, unload, variable = (("OUIterm", "ouiterm_unload", "ouiterm") if legacy else
                              ("oh-my-usage", "oh-my-usage-unload", "oh_my_usage"))
    print(f"Removed {name}. Open a new shell, or run {unload} in this shell.")
    print(f"Remove the Interpolated String using \\(user.{variable}) from your status bar, if added.")
    if not legacy:
        print("Saved preferences are kept for reinstallation.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("direct", "full", "existing", "uninstall"))
    default_prefix = ROOT if (ROOT / ".oh-my-usage-install").is_file() else Path.home() / ".local/share/oh-my-usage"
    parser.add_argument("--prefix", type=Path, default=default_prefix)
    parser.add_argument("--no-profile", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-shell", action="store_true")
    parser.add_argument("--no-start", action="store_true", help="Skip initial usage lookup and interactive shell")
    parser.add_argument("--activate", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--with-dependencies", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    prefix = args.prefix.expanduser().resolve()
    try:
        if (args.mode != "uninstall" and prefix == ROOT and not (ROOT / ".oh-my-usage-install").is_file()) or prefix in ROOT.parents or prefix == Path.home():
            raise ValueError("Choose a dedicated installation directory")
        with installation_lock(Path.home()):
            if args.mode == "uninstall":
                uninstall(prefix)
            else:
                install(prefix, Path.home(), not args.no_shell, args.mode, args.with_dependencies,
                        start=not args.no_start, activate=args.activate)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"oh-my-usage: {error}\nFix the reported problem and rerun ./install.sh; incomplete environments are repaired automatically.\n")


if __name__ == "__main__":
    main()
