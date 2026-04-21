#!/system/bin/sh
# Daily log rotation helper (plain text archives).

set -eu

logFile=${1:-}
stateFile=${2:-}
keepCount=${3:-5}

[ -n "$logFile" ] && [ -n "$stateFile" ] || exit 64

case "$keepCount" in
  ''|*[!0-9]*) keepCount=5 ;;
esac

mkdir -p "${logFile%/*}" "${stateFile%/*}"

today=$(date +%F)
lastDay=$(cat "$stateFile" 2>/dev/null || :)

if [ "$lastDay" != "$today" ]; then
  if [ -s "$logFile" ]; then
    rotatedFile="$logFile.$today"
    if [ -f "$rotatedFile" ]; then
      cat "$logFile" >> "$rotatedFile" 2>/dev/null || :
      : > "$logFile"
    else
      mv -f "$logFile" "$rotatedFile" 2>/dev/null || :
      : > "$logFile"
    fi
  fi
  printf '%s\n' "$today" > "$stateFile" 2>/dev/null || :
fi

if [ "$keepCount" -gt 0 ]; then
  i=0
  for rotatedFile in $(ls -1 "$logFile".20??-??-?? 2>/dev/null | sort -r); do
    i=$((i + 1))
    [ "$i" -le "$keepCount" ] && continue
    rm -f "$rotatedFile" 2>/dev/null || :
  done
else
  for rotatedFile in $(ls -1 "$logFile".20??-??-?? 2>/dev/null | sort -r); do
    rm -f "$rotatedFile" 2>/dev/null || :
  done
fi

exit 0
