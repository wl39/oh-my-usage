#!/bin/sh
# Independent macOS/Linux installation; OpenUsage integration is explicitly optional.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mode=direct
case ${1:-} in direct|full|existing|uninstall) mode=$1; shift ;; esac
case ${1:-} in --help|-h)
  echo 'Usage: ./install.sh [direct|full|existing|uninstall] [--no-shell] [--prefix PATH]'
  echo 'Default: independent macOS/Linux install. full/existing opt into OpenUsage (macOS).'
  exit 0 ;;
esac
python=${OH_MY_USAGE_PYTHON:-python3}
if [ "$mode" = uninstall ] && [ -z "${OH_MY_USAGE_PYTHON:-}" ]; then
  prefix="$HOME/.local/share/oh-my-usage"
  [ ! -f "$root/.oh-my-usage-install" ] || prefix=$root
  next_prefix=no
  for argument in "$@"; do
    if [ "$next_prefix" = yes ]; then prefix=$argument; next_prefix=no; fi
    [ "$argument" != --prefix ] || next_prefix=yes
  done
  if [ -r "$prefix/python-path" ]; then IFS= read -r python < "$prefix/python-path"; fi
fi
if ! "$python" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
  echo 'Install Python 3.9+ first (Linux: python3 and python3-venv; macOS: brew install python).' >&2
  exit 1
fi
app=''
if [ "$mode" = full ] || [ "$mode" = existing ]; then
  [ "$(uname -s)" = Darwin ] || { echo 'OpenUsage mode requires macOS; use ./install.sh for independent Linux support.' >&2; exit 1; }
  app_dir=${OH_MY_USAGE_APP_DIR:-/Applications}
  app="$app_dir/OpenUsage.app"
  if [ ! -d "$app" ] && [ -z "${OH_MY_USAGE_APP_DIR:-}" ] && [ -d "$HOME/Applications/OpenUsage.app" ]; then
    app="$HOME/Applications/OpenUsage.app"
  fi
  if [ ! -d "$app" ]; then
    [ "$mode" = full ] || { echo 'OpenUsage was not found; use ./install-full.sh or independent ./install.sh.' >&2; exit 1; }
    version=$(sw_vers -productVersion)
    [ "${version%%.*}" -ge 15 ] || { echo 'OpenUsage requires macOS 15 or later.' >&2; exit 1; }
    brew_cmd=$(command -v brew || true)
    [ -n "$brew_cmd" ] || { echo 'Install Homebrew from https://brew.sh first.' >&2; exit 1; }
    "$brew_cmd" install --cask --appdir "$app_dir" openusage
    [ -d "$app" ] || { echo 'OpenUsage installation did not finish.' >&2; exit 1; }
  fi
fi
export PYTHONDONTWRITEBYTECODE=1
if [ "$mode" = direct ]; then
  PYTHONPATH="$root" "$python" "$root/scripts/install.py" "$mode" --with-dependencies "$@"
else
  PYTHONPATH="$root" "$python" "$root/scripts/install.py" "$mode" "$@"
fi
if [ -n "$app" ]; then open "$app"; fi
