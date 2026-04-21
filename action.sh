#!/system/bin/sh
# PlayIntegrityFix action script helper for KeyboxScavenger.
# Shows recent KeyboxScavenger daemon logs, then runs autopif4.

MODPATH="${0%/*}"

boottime_sleep_once() {
  local seconds=${1:-0}

  case "$seconds" in
    ''|*[!0-9]*) return 2 ;;
  esac

  [ "$seconds" -gt 0 ] || return 0

  if [ -x /data/adb/modules/kbs/bin/kbs-sleep ]; then
    /data/adb/modules/kbs/bin/kbs-sleep "$seconds" && return 0
  fi

  if [ -x /system/bin/sleep ]; then
    /system/bin/sleep "$seconds"
  else
    sleep "$seconds"
  fi
}

# show daemon logs first so action output includes context
if [ -x /data/adb/modules/kbs/kbs.sh ]; then
  echo "=== KeyboxScavenger logs (last 120 lines) ==="
  /data/adb/modules/kbs/kbs.sh --log all 120 2>/dev/null || :
  echo "=== End KeyboxScavenger logs ==="
  echo
else
  echo "KeyboxScavenger CLI not found at /data/adb/modules/kbs/kbs.sh"
  echo
fi

# warn since KernelSU/APatch's implementation automatically closes if successful
if [ "$KSU" = "true" -o "$APATCH" = "true" ] && [ "$KSU_NEXT" != "true" ] && [ "$WKSU" != "true" ] && [ "$MMRL" != "true" ]; then
    echo -e "\nClosing dialog in 20 seconds ..."
  boottime_sleep_once 20
fi
