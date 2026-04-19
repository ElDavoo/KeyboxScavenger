#!/system/bin/sh
# $id uninstaller
# id is set/corrected by build.sh
# Copyright 2019-2024, ElDavoo
# License: GPLv3+

set -u
id=kbs
domain=eldavoo
execDir=/data/adb/modules/$id
export TMPDIR=$execDir/run/keybox
pifTMPDIR=$execDir/run/pif

# set up busybox
#BB#
bin_dir=/data/adb/modules/$id/bin
busybox_dir=/data/adb/modules/$id/busybox
magisk_busybox="$(ls /data/adb/*/bin/busybox /data/adb/magisk/busybox 2>/dev/null || :)"
[ -x $busybox_dir/ls ] || {
  mkdir -p $busybox_dir $bin_dir
  chmod 0755 $busybox_dir $bin_dir $bin_dir/busybox 2>/dev/null || :
  for f in $bin_dir/busybox $magisk_busybox /system/*bin/busybox*; do
    [ -e "$f" ] || continue
    [ -x "$f" ] || chmod 0755 "$f" 2>/dev/null || :
    "$f" --install -s "$busybox_dir/" >/dev/null 2>&1 && break || :
  done
  [ -x $busybox_dir/ls ] || {
    echo "Install busybox or simply place it in $bin_dir/"
    echo
    exit 3
  }
}
case $PATH in
  $bin_dir:*) ;;
  *) export PATH="$bin_dir:$busybox_dir:$PATH";;
esac
unset f bin_dir busybox_dir magisk_busybox
#/BB#

exec 2>/dev/null

# terminate/kill $id processes
mkdir -p $TMPDIR
(flock -n 0 || {
  read pid
  kill $pid
  timeout 10 flock 0
  kill -KILL $pid >/dev/null 2>&1
  flock 0
}) <>$TMPDIR/${id}.lock

# terminate/kill pif daemon process
mkdir -p $pifTMPDIR
(flock -n 0 || {
  read pid
  kill $pid
  timeout 10 flock 0
  kill -KILL $pid >/dev/null 2>&1
  flock 0
}) <>$pifTMPDIR/pif.lock

# uninstall
rm -rf \
  /data/local/tmp/${id}[-_]* \
  /data/adb/service.d/${id}-*.sh \
  /data/data/github.eldavoo.keyboxscavenger/files/$id \
  /data/data/com.termux/files/home/.termux/boot/${id}-init.sh

[ "${1:-}" = install ] || rm -rf "$execDir/data" "$execDir/run"

exit 0
