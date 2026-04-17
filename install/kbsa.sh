#!/system/bin/sh
# kbsa compatibility wrapper (updater-only)

set -eu
id=kbs
domain=eldavoo
exec /data/adb/$domain/$id/kbs.sh "$@"
