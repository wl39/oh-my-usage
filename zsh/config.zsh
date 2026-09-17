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

_oh_my_usage_view_load() {
  local mode=auto order=auto
  [[ -r "$_OH_MY_USAGE_CONFIG/mode" ]] && IFS= read -r mode < "$_OH_MY_USAGE_CONFIG/mode"
  [[ -r "$_OH_MY_USAGE_CONFIG/order" ]] && IFS= read -r order < "$_OH_MY_USAGE_CONFIG/order"
  typeset -g _OH_MY_USAGE_VIEW_KEY="$mode|$order"
}

_oh_my_usage_color_load() {
  local saved='' color=${OH_MY_USAGE_INLINE_COLOR:-245}
  [[ -r "$_OH_MY_USAGE_CONFIG/color" ]] && IFS= read -r saved < "$_OH_MY_USAGE_CONFIG/color"
  if [[ $saved == <-> && ${#saved} -le 3 ]] && (( saved <= 255 )); then
    color=$saved
  fi
  [[ $color == <-> && ${#color} -le 3 ]] || color=245
  (( color <= 255 )) || color=245
  typeset -g _OH_MY_USAGE_INLINE_COLOR=$color
}
