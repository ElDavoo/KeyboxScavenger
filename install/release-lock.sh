# usage: . $0
id=kbs
execDir=${execDir:-/data/adb/modules/kbs}
. "$execDir/boottime-sleep.sh" 2>/dev/null || :

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
    if [ -x "$execDir/bin/kbs-sleep" ]; then
      "$execDir/bin/kbs-sleep" 1 || sleep 1
    else
      sleep 1
    fi
    remaining=$((remaining - 1))
  done

  flock -n "$fd"
}

(pid=
exec 2>/dev/null
set +euo sh || :
if ! flock -n 0; then
  read pid
  kill $pid >/dev/null
  boottime_wait_flock_fd 0 10 || :
  kill -KILL $pid >/dev/null
  flock 0
fi) <>$TMPDIR/${id}.lock || :
