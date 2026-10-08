#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MOBILE_DIR="$ROOT_DIR/mobile"
SITE_ORIGIN="$(tr -d '\r\n' < "$MOBILE_DIR/site-origin.txt")"

case "$SITE_ORIGIN" in
  https://*) ;;
  *) echo "site-origin.txt must contain one HTTPS origin" >&2; exit 1 ;;
esac
case "$SITE_ORIGIN" in
  *localhost*|*127.0.0.1*|http://*) echo "local or cleartext origins are forbidden in the release build" >&2; exit 1 ;;
esac

export ANDROID_HOME="${ANDROID_HOME:-/home/ubuntu/android-sdk}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/build-tools/35.0.0:$PATH"

cd "$ROOT_DIR"
pnpm install --no-frozen-lockfile
VITE_API_BASE_URL="$SITE_ORIGIN" pnpm --dir artifacts/hydroguard run build

cd "$MOBILE_DIR"
npm install --no-fund --no-audit
if [ ! -d android ]; then
  npx cap add android
fi
rm -rf www
cp -R "$ROOT_DIR/artifacts/hydroguard/dist/public" www
sed -i "s|__HYDROGUARD_API_BASE__|$SITE_ORIGIN|g" www/simulator.html
npx cap sync android
cd android
./gradlew assembleDebug --no-daemon
cp app/build/outputs/apk/debug/app-debug.apk "$MOBILE_DIR/HydroGuard-debug.apk"

printf 'Built %s\n' "$MOBILE_DIR/HydroGuard-debug.apk"
