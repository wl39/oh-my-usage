#!/bin/zsh
# Install prerequisites only when requested; the reader has no pip dependencies.
emulate -LR zsh
set -eu
typeset root=${0:A:h}
typeset mode=${1:-}
case $mode in
  full|existing|uninstall) shift ;;
  *) print 'Usage: ./install.sh full|existing|uninstall [--no-shell] [--prefix PATH]'; exit 2 ;;
esac
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  print 'Options: --no-shell --prefix PATH'
  exit 0
fi
typeset -a forwarded=("$@")
typeset prefix="$HOME/.local/share/oh-my-usage"
[[ -f "$root/.oh-my-usage-install" ]] && prefix=$root
while (( $# )); do
  case $1 in
    --no-shell|--no-profile) shift ;;
    --prefix) (( $# >= 2 )) || { print -u2 '--prefix needs a path'; exit 2; }; prefix=$2; shift 2 ;;
    *) print -u2 "Unknown option: $1"; exit 2 ;;
  esac
done
[[ $(uname -s) == Darwin ]] || { print -u2 'oh-my-usage requires macOS (OpenUsage is a macOS app).'; exit 1; }

typeset app=''
typeset -a candidates=(/Applications/OpenUsage.app "$HOME/Applications/OpenUsage.app")
[[ -n ${OH_MY_USAGE_APP_DIR:-} ]] && candidates=("$OH_MY_USAGE_APP_DIR/OpenUsage.app")
for candidate in "${candidates[@]}"; do
  [[ -d $candidate ]] && app=$candidate && break
done
typeset brew_cmd=${commands[brew]:-}
[[ -z $brew_cmd && -x /opt/homebrew/bin/brew ]] && brew_cmd=/opt/homebrew/bin/brew
[[ -z $brew_cmd && -x /usr/local/bin/brew ]] && brew_cmd=/usr/local/bin/brew

need_brew() {
  [[ -n $brew_cmd ]] && return 0
  print -u2 'Install Homebrew from https://brew.sh first, then rerun this command.'
  return 1
}

if [[ $mode == existing && -z $app ]]; then
  print -u2 'OpenUsage was not found. Run ./install.sh full to install it.'
  exit 1
fi
if [[ $mode == full && -z $app ]]; then
  typeset os_version=$(sw_vers -productVersion)
  (( ${os_version%%.*} >= 15 )) || { print -u2 'OpenUsage requires macOS 15 or later.'; exit 1; }
  need_brew
  typeset app_dir=${OH_MY_USAGE_APP_DIR:-/Applications}
  "$brew_cmd" install --cask --appdir "$app_dir" openusage
  app="$app_dir/OpenUsage.app"
  [[ -d $app ]] || { print -u2 'OpenUsage installation did not finish.'; exit 1; }
fi

typeset python=${OH_MY_USAGE_PYTHON:-${commands[python3]:-}}
if [[ $mode == uninstall && -r "$prefix/python-path" && -z ${OH_MY_USAGE_PYTHON:-} ]]; then
  python=$(<"$prefix/python-path")
fi
if [[ -z $python ]] || ! "$python" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
  [[ $mode != uninstall ]] || { print -u2 'Python 3.9+ is needed for uninstall.'; exit 1; }
  need_brew
  "$brew_cmd" install python
  python="$("$brew_cmd" --prefix)/bin/python3"
fi
export PYTHONDONTWRITEBYTECODE=1
"$python" "$root/scripts/install.py" "$mode" "${forwarded[@]}"
if [[ $mode != uninstall ]]; then
  open "$app"
fi
