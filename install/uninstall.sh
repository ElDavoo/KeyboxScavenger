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

boottime_sleep_once() {
  local seconds=${1:-0}

  case "$seconds" in
    ''|*[!0-9]*) return 2 ;;
  esac

  [ "$seconds" -gt 0 ] || return 0

  if [ -x "$execDir/bin/kbs-sleep" ]; then
    "$execDir/bin/kbs-sleep" "$seconds" && return 0
  fi

  if [ -x /system/bin/sleep ]; then
    /system/bin/sleep "$seconds"
  else
    sleep "$seconds"
  fi
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
  boottime_wait_flock_fd 0 10 || :
  kill -KILL $pid >/dev/null 2>&1
  flock 0
}) <>$TMPDIR/${id}.lock

# terminate/kill pif daemon process
mkdir -p $pifTMPDIR
(flock -n 0 || {
  read pid
  kill $pid
  boottime_wait_flock_fd 0 10 || :
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
