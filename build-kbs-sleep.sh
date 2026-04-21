#!/usr/bin/env sh
set -eu

# Cross-build kbs-sleep for Android API 26.
# Requires ANDROID_NDK_HOME (or ANDROID_NDK_ROOT) to point to an unpacked Android NDK.

SELF_DIR=$(CDPATH= cd -- "${0%/*}" && pwd)
SRC=$SELF_DIR/native/kbs-sleep.c
OUT_DIR=$SELF_DIR/bin
API=${KBS_SLEEP_API:-26}

NDK_HOME=${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}
if [ -z "$NDK_HOME" ] || [ ! -d "$NDK_HOME" ]; then
  echo "Set ANDROID_NDK_HOME (or ANDROID_NDK_ROOT) to your Android NDK path." >&2
  exit 2
fi

HOST_TAG=
case "$(uname -s)" in
  Linux)
    for tag in linux-x86_64 linux-aarch64; do
      [ -d "$NDK_HOME/toolchains/llvm/prebuilt/$tag/bin" ] && {
        HOST_TAG=$tag
        break
      }
    done
  ;;
  Darwin)
    for tag in darwin-arm64 darwin-x86_64; do
      [ -d "$NDK_HOME/toolchains/llvm/prebuilt/$tag/bin" ] && {
        HOST_TAG=$tag
        break
      }
    done
  ;;
  *)
    echo "Unsupported host OS: $(uname -s)" >&2
    exit 2
  ;;
esac

[ -n "$HOST_TAG" ] || {
  echo "Unable to find an NDK host toolchain in $NDK_HOME/toolchains/llvm/prebuilt" >&2
  exit 2
}

TOOLCHAIN=$NDK_HOME/toolchains/llvm/prebuilt/$HOST_TAG/bin
[ -d "$TOOLCHAIN" ] || {
  echo "NDK toolchain not found: $TOOLCHAIN" >&2
  exit 2
}

mkdir -p "$OUT_DIR"

build_one() {
  abi=$1
  cc=$2
  out=$3

  static_ok=true

  "$TOOLCHAIN/$cc" \
    -O2 -ffunction-sections -fdata-sections -fno-ident \
    -Wl,--gc-sections \
    -static \
    -o "$out" "$SRC" 2>/dev/null || static_ok=false

  if ! $static_ok; then
    echo "[$abi] static link failed, building dynamic fallback" >&2
    "$TOOLCHAIN/$cc" \
      -O2 -ffunction-sections -fdata-sections -fno-ident \
      -Wl,--gc-sections \
      -o "$out" "$SRC"
  fi

  chmod 0755 "$out"

  if command -v file >/dev/null 2>&1; then
    echo "[$abi] $(file "$out")"
  else
    echo "[$abi] built $out"
  fi

  if command -v readelf >/dev/null 2>&1; then
    if readelf -l "$out" | grep -q INTERP; then
      echo "[$abi] dynamic binary (INTERP present)"
    else
      echo "[$abi] static binary (no INTERP)"
    fi
  fi
}

build_one arm64-v8a "aarch64-linux-android${API}-clang" "$OUT_DIR/kbs-sleep.arm64-v8a"
build_one armeabi-v7a "armv7a-linux-androideabi${API}-clang" "$OUT_DIR/kbs-sleep.armeabi-v7a"
build_one x86_64 "x86_64-linux-android${API}-clang" "$OUT_DIR/kbs-sleep.x86_64"

echo "Done. Artifacts in $OUT_DIR"
