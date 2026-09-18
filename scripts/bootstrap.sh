#!/bin/sh
# Sourced by install.sh before Python is available. System packages are the only
# privileged operation; the application and its virtualenv stay user-local.

omu_as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo 'Missing system packages require root or sudo. Ask an administrator to install Python 3.9+, its venv/pip packages, and zsh.' >&2
    return 1
  fi
}

omu_python_ready() {
  "$python" -c 'import sys, ssl, sqlite3, venv, ensurepip; ensurepip.version(); sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1
}

omu_apt_install() {
  # APT retains indexes from healthy repositories even when another repository
  # has a missing Release file. Do not edit the user's sources or disable checks.
  if omu_as_root apt-get update; then
    :
  else
    apt_status=$?
    # Only APT's ordinary error code is recoverable here. Preserve cancellation
    # and sudo failures instead of starting another privileged command.
    [ "$apt_status" -eq 100 ] || return "$apt_status"
    echo 'oh-my-usage: APT could not refresh every repository. Trying prerequisite installation from the available package indexes.' >&2
    echo 'Repository settings and normal APT verification are unchanged.' >&2
  fi
  if omu_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$@"; then
    return 0
  else
    apt_status=$?
    echo 'oh-my-usage: Required system packages could not be installed. See the APT error above; installation has not completed.' >&2
    return "$apt_status"
  fi
}

omu_bootstrap() {
  need_python=no need_zsh=no need_ps=no need_ca=no
  omu_python_ready || need_python=yes
  if [ "$with_shell" = yes ] && ! command -v zsh >/dev/null 2>&1; then need_zsh=yes; fi
  if [ "$platform" = Linux ]; then
    command -v ps >/dev/null 2>&1 || need_ps=yes
    [ -s /etc/ssl/certs/ca-certificates.crt ] || [ -s /etc/pki/tls/certs/ca-bundle.crt ] || need_ca=yes
  fi
  [ "$need_python$need_zsh$need_ps$need_ca" != nononono ] || return 0
  echo 'Preparing missing system dependencies (sudo may ask for your password)...'
  if [ "$platform" = Darwin ]; then
    brew_cmd=$(command -v brew || true)
    [ -n "$brew_cmd" ] || { echo 'Homebrew is needed to install missing dependencies on macOS: https://brew.sh' >&2; return 1; }
    set --
    [ "$need_python" = no ] || set -- "$@" python
    [ "$need_zsh" = no ] || set -- "$@" zsh
    "$brew_cmd" install "$@"
    if [ "$need_python" = yes ] && [ -z "${OH_MY_USAGE_PYTHON:-}" ]; then
      python="$("$brew_cmd" --prefix)/bin/python3"
    fi
  elif command -v apt-get >/dev/null 2>&1; then
    set --
    [ "$need_python" = no ] || set -- "$@" python3 python3-venv python3-pip
    [ "$need_zsh" = no ] || set -- "$@" zsh
    [ "$need_ps" = no ] || set -- "$@" procps
    [ "$need_ca" = no ] || set -- "$@" ca-certificates
    omu_apt_install "$@"
  elif command -v dnf >/dev/null 2>&1; then
    set --
    [ "$need_python" = no ] || set -- "$@" python3 python3-pip
    [ "$need_zsh" = no ] || set -- "$@" zsh
    [ "$need_ps" = no ] || set -- "$@" procps-ng
    [ "$need_ca" = no ] || set -- "$@" ca-certificates
    omu_as_root dnf install -y "$@"
  elif command -v pacman >/dev/null 2>&1; then
    set --
    [ "$need_python" = no ] || set -- "$@" python python-pip
    [ "$need_zsh" = no ] || set -- "$@" zsh
    [ "$need_ps" = no ] || set -- "$@" procps-ng
    [ "$need_ca" = no ] || set -- "$@" ca-certificates
    # Do not update Arch's package database without a corresponding system upgrade.
    omu_as_root pacman -S --needed --noconfirm "$@"
  elif command -v zypper >/dev/null 2>&1; then
    set --
    [ "$need_python" = no ] || set -- "$@" python3 python3-pip
    [ "$need_zsh" = no ] || set -- "$@" zsh
    [ "$need_ps" = no ] || set -- "$@" procps
    [ "$need_ca" = no ] || set -- "$@" ca-certificates
    omu_as_root zypper --non-interactive install "$@"
  elif command -v apk >/dev/null 2>&1; then
    set --
    [ "$need_python" = no ] || set -- "$@" python3 py3-pip
    [ "$need_zsh" = no ] || set -- "$@" zsh
    [ "$need_ps" = no ] || set -- "$@" procps
    [ "$need_ca" = no ] || set -- "$@" ca-certificates
    omu_as_root apk add --no-cache "$@"
  else
    echo 'No supported package manager found. Install Python 3.9+ with venv/ensurepip and zsh, then rerun ./install.sh.' >&2
    return 1
  fi
  if ! omu_python_ready && [ -z "${OH_MY_USAGE_PYTHON:-}" ] && [ -x /usr/bin/python3 ]; then
    python=/usr/bin/python3
  fi
  if ! omu_python_ready; then
    echo 'Python still lacks Python 3.9+, ssl, sqlite3, venv or ensurepip. Check OH_MY_USAGE_PYTHON or your distribution Python packages.' >&2
    return 1
  fi
  if [ "$with_shell" = yes ] && ! command -v zsh >/dev/null 2>&1; then
    echo 'The package manager did not provide zsh.' >&2
    return 1
  fi
}
