#!/system/bin/sh
# $id initializer
# Copyright 2017-2021, ElDavoo
# License: GPLv3+

id=kbs
domain=eldavoo
execDir=/data/adb/$domain/$id

keyboxTmp=/dev/.$domain/$id
keyboxData=/data/adb/$domain/${id}-data
pifId=pif
pifTmp=/dev/.$domain/$pifId
pifData=/data/adb/$domain/${pifId}-data

[ -f $execDir/disable -o -f $keyboxData/disable ] && exit 14

# wait til the lock screen is ready and give some bootloop grace period
slept=false
until [ .$(getprop init.svc.bootanim 2>/dev/null) = .stopped ]; do
  [ -f $execDir/disable -o -f $keyboxData/disable ] && exit 14
  sleep 10 && slept=true
done
$slept && sleep 60
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
