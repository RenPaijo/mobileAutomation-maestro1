# Maestro Mobile Automation — andro_1

Maestro-based mobile automation for Android, tested against the Sauce Labs MyDemoApp demo APK.

- App under test: `Maestro/apps/mda-2.2.0-25.apk`
- Package (`appId`): `com.saucelabs.mydemoapp.android` (v2.2.0, `versionCode` 25)
- Default test credentials (MyDemoApp): `bob@example.com` / `10203040`
- Maestro CLI verified: `2.10.0`

## Project structure

```text
.
├── Maestro/
│   ├── apps/
│   │   └── mda-2.2.0-25.apk
│   └── flows/
│       ├── 01_smoke_launch.yaml
│       ├── 02_add_to_cart.yaml
│       ├── 03_checkout_e2e.yaml
│       └── helpers/
│           └── launch_app.yaml
├── tools/
│   └── maestro_junit_to_allure.py   # JUnit XML -> Allure results (stdlib only)
├── .github/
│   └── workflows/
│       ├── maestro-local.yml   # emulator runner, no API key needed
│       └── maestro-cloud.yml   # Maestro Cloud, needs API key secret
├── .gitignore
└── README.md
```

## Prerequisites

- Maestro CLI (`maestro --version`)
- Java 17+ (`java -version`)
- Android SDK + emulator or a physical device (`adb devices`)
- The demo APK is already committed under `Maestro/apps/`

## Run locally

Start an emulator (or connect a device):

```bash
maestro start-device
# or
maestro list-devices
adb devices
```

Install the app (flows also use `launchApp` with `clearState: true`):

```bash
adb install Maestro/apps/mda-2.2.0-25.apk
```

Validate flow syntax:

```bash
maestro check-syntax Maestro/flows/01_smoke_launch.yaml
maestro check-syntax Maestro/flows/02_add_to_cart.yaml
maestro check-syntax Maestro/flows/03_checkout_e2e.yaml
```

Run a single flow or the whole suite:

```bash
maestro test Maestro/flows/01_smoke_launch.yaml
maestro test Maestro/flows
```

JUnit report:

```bash
maestro test --format JUNIT --output report.xml Maestro/flows
```

## Reporting with Allure

Maestro has no native Allure output, so this repo converts the JUnit XML
into Allure result files with `tools/maestro_junit_to_allure.py`
(Python stdlib only — statuses, failure messages/traces, device properties,
flow-matched screenshots, `environment.xml`, and `executor.json`).

Install the Allure CLI once (any one):

```bash
npm install -g allure-commandline
# or: scoop install allure
```

Generate and view a report locally:

```bash
maestro test --format JUNIT --output report.xml Maestro/flows

python tools/maestro_junit_to_allure.py \
  --junit report.xml \
  --out allure-results \
  --screenshots ~/.maestro/tests \
  --env "device=pixel_6 (API 33)" \
  --env "branch=main"

allure serve allure-results
# or: allure generate allure-results --clean -o allure-report
```

In CI, both workflows already do this automatically and upload
`report.xml`, `allure-results/`, and `allure-report/` as artifacts
(`maestro-allure-report`, `maestro-cloud-allure-report`).

Debug selectors:

```bash
maestro studio
maestro hierarchy
```

## Flows

| Flow | Purpose |
|---|---|
| `helpers/launch_app.yaml` | Reusable launch with `clearState: true` / `stopApp: true` |
| `01_smoke_launch.yaml` | Launch, wait for `Sauce Labs Backpack`, assert `Products` catalog, screenshot |
| `02_add_to_cart.yaml` | Open product detail, tap `Add To Cart`, open cart via `id: .../cartIV`, assert cart, screenshot |
| `03_checkout_e2e.yaml` | Add to cart → `Proceed To Checkout` → login via `env` (`LOGIN_USER` / `LOGIN_PASS`) → reach checkout/address step |

Override login without editing the flow:

```bash
maestro test -e LOGIN_USER=bob@example.com -e LOGIN_PASS=10203040 Maestro/flows/03_checkout_e2e.yaml
```

> Note: the cart icon selector (`com.saucelabs.mydemoapp.android:id/cartIV`) was written without a live hierarchy. If it fails, run `maestro studio` / `maestro hierarchy` and replace it with the visible `contentDescription` or text match (e.g. `tapOn: ".*Cart.*"`).

## CI (GitHub Actions)

Two workflows are included:

- `maestro-local.yml` — runs on `push` to `main`, PRs, and manual dispatch. Provisions a `pixel_6` emulator (API 33), installs the APK, runs `check-syntax`, then `maestro test Maestro/flows`, converts the JUnit output to Allure results, and generates the HTML report. Uploads `report.xml`, `allure-results/`, and `allure-report/` as the `maestro-allure-report` artifact. No secrets required.
- `maestro-cloud.yml` — runs on `push` to `main`, manual dispatch, and nightly (`0 1 * * *`). Uploads the APK + `Maestro/flows` to Maestro Cloud with JUnit output (`report-cloud.xml`), then converts and generates the Allure report (`maestro-cloud-allure-report` artifact).

Required secrets for the Cloud workflow (Settings > Secrets > Actions):

- `MAESTRO_CLOUD_API_KEY` (required)
- `MAESTRO_CLOUD_PROJECT_ID` (optional — remove the `--projectId` flag if unused)

## Troubleshooting

- `adb devices` empty: start an emulator (`maestro start-device`) or enable USB debugging on a device.
- `check-syntax` passes but `tapOn` fails: element text differs by app version — inspect with `maestro hierarchy` and update the regex.
- Cloud workflow exits with `MAESTRO_CLOUD_API_KEY belum diset`: add the secret, then re-run.
- Large binary warning: the APK (~17 MB) is intentionally committed so CI can `adb install` it.
