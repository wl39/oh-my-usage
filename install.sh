#!/bin/sh
# One-command independent setup. Linux never installs or launches OpenUsage.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mode=direct
case ${1:-} in direct|full|existing|uninstall) mode=$1; shift ;; esac
case ${1:-} in --help|-h)
  echo 'Usage: ./install.sh [direct|full|existing|uninstall] [--no-shell] [--no-start] [--prefix PATH]'
  echo 'Installs missing prerequisites, repairs the private environment, discovers services and opens a ready zsh.'
  echo 'Linux always uses direct collection. full/existing opt into OpenUsage only on macOS.'
  echo '--no-start skips the first usage read and automatic interactive shell (for unattended installation).'
  exit 0 ;;
esac
# Validate all options before downloading packages or changing the machine.
with_shell=yes start=yes next_prefix=no
prefix="$HOME/.local/share/oh-my-usage"
[ ! -f "$root/.oh-my-usage-install" ] || prefix=$root
for argument in "$@"; do
  if [ "$next_prefix" = yes ]; then
    [ -n "$argument" ] || { echo '--prefix needs a path' >&2; exit 2; }
    prefix=$argument; next_prefix=no; continue
  fi
  case $argument in
    --no-shell) with_shell=no ;;
    --no-profile) : ;;
    --no-start) start=no ;;
    --prefix) next_prefix=yes ;;
    *) echo "Unknown option: $argument" >&2; exit 2 ;;
  esac
done
[ "$next_prefix" = no ] || { echo '--prefix needs a path' >&2; exit 2; }
platform=$(uname -s)
case $platform in Darwin|Linux) ;; *) echo 'Supported installer hosts: macOS and Linux.' >&2; exit 1 ;; esac
if [ "$platform" = Linux ] && { [ "$mode" = full ] || [ "$mode" = existing ]; }; then
  echo 'Linux: using independent collection; OpenUsage is not needed.'
  mode=direct
fi
python=${OH_MY_USAGE_PYTHON:-python3}
export PYTHONDONTWRITEBYTECODE=1
if [ "$mode" = uninstall ]; then
  if [ -r "$prefix/python-path" ] && [ -z "${OH_MY_USAGE_PYTHON:-}" ]; then IFS= read -r python < "$prefix/python-path"; fi
  PYTHONPATH="$root" exec "$python" "$root/scripts/install.py" uninstall "$@"
fi
# Do not install into root's home merely because the user prefixed the command with sudo.
if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != root ]; then
  echo 'Run ./install.sh as your own user. It invokes sudo only for missing system packages.' >&2
  exit 1
fi
if [ -e "$prefix" ] && [ ! -f "$prefix/.oh-my-usage-install" ]; then
  echo "Refusing to replace an unowned directory: $prefix" >&2; exit 1
fi
. "$root/scripts/bootstrap.sh"
omu_bootstrap
app=''
if [ "$mode" = full ] || [ "$mode" = existing ]; then
  app_dir=${OH_MY_USAGE_APP_DIR:-/Applications}
  app="$app_dir/OpenUsage.app"
  if [ ! -d "$app" ] && [ -z "${OH_MY_USAGE_APP_DIR:-}" ] && [ -d "$HOME/Applications/OpenUsage.app" ]; then app="$HOME/Applications/OpenUsage.app"; fi
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
activate=no
if [ "$with_shell" = yes ] && [ "$start" = yes ] && [ -t 0 ] && [ -t 1 ]; then activate=yes; fi
if [ "$mode" = direct ]; then set -- "$@" --with-dependencies; fi
if [ "$activate" = yes ]; then set -- "$@" --activate; fi
PYTHONPATH="$root" "$python" "$root/scripts/install.py" "$mode" "$@"
if [ -n "$app" ]; then open "$app"; fi
if [ "$activate" = yes ]; then
  # An executable cannot alter its parent shell. Enter a configured shell now,
  # retaining the working directory; future terminals load the saved integration.
  exec zsh -i
fi
