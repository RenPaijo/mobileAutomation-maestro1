#!/bin/sh
# CI helper: install the demo APK and run the Maestro suite with retries.
#
# Must be called as a SINGLE line from the android-emulator-runner `script:`
# block (e.g. `sh tools/maestro_test_retry.sh`), because that runner executes
# every script line via a separate `/usr/bin/sh -c` call, so multi-line shell
# constructs (until/for/if blocks) cannot be written inline in the workflow.
#
# Retries exist because the Maestro Android driver handshake is flaky on
# slow CI emulators (AndroidDriverTimeoutException on a cold device); the
# first attempt warms things up and a later attempt usually connects.

export PATH="$HOME/.maestro/bin:$PATH"

adb install Maestro/apps/mda-2.2.0-25.apk

ATTEMPT=1
until maestro test --format JUNIT --output report.xml Maestro/flows; do
  if [ "$ATTEMPT" -ge 3 ]; then
    echo "Maestro still failing after 3 attempts"
    exit 1
  fi
  ATTEMPT=$((ATTEMPT+1))
  echo "Maestro attempt failed (often flaky driver startup on CI), retrying ($ATTEMPT/3)..."
  adb reconnect || true
  sleep 20
done
