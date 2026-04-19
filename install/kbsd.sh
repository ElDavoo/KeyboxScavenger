#!/system/bin/sh
# keybox updater daemon (kbsd)
# Reuses KBS crash-safety skeleton (lock + trap cleanup),
# with legacy controller logic removed.

set -eu

id=kbs
domain=eldavoo
execDir=/data/adb/modules/$id
dataDir=$execDir/data/keybox
TMPDIR=$execDir/run/keybox

url=${KEYBOX_URL:-https://www.davidepalma.it/pib/keybox.xml}
target=${KEYBOX_TARGET:-/data/adb/tricky_store/keybox.xml}
intervalSeconds=${KEYBOX_INTERVAL_SECONDS:-10800}

stateDir=$dataDir/state
stateFile=$stateDir/keybox.last_modified
logFile=$dataDir/logs/keyboxd.log
headFile=$TMPDIR/keybox.head

mkdir -p "$TMPDIR" "$dataDir/logs" "$stateDir"
export id domain execDir dataDir TMPDIR

. "$execDir/setup-busybox.sh"
. "$execDir/acquire-lock.sh"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$logFile"
}

cleanup_tmp() {
  rm -f "$headFile" "$TMPDIR/keybox.body.tmp" 2>/dev/null || :
}

exxit() {
  exitCode=$?
  set +eu
  trap - EXIT
  cleanup_tmp
  cd /
  exit "$exitCode"
}

trap exxit EXIT

download_file() {
  # $1: destination file
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --connect-timeout 30 --max-time 120 -o "$1" "$url" >/dev/null 2>&1 && return 0
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -q --no-check-certificate -O "$1" "$url" >/dev/null 2>&1 && return 0
  fi
  return 1
}

head_request() {
  : > "$headFile"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSIL --connect-timeout 20 --max-time 60 "$url" > "$headFile" 2>/dev/null && return 0
  fi
  if command -v wget >/dev/null 2>&1; then
    wget --server-response --spider --no-check-certificate "$url" > /dev/null 2> "$headFile" && return 0
  fi
  return 1
}

http_status() {
  awk 'toupper($1) ~ /^HTTP\// {code=$2} END {print code+0}' "$headFile"
}

last_modified() {
  awk 'tolower($0) ~ /^last-modified:/ {line=$0} END {sub(/\r$/, "", line); sub(/^[^:]*:[[:space:]]*/, "", line); print line}' "$headFile"
}

file_hash() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
    return 0
  fi
  if command -v md5sum >/dev/null 2>&1; then
    md5sum "$1" | awk '{print $1}'
    return 0
  fi
  cksum "$1" | awk '{print $1":"$2}'
}

replace_target() {
  # $1: new file, $2: target
  local newFile=$1
  local dst=$2
  local mode=644
  local owner=0
  local group=0
  local context=

  if [ -f "$dst" ]; then
    mode=$(stat -c '%a' "$dst" 2>/dev/null || echo 644)
    owner=$(stat -c '%u' "$dst" 2>/dev/null || echo 0)
    group=$(stat -c '%g' "$dst" 2>/dev/null || echo 0)
    context=$(ls -Zd "$dst" 2>/dev/null | awk '{print $1}')
  fi

  mv -f "$newFile" "$dst" || return 1

  chown "$owner:$group" "$dst" 2>/dev/null || :
  chmod "$mode" "$dst" 2>/dev/null || :

  if [ -n "$context" ]; then
    chcon "$context" "$dst" 2>/dev/null || /system/bin/restorecon "$dst" 2>/dev/null || restorecon "$dst" 2>/dev/null || :
  else
    /system/bin/restorecon "$dst" 2>/dev/null || restorecon "$dst" 2>/dev/null || :
  fi

  return 0
}

sync_keybox() {
  local targetDir=${target%/*}
  local lm=
  local oldLm=
  local status=
  local tmpBody=
  local oldHash=
  local newHash=

  [ -d "$targetDir" ] || return 0

  if ! head_request; then
    log "HEAD request failed"
    return 0
  fi

  status=$(http_status)
  case "$status" in
    200|301|302|303|307|308|304) ;;
    *)
      log "HEAD returned status $status"
      return 0
    ;;
  esac

  lm=$(last_modified)
  oldLm=$(cat "$stateFile" 2>/dev/null || :)

  if [ -n "$lm" ] && [ -n "$oldLm" ] && [ "$lm" = "$oldLm" ]; then
    return 0
  fi

  tmpBody="$targetDir/.keybox.xml.tmp.$$"
  if ! download_file "$tmpBody" || [ ! -s "$tmpBody" ]; then
    rm -f "$tmpBody" 2>/dev/null || :
    log "download failed"
    return 0
  fi

  if [ -z "$lm" ] && [ -f "$target" ]; then
    oldHash=$(file_hash "$target" 2>/dev/null || :)
    newHash=$(file_hash "$tmpBody" 2>/dev/null || :)
    if [ -n "$oldHash" ] && [ "$oldHash" = "$newHash" ]; then
      rm -f "$tmpBody" 2>/dev/null || :
      return 0
    fi
  fi

  if replace_target "$tmpBody" "$target"; then
    if [ -n "$lm" ]; then
      printf '%s\n' "$lm" > "$stateFile"
    else
      : > "$stateFile"
    fi
    log "updated $target"
  else
    rm -f "$tmpBody" 2>/dev/null || :
    log "failed replacing $target"
  fi
}

# one immediate check, then periodic checks every 3 hours (default)
sync_keybox
while :; do
  sleep "$intervalSeconds"
  sync_keybox
done
