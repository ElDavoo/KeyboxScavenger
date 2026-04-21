# usage: . $0

execDir=${execDir:-/data/adb/modules/kbs}
boottime_sleep_bin=${boottime_sleep_bin:-$execDir/bin/kbs-sleep}

boottime_sleep_once() {
  local seconds=${1:-0}

  case "$seconds" in
    ''|*[!0-9]*) return 2 ;;
  esac

  [ "$seconds" -gt 0 ] || return 0

  if [ -x "$boottime_sleep_bin" ]; then
    "$boottime_sleep_bin" "$seconds" && return 0
  fi

  if [ -x /system/bin/sleep ]; then
    /system/bin/sleep "$seconds"
  else
    sleep "$seconds"
  fi
}

boottime_sleep_interval() {
  local seconds=${1:-0}

  case "$seconds" in
    ''|*[!0-9]*) return 2 ;;
  esac

  boottime_sleep_once "$seconds"
}

boottime_wait_flock_fd() {
  local fd=${1:-0}
  local timeout=${2:-0}
  local remaining=

  case "$timeout" in
    ''|*[!0-9]*) return 2 ;;
  esac

  remaining=$timeout

  while [ "$remaining" -gt 0 ]; do
    flock -n "$fd" && return 0
    boottime_sleep_once 1 || return 1
    remaining=$((remaining - 1))
  done

  flock -n "$fd"
}
