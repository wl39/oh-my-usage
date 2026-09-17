# Run once after ZLE starts reading, when themes have finished the first prompt.
# /dev/null is immediately ready: no child process, sleep, or recurring timer.
_oh_my_usage_startup_schedule() {
  [[ ${OH_MY_USAGE_DISPLAY:-status} == off ]] && return 0
  [[ ${_OH_MY_USAGE_INLINE_MODE:-off} == on ]] || _oh_my_usage_status_supported || return 0
  zmodload zsh/zle || return 1
  exec {_OH_MY_USAGE_STARTUP_FD}< /dev/null || return
  zle -N _oh_my_usage_startup_ready
  zle -F -w "$_OH_MY_USAGE_STARTUP_FD" _oh_my_usage_startup_ready
}

_oh_my_usage_startup_close() {
  [[ -n ${_OH_MY_USAGE_STARTUP_FD:-} ]] || return 0
  zle -F "$_OH_MY_USAGE_STARTUP_FD"
  exec {_OH_MY_USAGE_STARTUP_FD}<&-
  unset _OH_MY_USAGE_STARTUP_FD
  zle -D _oh_my_usage_startup_ready
}

_oh_my_usage_startup_ready() {
  _oh_my_usage_startup_close
  # Instant-prompt themes may redirect stdout throughout the first precmd.
  _oh_my_usage_precmd
  if [[ ${_OH_MY_USAGE_INLINE_ACTIVE:-0} == 1 ]]; then
    _OH_MY_USAGE_INLINE_VISIBLE=0
    _oh_my_usage_inline_update "$options[promptsubst]"
    # A theme may have rebuilt the prompt after our line-init hook.
    zle .reset-prompt
    zle -R
  fi
  return 0
}
