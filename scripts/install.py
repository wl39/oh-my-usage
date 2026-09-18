"""User-local installation. Back up shell config and touch only a marked block."""

import argparse
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


def install(prefix, home, shell=True, mode="direct", dependencies=False):
    if shell and not shutil.which("zsh"):
        raise ValueError("Install zsh for prompt integration, or use --no-shell for CLI-only installation")
    rc = Path(os.environ.get("ZDOTDIR", str(home))) / ".zshrc"
    # Preflight before modifying anything, including an unrelated existing directory.
    without_block(rc.read_text() if rc.exists() else "")
    marker = prefix / ".oh-my-usage-install"
    if prefix.exists() and not marker.is_file():
        raise ValueError(f"Refusing to replace an unowned directory: {prefix}")
    previous = json.loads(marker.read_text()) if marker.exists() else {}
    if previous.get("shell") and str(rc) != previous["rc"]:
        raise ValueError("ZDOTDIR changed; uninstall the previous installation first")
    remove_legacy_profile(previous)
    prefix.mkdir(parents=True, exist_ok=True)
    # A failed dependency download remains a recognized, retryable installation.
    if not marker.exists():
        marker.write_text(json.dumps({"rc": str(rc), "shell": False}))
    for name in ("oh_my_usage", "bin", "zsh"):
        shutil.copytree(ROOT / name, prefix / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # Explicit files keep local notes, previews, and test tools out of installations.
    for name in ("oh-my-usage.plugin.zsh", "install.sh", "README.md", "LICENSE",
                 "scripts/install.py", "requirements.txt", "docs/providers.md", "docs/README.ko.md", "docs/README.zh-CN.md"):
        (prefix / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, prefix / name)
    python = sys.executable
    if dependencies:
        environment = prefix / ".venv"
        if not (environment / "bin/python").exists():
            subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
        python = str(environment / "bin/python")
        subprocess.run([python, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(prefix / "requirements.txt")], check=True)
    (prefix / "python-path").write_text(python + "\n")
    cache = cache_directory(home)
    marker.write_text(json.dumps({"rc": str(rc), "cache": str(cache),
                                  "shell": shell or previous.get("shell", False)}))
    if shell:
        quoted = shlex.quote(str(prefix / "oh-my-usage.plugin.zsh"))
        write_shell(rc, f"{START}\n[[ -r {quoted} ]] && source {quoted}\n{END}\n")
    settings = Path(os.environ.get("OH_MY_USAGE_CONFIG_DIR") or
                    Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "oh-my-usage")
    settings.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write(settings / "source", ("direct" if mode == "direct" else "openusage") + "\n")
    if mode == "direct" and not (settings / "inline").exists():
        atomic_write(settings / "inline", "on\n")
    installed_screen(prefix, shell or previous.get("shell", False))


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
    parser.add_argument("--with-dependencies", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    prefix = args.prefix.expanduser().resolve()
    try:
        if (args.mode != "uninstall" and prefix == ROOT) or prefix in ROOT.parents or prefix == Path.home():
            raise ValueError("Choose a dedicated installation directory")
        if args.mode == "uninstall":
            uninstall(prefix)
        else:
            install(prefix, Path.home(), not args.no_shell, args.mode, args.with_dependencies)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"oh-my-usage: {error}\n")


if __name__ == "__main__":
    main()
