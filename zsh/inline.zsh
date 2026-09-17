# Optional ZLE display. Only shell builtins run while editing input.
_oh_my_usage_inline_control() {
  local action=${1:-status}
  (( $# )) && shift
  case $action in
    on|off)
      if (( $# == 0 )); then
        "$_OH_MY_USAGE_ROOT/bin/oh-my-usage" inline "$action" || return $?
        unset _OH_MY_USAGE_INLINE_SESSION
      elif (( $# == 1 )) && [[ $1 == --session ]]; then
        typeset -g _OH_MY_USAGE_INLINE_SESSION=$action
        print -r -- "inline: $action (session)"
      else
        print -u2 'Usage: oh-my-usage inline on|off [--session]'
        return 2
      fi
      # An explicit first enable should show data at the very next prompt.
      if [[ $action == on && ! -r "$_OH_MY_USAGE_CACHE/display" ]]; then
        oh-my-usage show > /dev/null
      fi
      _oh_my_usage_inline_sync
      ;;
    status)
      (( $# == 0 )) || { print -u2 'Usage: oh-my-usage inline status'; return 2; }
      _oh_my_usage_inline_load
      print -r -- "inline: $_OH_MY_USAGE_INLINE_MODE ($_OH_MY_USAGE_INLINE_ORIGIN)"
      ;;
    *) "$_OH_MY_USAGE_ROOT/bin/oh-my-usage" inline "$action" "$@" ;;
  esac
}

_oh_my_usage_inline_sync() {
  _oh_my_usage_inline_load
  if [[ $_OH_MY_USAGE_INLINE_MODE == on && ${OH_MY_USAGE_DISPLAY:-status} != off ]]; then
    [[ ${_OH_MY_USAGE_INLINE_ACTIVE:-0} == 1 ]] && return 0
    typeset -g _OH_MY_USAGE_INLINE_ACTIVE=1 _OH_MY_USAGE_INLINE_VISIBLE=0
    typeset -g _OH_MY_USAGE_INLINE_BASE=$RPROMPT _OH_MY_USAGE_INLINE_APPLIED=$RPROMPT
    typeset -g _OH_MY_USAGE_INLINE_LEFT_BASE=$PROMPT _OH_MY_USAGE_INLINE_LEFT_APPLIED=$PROMPT
    typeset -g _OH_MY_USAGE_INLINE_RENDERED='' _OH_MY_USAGE_INLINE_COLUMNS=0
    autoload -Uz add-zle-hook-widget
    add-zle-hook-widget line-init _oh_my_usage_inline_start
    add-zle-hook-widget line-pre-redraw _oh_my_usage_inline_redraw
    add-zle-hook-widget line-finish _oh_my_usage_inline_finish
  else
    _oh_my_usage_inline_disable
  fi
}

_oh_my_usage_inline_disable() {
  [[ ${_OH_MY_USAGE_INLINE_ACTIVE:-0} == 1 ]] || return 0
  _oh_my_usage_inline_finish
  add-zle-hook-widget -d line-init _oh_my_usage_inline_start
  add-zle-hook-widget -d line-pre-redraw _oh_my_usage_inline_redraw
  add-zle-hook-widget -d line-finish _oh_my_usage_inline_finish
  zle -D _oh_my_usage_inline_start _oh_my_usage_inline_redraw _oh_my_usage_inline_finish
  unset _OH_MY_USAGE_INLINE_ACTIVE _OH_MY_USAGE_INLINE_VISIBLE _OH_MY_USAGE_INLINE_BASE
  unset _OH_MY_USAGE_INLINE_APPLIED _OH_MY_USAGE_INLINE_RENDERED _OH_MY_USAGE_INLINE_COLUMNS
  unset _OH_MY_USAGE_INLINE_LEFT_BASE _OH_MY_USAGE_INLINE_LEFT_APPLIED
}

_oh_my_usage_inline_start() {
  _OH_MY_USAGE_INLINE_VISIBLE=0
  _oh_my_usage_inline_redraw
}

_oh_my_usage_inline_redraw() {
  # Keep the user's prompt options when ZLE expands their theme.
  _oh_my_usage_inline_update "$options[promptsubst]" && zle .reset-prompt
  return 0
}

_oh_my_usage_inline_update() {
  emulate -L zsh
  # A theme may replace RPROMPT between prompts or in another ZLE hook.
  [[ $RPROMPT == "$_OH_MY_USAGE_INLINE_APPLIED" ]] || _OH_MY_USAGE_INLINE_BASE=$RPROMPT
  [[ $PROMPT == "$_OH_MY_USAGE_INLINE_LEFT_APPLIED" ]] || _OH_MY_USAGE_INLINE_LEFT_BASE=$PROMPT
  local desired=$_OH_MY_USAGE_INLINE_BASE previous_render=$_OH_MY_USAGE_INLINE_RENDERED
  local desired_left=$_OH_MY_USAGE_INLINE_LEFT_BASE hint
  if [[ $_OH_MY_USAGE_INLINE_MODE == on && ${OH_MY_USAGE_DISPLAY:-status} != off &&
        $CONTEXT == start && -z $BUFFER && -z $PREBUFFER ]]; then
    if [[ $_OH_MY_USAGE_INLINE_VISIBLE == 0 || $_OH_MY_USAGE_INLINE_COLUMNS != $COLUMNS ]]; then
      _oh_my_usage_color_load
      local stamp text=$OH_MY_USAGE_TEXT color=$_OH_MY_USAGE_INLINE_COLOR
      local limit=$(( COLUMNS < 80 ? COLUMNS - 2 : COLUMNS / 2 ))
      local width=${OH_MY_USAGE_INLINE_WIDTH:-$limit}
      [[ $width == <-> && ${#width} -le 4 ]] || width=$limit
      (( width > limit )) && width=$limit
      (( width < 1 )) && width=1
      # Read once when becoming visible; no disk read for each typed character.
      if [[ -r "$_OH_MY_USAGE_CACHE/display" ]]; then
        { IFS= read -r stamp; IFS= read -r text; } < "$_OH_MY_USAGE_CACHE/display"
      fi
      # Literal percent signs cannot introduce prompt formatting directives.
      _OH_MY_USAGE_INLINE_RENDERED=${text:+"%F{$color}%${width}>…>${text//\%/%%}%>>%f"}
      _OH_MY_USAGE_INLINE_VISIBLE=1
      _OH_MY_USAGE_INLINE_COLUMNS=$COLUMNS
    fi
    if [[ -n $_OH_MY_USAGE_INLINE_RENDERED ]]; then
      # Parameter expansion is not recursive: usage text cannot run $() or `...`.
      if [[ $1 == on ]]; then
        hint='${_OH_MY_USAGE_INLINE_RENDERED}'
      else
        hint=$_OH_MY_USAGE_INLINE_RENDERED
      fi
      # A phone's long theme can leave no space for any right prompt.
      # Put the hint on its own prompt line, never in the editable buffer.
      if (( COLUMNS < 80 )); then
        desired_left=$hint$'\n'$_OH_MY_USAGE_INLINE_LEFT_BASE
      else
        desired=$hint
        [[ -n $_OH_MY_USAGE_INLINE_BASE ]] && desired+=" $_OH_MY_USAGE_INLINE_BASE"
      fi
    fi
  else
    _OH_MY_USAGE_INLINE_VISIBLE=0
  fi
  _OH_MY_USAGE_INLINE_APPLIED=$desired
  _OH_MY_USAGE_INLINE_LEFT_APPLIED=$desired_left
  if [[ $RPROMPT == "$desired" && $PROMPT == "$desired_left" &&
        $_OH_MY_USAGE_INLINE_RENDERED == "$previous_render" ]]; then
    return 1
  fi
  RPROMPT=$desired
  PROMPT=$desired_left
  return 0
}

_oh_my_usage_inline_finish() {
  _OH_MY_USAGE_INLINE_VISIBLE=0
  local changed=0
  if [[ $RPROMPT == "$_OH_MY_USAGE_INLINE_APPLIED" && $RPROMPT != "$_OH_MY_USAGE_INLINE_BASE" ]]; then
    RPROMPT=$_OH_MY_USAGE_INLINE_BASE
    _OH_MY_USAGE_INLINE_APPLIED=$RPROMPT
    changed=1
  fi
  if [[ $PROMPT == "$_OH_MY_USAGE_INLINE_LEFT_APPLIED" && $PROMPT != "$_OH_MY_USAGE_INLINE_LEFT_BASE" ]]; then
    PROMPT=$_OH_MY_USAGE_INLINE_LEFT_BASE
    _OH_MY_USAGE_INLINE_LEFT_APPLIED=$PROMPT
    changed=1
  fi
  # Remove the hint before the line enters scrollback, including an empty Enter.
  (( changed )) && zle && zle .reset-prompt
  return 0
}
