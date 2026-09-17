# iTerm2 status-bar transport, with an optional empty-input right prompt.
[[ -o interactive ]] || return 0
if (( ${+_OH_MY_USAGE_LOADED} )); then
  [[ ${_OH_MY_USAGE_VERSION:-} == 0.6.0 ]] && return 0
  # Restore the theme before replacing a previously loaded version.
  (( ${+functions[oh-my-usage-unload]} )) && oh-my-usage-unload
fi
typeset -g _OH_MY_USAGE_LOADED=1 _OH_MY_USAGE_VERSION=0.6.0
typeset -g _OH_MY_USAGE_ROOT=${${(%):-%x}:A:h}
typeset -g _OH_MY_USAGE_CACHE=${OH_MY_USAGE_CACHE_DIR:-$HOME/Library/Caches/oh-my-usage}
typeset -g _OH_MY_USAGE_CONFIG=${OH_MY_USAGE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/oh-my-usage}
typeset -g _OH_MY_USAGE_NEXT=0 OH_MY_USAGE_TEXT=''
typeset -g _OH_MY_USAGE_ENCODED='?'
zmodload zsh/datetime
autoload -Uz add-zsh-hook

source "$_OH_MY_USAGE_ROOT/zsh/config.zsh"
source "$_OH_MY_USAGE_ROOT/zsh/inline.zsh"
source "$_OH_MY_USAGE_ROOT/zsh/async.zsh"

oh-my-usage() {
  if [[ ${1:-} == inline ]]; then
    shift
    _oh_my_usage_inline_control "$@"
  else
    "$_OH_MY_USAGE_ROOT/bin/oh-my-usage" "$@" || return $?
    if [[ ${1:-} == start ]]; then
      typeset -g OH_MY_USAGE_DISPLAY=status
      _oh_my_usage_inline_sync
      _oh_my_usage_publish
    fi
  fi
}

_oh_my_usage_status_supported() {
  [[ ${TERM_PROGRAM:-} == iTerm.app && -z ${TMUX:-} && -z ${STY:-} ]]
}

_oh_my_usage_emit() {
  [[ -t 1 ]] && _oh_my_usage_status_supported || return 0
  [[ $1 == *[^A-Za-z0-9+/=]* ]] && return 0
  [[ $_OH_MY_USAGE_ENCODED == "$1" ]] && return 0
  printf '\e]1337;SetUserVar=oh_my_usage=%s\a' "$1"
  _OH_MY_USAGE_ENCODED=$1
}

_oh_my_usage_publish() {
  local stamp text encoded
  [[ -r "$_OH_MY_USAGE_CACHE/display" ]] || return 0
  { IFS= read -r stamp; IFS= read -r text; IFS= read -r encoded; } < "$_OH_MY_USAGE_CACHE/display"
  OH_MY_USAGE_TEXT=$text
  _oh_my_usage_emit "$encoded"
}

_oh_my_usage_refresh() {
  oh-my-usage show --interval "$1" > /dev/null || return 0
  # Publish immediately after the one-shot read, including the first cold start.
  _oh_my_usage_publish
}

_oh_my_usage_precmd() {
  emulate -L zsh
  _oh_my_usage_inline_sync
  [[ -t 1 ]] || return 0
  if [[ ${OH_MY_USAGE_DISPLAY:-status} == off ]]; then
    OH_MY_USAGE_TEXT=''
    _oh_my_usage_emit ''
    return 0
  fi
  # SSH clients need only ZLE. iTerm2's OSC transport is independent of it.
  [[ $_OH_MY_USAGE_INLINE_MODE == on ]] || _oh_my_usage_status_supported || return 0
  local stamp=0 interval=${OH_MY_USAGE_INTERVAL:-30} text encoded key='auto|auto'
  [[ $interval == <-> ]] || interval=30
  (( interval < 5 )) && interval=5
  if [[ -r "$_OH_MY_USAGE_CACHE/display" ]]; then
    { IFS= read -r stamp; IFS= read -r text; IFS= read -r encoded
      IFS= read -r key || key='auto|auto'
    } < "$_OH_MY_USAGE_CACHE/display"
    _oh_my_usage_publish
  fi
  [[ $stamp == <-> ]] || stamp=0
  _oh_my_usage_view_load
  if [[ $key != "$_OH_MY_USAGE_VIEW_KEY" ]]; then
    stamp=0
    _OH_MY_USAGE_NEXT=0
  fi
  if (( (EPOCHSECONDS - stamp >= interval || EPOCHSECONDS < stamp) && EPOCHSECONDS >= _OH_MY_USAGE_NEXT )); then
    _OH_MY_USAGE_NEXT=$(( EPOCHSECONDS + interval ))
    if [[ $_OH_MY_USAGE_INLINE_MODE == on ]]; then
      _oh_my_usage_async_refresh "$interval"
    else
      (_oh_my_usage_refresh "$interval" < /dev/null 2>/dev/null) &!
    fi
  fi
  return 0
}

oh-my-usage-unload() {
  add-zsh-hook -d precmd _oh_my_usage_precmd
  _oh_my_usage_async_close
  _oh_my_usage_inline_disable
  _oh_my_usage_emit ''
  unset _OH_MY_USAGE_LOADED _OH_MY_USAGE_VERSION _OH_MY_USAGE_ENCODED OH_MY_USAGE_TEXT
  unset _OH_MY_USAGE_INLINE_SESSION _OH_MY_USAGE_INLINE_MODE _OH_MY_USAGE_INLINE_ORIGIN
}

add-zsh-hook precmd _oh_my_usage_precmd
_oh_my_usage_inline_sync
