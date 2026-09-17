# One pipe per pending read. ZLE wakes on completion; no polling or resident worker.
_oh_my_usage_async_refresh() {
  [[ -n ${_OH_MY_USAGE_ASYNC_FD:-} ]] && return 0
  exec {_OH_MY_USAGE_ASYNC_FD}< <(
    _oh_my_usage_refresh "$1" < /dev/null > /dev/null 2>/dev/null
  ) || return
  zle -N _oh_my_usage_async_ready
  zle -F -w "$_OH_MY_USAGE_ASYNC_FD" _oh_my_usage_async_ready
}

_oh_my_usage_async_close() {
  [[ -n ${_OH_MY_USAGE_ASYNC_FD:-} ]] || return 0
  zle -F "$_OH_MY_USAGE_ASYNC_FD"
  exec {_OH_MY_USAGE_ASYNC_FD}<&-
  unset _OH_MY_USAGE_ASYNC_FD
  zle -D _oh_my_usage_async_ready
}

_oh_my_usage_async_ready() {
  # EOF is the completion signal, including failed reads. Close before redrawing.
  _oh_my_usage_async_close
  [[ ${OH_MY_USAGE_DISPLAY:-status} == off ]] && return 0
  _oh_my_usage_publish
  if [[ ${_OH_MY_USAGE_INLINE_ACTIVE:-0} == 1 ]]; then
    _OH_MY_USAGE_INLINE_VISIBLE=0
    _oh_my_usage_inline_redraw
    zle -R
  fi
  return 0
}
