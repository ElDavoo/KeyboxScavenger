#!/system/bin/sh
# $id uninstaller
# id is set/corrected by build.sh
# Copyright 2019-2024, ElDavoo
# License: GPLv3+

set -u
id=kbs
domain=eldavoo
export TMPDIR=/dev/.$domain/$id
pifTMPDIR=/dev/.$domain/pif

# set up busybox
#BB#
bin_dir=/data/adb/eldavoo/bin
busybox_dir=/dev/.eldavoo/busybox
magisk_busybox="$(ls /data/adb/*/bin/busybox /data/adb/magisk/busybox 2>/dev/null || :)"
[ -x $busybox_dir/ls ] || {
  mkdir -p $busybox_dir
  chmod 0755 $busybox_dir $bin_dir/busybox 2>/dev/null || :
  for f in $bin_dir/busybox $magisk_busybox /system/*bin/busybox*; do
    [ -x $f ] && eval $f --install -s $busybox_dir/ && break || :
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

[ "${1:-}" = install ] || rm -rf $(readlink -f /data/adb/$domain/$id) /data/adb/$domain/${id}-data
[ "${1:-}" = install ] || rm -rf /data/adb/$domain/pif-data
rmdir /data/adb/$domain

exit 0
