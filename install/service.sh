#!/system/bin/sh
# $id initializer
# Copyright 2017-2021, ElDavoo
# License: GPLv3+

id=kbs
domain=eldavoo
execDir=/data/adb/modules/$id

runtimeRoot=$execDir/run
dataRoot=$execDir/data
keyboxTmp=$runtimeRoot/keybox
keyboxData=$dataRoot/keybox
pifId=pif
pifTmp=$runtimeRoot/pif
pifData=$dataRoot/pif
rotateScript=$execDir/rotate-log.sh
logKeepCount=${KBS_LOG_KEEP_COUNT:-5}

[ -f "$execDir/disable" ] || [ -f "$keyboxData/disable" ] && exit 14

# Wait until userspace is fully available before touching /data/adb/modules.
slept=false
until [ ."$(getprop sys.boot_completed 2>/dev/null)" = .1 ] \
  && [ ."$(getprop init.svc.bootanim 2>/dev/null)" = .stopped ] \
  && [ -d /data/adb/modules ] \
  && [ -d "$execDir" ]
do
  [ -f "$execDir/disable" ] || [ -f "$keyboxData/disable" ] && exit 14
  sleep 10 && slept=true
done
$slept && sleep 30
unset slept

mkdir -p "$keyboxTmp" "$keyboxData" "$pifTmp" "$pifData"

export domain execDir

TMPDIR=$keyboxTmp
dataDir=$keyboxData
id=kbs
export id TMPDIR dataDir
. $execDir/setup-busybox.sh
. $execDir/release-lock.sh

TMPDIR=$pifTmp
dataDir=$pifData
id=$pifId
export id TMPDIR dataDir
. $execDir/pif-release-lock.sh

rotate_log_safe() {
  local logFile=$1
  local stateFile=$2
  [ -f "$rotateScript" ] || return 0
  sh "$rotateScript" "$logFile" "$stateFile" "$logKeepCount" >/dev/null 2>&1 || :
}

rotate_log_safe "$keyboxData/logs/keyboxd.log" "$keyboxData/state/keyboxd.log.rotate_date"
rotate_log_safe "$pifData/logs/pifd.log" "$pifData/state/pifd.log.rotate_date"

if [ ".$1" = .-x ]; then
  touch "$keyboxData/disable"
  exit 0
fi

keyboxRc=0
(
  export id=kbs TMPDIR="$keyboxTmp" dataDir="$keyboxData" domain execDir
  exec start-stop-daemon -bx "$execDir/kbsd.sh" -S -- "$@"
) || keyboxRc=$?

pifRc=0
(
  export id="$pifId" TMPDIR="$pifTmp" dataDir="$pifData" domain execDir
  exec start-stop-daemon -bx "$execDir/pifd.sh" -S --
) || pifRc=$?

[ $keyboxRc -eq 0 -o $pifRc -eq 0 ] && exit 0 || exit 12
