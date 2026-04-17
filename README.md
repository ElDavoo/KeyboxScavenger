# KeyboxScavenger

Systemless Magisk/Root module that runs two independent background services:

1. Keybox updater (`kbsd`)
- Every 3 hours (with an immediate run at start), performs a HEAD request to:
  - `https://www.davidepalma.it/pib/keybox.xml`
- Downloads only when modified.
- Writes to:
  - `/data/adb/tricky_store/keybox.xml`
- Preserves destination owner/group/mode/SELinux context.

2. PlayIntegrityFix patch watcher (`pifd`)
- Reads:
  - `/data/adb/modules/playintegrityfix/custom.pif.prop`
- Parses:
  - `SECURITY_PATCH=YYYY-MM-DD`
- If patch date is at least 30 days old, runs:
  - `/system/bin/sh /data/adb/modules/playintegrityfix/action.sh`
- Runs immediately when stale is detected, then once per day until `SECURITY_PATCH` changes.

## Crash Isolation

The services are independent:
- Separate process
- Separate lock file
- Separate state and log paths
- Separate exit traps

A crash in one service does not stop the other.

## Paths

- Keybox service lock: `/dev/.eldavoo/kbs/kbs.lock`
- PIF service lock: `/dev/.eldavoo/pif/pif.lock`
- Keybox logs/state: `/data/adb/eldavoo/kbs-data/`
- PIF logs/state: `/data/adb/eldavoo/pif-data/`

## CLI

- `kbs --daemon status`
- `kbs --daemon start`
- `kbs --daemon stop`
- `kbs --daemon restart`
- `kbs --log keybox`
- `kbs --log pif`
- `kbs --log all`

## Notes

- This repository no longer contains battery charging control logic.
- Legacy battery-related install scripts have been removed from `install/`.
