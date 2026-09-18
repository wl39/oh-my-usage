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
  local position=auto
  [[ -r "$_OH_MY_USAGE_CONFIG/position" ]] && IFS= read -r position < "$_OH_MY_USAGE_CONFIG/position"
  [[ $position == (auto|left|right|after|above) ]] || position=auto
  typeset -g _OH_MY_USAGE_INLINE_POSITION=$position
  local gap=1 indent=0 width=auto
  [[ -r "$_OH_MY_USAGE_CONFIG/gap" ]] && IFS= read -r gap < "$_OH_MY_USAGE_CONFIG/gap"
  [[ -r "$_OH_MY_USAGE_CONFIG/indent" ]] && IFS= read -r indent < "$_OH_MY_USAGE_CONFIG/indent"
  [[ -r "$_OH_MY_USAGE_CONFIG/width" ]] && IFS= read -r width < "$_OH_MY_USAGE_CONFIG/width"
  [[ $gap == <-> && ${#gap} -le 1 ]] && (( gap <= 8 )) || gap=1
  [[ $indent == <-> && ${#indent} -le 2 ]] && (( indent <= 20 )) || indent=0
  [[ $width == <-> && ${#width} -le 3 ]] && (( width >= 1 && width <= 240 )) || width=auto
  typeset -g _OH_MY_USAGE_INLINE_GAP=$gap _OH_MY_USAGE_INLINE_INDENT=$indent _OH_MY_USAGE_INLINE_WIDTH=$width
}

_oh_my_usage_view_load() {
  local mode=auto order=auto
  [[ -r "$_OH_MY_USAGE_CONFIG/mode" ]] && IFS= read -r mode < "$_OH_MY_USAGE_CONFIG/mode"
  [[ -r "$_OH_MY_USAGE_CONFIG/order" ]] && IFS= read -r order < "$_OH_MY_USAGE_CONFIG/order"
  typeset -g _OH_MY_USAGE_VIEW_KEY="$mode|$order"
  local backend=direct saved_source=''
  [[ -n ${OH_MY_USAGE_PREFERENCES:-} ]] && backend=openusage
  [[ -r "$_OH_MY_USAGE_CONFIG/source" ]] && IFS= read -r saved_source < "$_OH_MY_USAGE_CONFIG/source"
  [[ $saved_source == (direct|openusage) ]] && backend=$saved_source
  [[ ${OH_MY_USAGE_SOURCE:-} == (direct|openusage) ]] && backend=$OH_MY_USAGE_SOURCE
  [[ $backend == direct ]] && _OH_MY_USAGE_VIEW_KEY+='|source=direct'
  local style=text icons=unicode
  [[ -r "$_OH_MY_USAGE_CONFIG/style" ]] && IFS= read -r style < "$_OH_MY_USAGE_CONFIG/style"
  [[ -r "$_OH_MY_USAGE_CONFIG/icons" ]] && IFS= read -r icons < "$_OH_MY_USAGE_CONFIG/icons"
  [[ $icons == ascii ]] || icons=unicode
  [[ $style == icons ]] && _OH_MY_USAGE_VIEW_KEY+="|icons|$icons"
  local name default setting
  for name default in metric-labels auto mode-label on separator pipe icon-map '{}' providers '{}' metrics '{}'; do
    setting=$default
    [[ -r "$_OH_MY_USAGE_CONFIG/$name" ]] && IFS= read -r setting < "$_OH_MY_USAGE_CONFIG/$name"
    [[ $setting != "$default" ]] && _OH_MY_USAGE_VIEW_KEY+="|$name=$setting"
  done
  return 0
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
