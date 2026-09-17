#!/bin/sh
# CI helper: install the demo APK and run each top-level Maestro flow with
# bounded retries.
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
FLOW_FAILED=0

FLOWS="Maestro/flows/01_smoke_launch.yaml
Maestro/flows/02_add_to_cart.yaml
Maestro/flows/03_checkout_e2e.yaml
Maestro/flows/04_login.yaml"

adb wait-for-device
adb shell 'while [ "$(getprop sys.boot_completed)" != "1" ]; do sleep 2; done' || true

for flow in $FLOWS; do
  flow_name=$(basename "$flow" .yaml)
  report="report-${flow_name}.xml"
  flow_passed=0

  for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    echo "Starting $flow_name attempt $attempt/$MAX_ATTEMPTS"
    rm -f "$report"

    # Reinstall/reset on every attempt. adb reconnect alone does not reset a
    # stale app or Maestro driver session after a failed run.
    adb install -r "$APK"
    adb shell am force-stop "$PACKAGE" || true
    adb shell pm clear "$PACKAGE" || true

    # A flow/driver hang used to make each retry run until the job timed out.
    timeout --signal=TERM --kill-after=30s 8m \
      maestro test --format JUNIT --output "$report" "$flow"
    status=$?

    if [ "$status" -eq 0 ]; then
      echo "$flow_name completed successfully on attempt $attempt"
      flow_passed=1
      break
    fi

    echo "$flow_name attempt $attempt failed (exit $status)"
    adb devices || true
    adb logcat -d -t 300 > "adb-log-${flow_name}-attempt-${attempt}.txt" || true

    if [ "$attempt" -lt "$MAX_ATTEMPTS" ]; then
      adb reconnect || true
      sleep 20
    fi
  done

  if [ "$flow_passed" -ne 1 ]; then
    echo "$flow_name failed after $MAX_ATTEMPTS attempts"
    FLOW_FAILED=1
  fi
done

if [ "$FLOW_FAILED" -ne 0 ]; then
  exit 1
fi
