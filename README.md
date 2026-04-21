# Keybox Scavenger

![Keybox Scavenger](https://repository-images.githubusercontent.com/1213838454/00fef3de-b7a0-4777-910a-2eb06326c3ab)

> Another unnecessary modulr - @bad_rulez

Systemless Magisk/Root module that does two things:
1. Keeps your keybox up to date downloading it automatically from my server.
2. Auto-runs Play Integrity Fork action.sh when it's time.

In this way, your root setup becomes 100% "set and forget".


## Keybox Service (`kbsd`)
- Every 3 hours (with an immediate run at start), performs a HEAD request to:
  - `https://www.davidepalma.it/pib/keybox.xml`
- Downloads only when modified.
- Writes to:
  - `/data/adb/tricky_store/keybox.xml`
- Preserves destination owner/group/mode/SELinux context.

## PlayIntegrityFix Patch Watcher (`pifd`)
- Reads:
  - `/data/adb/modules/playintegrityfix/custom.pif.prop`
- Parses:
  - `SECURITY_PATCH=YYYY-MM-DD`
- If patch date is at least 30 days old, runs:
  - `/data/adb/modules/playintegrityfix/action.sh` with `/data/adb/modules/kbs/busybox/ash`
- Runs immediately when stale is detected, then once per day until `SECURITY_PATCH` changes.

## Crash Isolation

The services are independent:
- Separate process
- Separate lock file
- Separate state and log paths
- Separate exit traps

A crash in one service does not stop the other.

## Paths

- Keybox service lock: `/data/adb/modules/kbs/run/keybox/kbs.lock`
- PIF service lock: `/data/adb/modules/kbs/run/pif/pif.lock`
- Keybox logs/state: `/data/adb/modules/kbs/data/keybox/`
- PIF logs/state: `/data/adb/modules/kbs/data/pif/`

## Log Rotation

- Daemon logs are rotated daily (plain text archives).
- Rotated files are kept per daemon log and pruned to the newest 5 files.
- Current default logs are:
  - `/data/adb/modules/kbs/data/keybox/logs/keyboxd.log`
  - `/data/adb/modules/kbs/data/pif/logs/pifd.log`
- You can override retention count with `KBS_LOG_KEEP_COUNT`.

## CLI

- `kbs --daemon status`
- `kbs --daemon start`
- `kbs --daemon stop`
- `kbs --daemon restart`
- `kbs --log keybox`
- `kbs --log pif`
- `kbs --log all`