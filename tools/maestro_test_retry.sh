#!/bin/sh
# CI helper: install the demo APK and run the Maestro suite with bounded retries.
#
# Must be called as a SINGLE line from the android-emulator-runner `script:`
# block (e.g. `sh tools/maestro_test_retry.sh`), because that runner executes
# every script line via a separate `/usr/bin/sh -c` call, so multi-line shell
# constructs (until/for/if blocks) cannot be written inline in the workflow.
#
# Retries exist because the Maestro Android driver handshake can be flaky on
# slow CI emulators. Every attempt is bounded so a hung driver cannot consume
# the whole GitHub Actions job timeout.

set -u

export PATH="$HOME/.maestro/bin:$PATH"

PACKAGE="com.saucelabs.mydemoapp.android"
APK="Maestro/apps/mda-2.2.0-25.apk"
MAX_ATTEMPTS=3
ATTEMPT=1

adb wait-for-device
adb shell 'while [ "$(getprop sys.boot_completed)" != "1" ]; do sleep 2; done' || true

while [ "$ATTEMPT" -le "$MAX_ATTEMPTS" ]; do
  echo "Starting Maestro attempt $ATTEMPT/$MAX_ATTEMPTS"
  rm -f report.xml

  # Reinstall/reset on every attempt. adb reconnect alone does not reset a
  # stale app or Maestro driver session after a failed run.
  adb install -r "$APK"
  adb shell am force-stop "$PACKAGE" || true
  adb shell pm clear "$PACKAGE" || true

  # A flow/driver hang used to make each retry run until the job timed out.
  # Keep the whole suite bounded while retaining the retry behavior.
  timeout --signal=TERM --kill-after=30s 8m \
    maestro test --format JUNIT --output report.xml Maestro/flows
  status=$?

  if [ "$status" -eq 0 ]; then
    echo "Maestro completed successfully on attempt $ATTEMPT"
    exit 0
  fi

  echo "Maestro attempt $ATTEMPT failed (exit $status)"
  adb devices || true
  adb logcat -d -t 300 > "adb-log-attempt-${ATTEMPT}.txt" || true

  if [ "$ATTEMPT" -eq "$MAX_ATTEMPTS" ]; then
    echo "Maestro still failing after $MAX_ATTEMPTS attempts"
    exit "$status"
  fi

  ATTEMPT=$((ATTEMPT+1))
  adb reconnect || true
  sleep 20
done
