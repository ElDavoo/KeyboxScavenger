#!/system/bin/sh
# PlayIntegrityFix action script helper for KeyboxScavenger.
# Shows recent KeyboxScavenger daemon logs, then runs autopif4.

MODPATH="${0%/*}"

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
    sleep 20
fi
