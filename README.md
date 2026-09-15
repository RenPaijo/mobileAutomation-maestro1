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
│       ├── 04_login.yaml
│       └── helpers/
│           ├── launch_app.yaml
│           └── login.yaml
├── tools/
│   ├── maestro_junit_to_allure.py   # JUnit XML -> Allure results (stdlib only)
│   └── maestro_test_retry.sh        # install APK + run suite with 3x retry (single-line call: the emulator runner executes each workflow script line separately)
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
maestro check-syntax Maestro/flows/04_login.yaml
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
| `helpers/login.yaml` | Reusable login submit; expects the Login screen visible, credentials via `LOGIN_USER` / `LOGIN_PASS` env (defaults `bob@example.com` / `10203040`) |
| `01_smoke_launch.yaml` | Launch, wait for `Sauce Labs Backpack`, assert `Products` catalog, screenshot |
| `02_add_to_cart.yaml` | Tap first product image (`productIV`) to open detail, tap `Add To Cart`, open cart via `id: .../cartIV`, assert cart, screenshot |
| `03_checkout_e2e.yaml` | Add to cart → `Proceed To Checkout` → `helpers/login.yaml` → checkout/address step |
| `04_login.yaml` | Login case: reach Login via cart → checkout → `helpers/login.yaml` → assert checkout/address screen, screenshot |

Override login without editing any flow (applies to the case and the helper):

```bash
maestro test -e LOGIN_USER=bob@example.com -e LOGIN_PASS=10203040 Maestro/flows/04_login.yaml
```

> Notes (verified against live `uiautomator` hierarchy on emulator, API 34):
> - Cart icon `com.saucelabs.mydemoapp.android:id/cartIV` is present and working.
> - Product titles (`titleTV`, e.g. `Sauce Labs Backpack`) are NOT clickable — tap the product image instead (`id: .../productIV`, `index: 0` for the first product) to open the detail screen. Tapping the title text does nothing and the flow will time out waiting for `Add to cart`.

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
