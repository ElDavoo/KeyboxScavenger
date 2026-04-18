#!/system/bin/sh
# playintegrityfix SECURITY_PATCH monitor daemon
# Runs action.sh once per day when SECURITY_PATCH is 30+ days old,
# until SECURITY_PATCH changes.

set -eu

daemon_id=pif
domain=eldavoo
execDir=/data/adb/modules/kbs
dataDir=$execDir/.data/pif
TMPDIR=$execDir/.run/pif

propFile=/data/adb/modules/playintegrityfix/custom.pif.prop
actionFile=/data/adb/modules/playintegrityfix/action.sh
minAgeSeconds=$((30 * 86400))
checkIntervalSeconds=3600

stateDir=$dataDir/state
stateFile=$stateDir/pif.state
logFile=$dataDir/logs/pifd.log

mkdir -p "$TMPDIR" "$stateDir" "$dataDir/logs"
export domain execDir dataDir TMPDIR

. "$execDir/setup-busybox.sh"
. "$execDir/pif-acquire-lock.sh"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$logFile"
}

lastPatch=
lastRunDate=

load_state() {
  [ -f "$stateFile" ] || return 0
  # shellcheck disable=SC1090
  . "$stateFile" 2>/dev/null || :
}

save_state() {
  cat > "$stateFile" <<EOF
lastPatch='${lastPatch}'
lastRunDate='${lastRunDate}'
EOF
}

cleanup_tmp() {
  rm -f "$TMPDIR/.pifd.tmp" 2>/dev/null || :
}

exxit() {
  exitCode=$?
  set +eu
  trap - EXIT
  save_state
  cleanup_tmp
  cd /
  exit "$exitCode"
}

trap exxit EXIT

date_to_epoch() {
  local epoch=
  epoch=$(date -d "$1" +%s 2>/dev/null || :)
  [ -n "$epoch" ] && {
    printf '%s\n' "$epoch"
    return 0
  }
  epoch=$("$execDir/.busybox/date" -D %Y-%m-%d -d "$1" +%s 2>/dev/null || :)
  [ -n "$epoch" ] && {
    printf '%s\n' "$epoch"
    return 0
  }
  return 1
}

read_security_patch() {
  [ -f "$propFile" ] || return 0
  sed -n 's/\r$//; s/^SECURITY_PATCH=\([0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\)$/\1/p' "$propFile" | head -n 1
}

is_patch_stale() {
  local patchEpoch=
  local nowEpoch=

  patchEpoch=$(date_to_epoch "$1" 2>/dev/null || :)
  [ -n "$patchEpoch" ] || return 1

  nowEpoch=$(date +%s)
  [ $((nowEpoch - patchEpoch)) -ge "$minAgeSeconds" ]
}

run_action_if_needed() {
  local patch=
  local today=
  local actionShell=$execDir/.busybox/ash
  local actionRc=

  patch=$(read_security_patch)
  today=$(date +%F)

  if [ -z "$patch" ]; then
    [ -z "$lastPatch" ] || {
      lastPatch=
      lastRunDate=
      save_state
    }
    return 0
  fi

  if [ "$patch" != "$lastPatch" ]; then
    log "SECURITY_PATCH changed to $patch"
    lastPatch=$patch
    lastRunDate=
    save_state
  fi

  is_patch_stale "$patch" || return 0

  [ "$lastRunDate" = "$today" ] && return 0

  if [ ! -f "$actionFile" ]; then
    log "action script missing: $actionFile"
    lastRunDate=$today
    save_state
    return 0
  fi

  if [ ! -x "$actionShell" ]; then
    log "missing compatible shell: $actionShell"
    lastRunDate=$today
    save_state
    return 0
  fi

  log "running $actionFile with $actionShell (SECURITY_PATCH=$patch)"
  if "$actionShell" "$actionFile" >> "$logFile" 2>&1; then
    log "action.sh completed"
  else
    actionRc=$?
    log "action.sh failed (exit $actionRc)"
  fi

  lastRunDate=$today
  save_state
}

load_state
run_action_if_needed

while :; do
  sleep "$checkIntervalSeconds"
  run_action_if_needed
done
