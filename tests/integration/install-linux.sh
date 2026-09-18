#!/bin/sh
# Run inside a disposable, stock Ubuntu container, with this repo mounted at /src.
set -eu
cd /src
if [ "${1:-}" = --as-user ]; then
  # Stock containers lack sudo/users. Prepare only those, leaving Python/zsh absent.
  apt-get update
  apt-get install -y --no-install-recommends sudo
  useradd -m -s /bin/sh usageinstaller
  echo 'usageinstaller ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/usageinstaller
  chmod 440 /etc/sudoers.d/usageinstaller
  exec su -s /bin/sh usageinstaller -c 'sh /src/tests/integration/install-linux.sh'
fi
export HOME=/tmp/omu-install-home
export ZDOTDIR="$HOME"
export XDG_CONFIG_HOME="$HOME/.config" XDG_CACHE_HOME="$HOME/.cache"
unset OH_MY_USAGE_PYTHON OH_MY_USAGE_SOURCE OH_MY_USAGE_CONFIG_DIR OH_MY_USAGE_CACHE_DIR
mkdir -p "$HOME"
# A stock image should have none of the prerequisites; don't hide missing packages.
if command -v python3 >/dev/null 2>&1 || command -v zsh >/dev/null 2>&1; then
  echo 'Use a stock Ubuntu image without Python or zsh for this test.' >&2
  exit 1
fi
mkdir -p /tmp/omu-forbidden
for command in brew open; do
  cat > "/tmp/omu-forbidden/$command" <<'STUB'
#!/bin/sh
echo "Forbidden OpenUsage install/launch: $0" >&2
touch /tmp/omu-openusage-invoked
exit 99
STUB
  chmod +x "/tmp/omu-forbidden/$command"
done
export PATH="/tmp/omu-forbidden:$PATH"
# Exactly the user's command: no prerequisite setup, no extra install options.
./install.sh
prefix="$HOME/.local/share/oh-my-usage"
"$prefix/.venv/bin/python" -m pip --version
"$prefix/.venv/bin/python" -c 'import cryptography'
test "$(cat "$HOME/.config/oh-my-usage/source")" = direct
test -f "$HOME/.cache/oh-my-usage/usage.json"
test "$(stat -c %u "$prefix/.venv")" = "$(id -u)"
"$HOME/.local/bin/oh-my-usage" providers --json > /tmp/omu-providers.json
python3 - <<'PY'
import json
from pathlib import Path
providers = json.loads(Path('/tmp/omu-providers.json').read_text())
assert len(providers) == 11, providers
PY
# Reproduce the reported Ubuntu failure without losing the installation marker.
"$prefix/.venv/bin/python" -m pip uninstall -y pip
touch "$prefix/.venv/preserve-me"
echo off > "$HOME/.config/oh-my-usage/inline"
echo '# existing shell customization' >> "$HOME/.zshrc"
./install.sh
"$prefix/.venv/bin/python" -m pip --version
test -f "$prefix/.venv/preserve-me"
test "$(cat "$HOME/.config/oh-my-usage/inline")" = off
# Legacy entry points must also stay independent on Linux.
./install-full.sh --no-start
./install-existing.sh --no-start
test ! -e /tmp/omu-openusage-invoked
python3 - <<'PY'
import os
from pathlib import Path
rc = Path(os.environ['HOME']) / '.zshrc'
assert rc.read_text().count('# >>> oh-my-usage >>>') == 1
assert '# existing shell customization' in rc.read_text()
PY
zsh -di -c 'whence -w oh-my-usage; oh-my-usage --version'
# PTY is needed to exercise automatic entry into an immediately usable shell.
python3 /src/tests/integration/install-pty.py
"$prefix/install.sh" uninstall
test ! -e "$prefix"
test ! -e "$HOME/.local/bin/oh-my-usage"
echo 'PASS: pristine Ubuntu, pip repair, repeat install, Linux legacy options, interactive shell, uninstall'
