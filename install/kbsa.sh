#!/system/bin/sh
# kbsa compatibility wrapper (updater-only)

set -eu
id=kbs
exec /data/adb/modules/$id/kbs.sh "$@"
