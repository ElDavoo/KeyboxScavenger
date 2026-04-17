#!/system/bin/sh
# KBS compatibility CLI (updater-only)
# Controls updater daemons only.

set -eu

id=kbs
domain=eldavoo
execDir=/data/adb/$domain/$id
keyboxTMP=/dev/.$domain/$id
keyboxData=/data/adb/$domain/${id}-data
pifId=pif
pifTMP=/dev/.$domain/$pifId
pifData=/data/adb/$domain/${pifId}-data

mkdir -p "$keyboxTMP" "$keyboxData" "$pifTMP" "$pifData"

. "$execDir/setup-busybox.sh"

daemon_running() {
  local lockFile=$1
  if (flock -n 8) 8<>"$lockFile"; then
    return 1
  fi
  return 0
}

print_status() {
  if daemon_running "$keyboxTMP/${id}.lock"; then
    echo "keyboxd: running (pid $(cat "$keyboxTMP/${id}.lock" 2>/dev/null || echo '?'))"
  else
    echo "keyboxd: stopped"
  fi

  if daemon_running "$pifTMP/pif.lock"; then
    echo "pifd: running (pid $(cat "$pifTMP/pif.lock" 2>/dev/null || echo '?'))"
  else
    echo "pifd: stopped"
  fi
}

stop_daemons() {
  TMPDIR="$keyboxTMP"
  export TMPDIR
  . "$execDir/release-lock.sh"

  TMPDIR="$pifTMP"
  export TMPDIR
  . "$execDir/pif-release-lock.sh"
}

start_daemons() {
  rm -f "$keyboxData/disable" 2>/dev/null || :
  exec "$execDir/service.sh"
}

print_help() {
  cat <<'EOT'
Usage
  kbs --daemon [status|start|stop|restart]
  kbs --log [keybox|pif|all] [lines]
  kbsd,   Print daemon status
  kbsd.   Stop both daemons

Note
  Legacy controller features were removed.
EOT
}

print_log() {
  local target=${1:-keybox}
  local lines=${2:-80}

  case "$target" in
    keybox)
      tail -n "$lines" "$keyboxData/logs/keyboxd.log" 2>/dev/null || :
    ;;
    pif)
      tail -n "$lines" "$pifData/logs/pifd.log" 2>/dev/null || :
    ;;
    all)
      echo "== keyboxd =="
      tail -n "$lines" "$keyboxData/logs/keyboxd.log" 2>/dev/null || :
      echo "== pifd =="
      tail -n "$lines" "$pifData/logs/pifd.log" 2>/dev/null || :
    ;;
    *)
      print_help
      return 1
    ;;
  esac
}

case "${0##*/}" in
  kbsd,)
    print_status
    exit 0
  ;;
  kbsd.)
    stop_daemons
    echo "daemons stopped"
    exit 0
  ;;
esac

case "${1:-}" in
  ""|-h|--help)
    print_help
  ;;

  -D|--daemon)
    case "${2:-status}" in
      status)
        print_status
      ;;
      start)
        start_daemons
      ;;
      stop)
        stop_daemons
        echo "daemons stopped"
      ;;
      restart)
        stop_daemons
        start_daemons
      ;;
      *)
        print_help
        exit 1
      ;;
    esac
  ;;

  -l|--log)
    print_log "${2:-keybox}" "${3:-80}"
  ;;

  *)
    print_help
    exit 1
  ;;
esac

exit 0
