# Read one small preference with shell builtins, including changes from other tabs.
_oh_my_usage_inline_load() {
  local saved=''
  if [[ -r "$_OH_MY_USAGE_CONFIG/inline" ]]; then
    IFS= read -r saved < "$_OH_MY_USAGE_CONFIG/inline"
  fi
  typeset -g _OH_MY_USAGE_INLINE_MODE=off _OH_MY_USAGE_INLINE_ORIGIN=default
  if [[ ${OH_MY_USAGE_INLINE:-} == (on|off) ]]; then
    _OH_MY_USAGE_INLINE_MODE=$OH_MY_USAGE_INLINE
    _OH_MY_USAGE_INLINE_ORIGIN=environment
  fi
  if [[ $saved == (on|off) ]]; then
    _OH_MY_USAGE_INLINE_MODE=$saved
    _OH_MY_USAGE_INLINE_ORIGIN=saved
  fi
  if [[ ${_OH_MY_USAGE_INLINE_SESSION:-} == (on|off) ]]; then
    _OH_MY_USAGE_INLINE_MODE=$_OH_MY_USAGE_INLINE_SESSION
    _OH_MY_USAGE_INLINE_ORIGIN=session
  fi
}
