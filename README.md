# Amazon Price Tracker & Refund Assistant

Independent local tool for watching prices on purchases you already made and preparing price-adjustment notes for you to review. It is not affiliated with Amazon and it does not submit orders, returns, or refund requests.

This repository is **Phase 1 only**: project structure, SQLite schema, a local FastAPI service, a React interface with seven sections, a Tauri shell config, and tests. The orders on screen are labeled **SAMPLE**. They are fictional. No Amazon account is connected, and a refund is not guaranteed.

## What Phase 1 does

- Creates a SQLite database and applies a forward-only migration.
- Serves health checks and a small local API on `127.0.0.1:8787`.
- Shows seven sections filled with clearly labeled sample data: Dashboard, Amazon Orders, Price Monitoring, Refund Assistant, Returns and Deadlines, Savings History, and Settings.
- Stores non-secret settings in SQLite.
- Stores a Keepa API key, if you add one, in an encrypted file on Linux or in the macOS Keychain on a Mac. The key is never written to SQLite and is never returned by the API.
- Records a skipped price check when you press **Check prices now**. It does not fetch a price and it does not contact Amazon.
- Deletes locally stored purchase rows when you confirm that action. Sample illustrations are not stored in the database, so they remain on screen.
- Refuses Amazon passwords, card numbers, automated refund submission, and any "guaranteed refund" flag.
- Ships a disabled launchd template. Loading it is refused in this phase, and the script it would run exits with an error.

## What Phase 1 does not do

- It does not sign in to Amazon, browse Amazon, or call Amazon APIs.
- It does not import real orders. That is Phase 2, and it needs your approval.
- It does not check live prices. That is Phase 3.
- It does not send a customer-service message, return, or repurchase.
- It does not process payments or store a card.
- It does not install a background agent or build a macOS `.app`. The Tauri project is configured, not packaged.

## This environment

Phase 1 was assembled on a Linux x86_64 cloud VM, not on a Mac.

| Tool | Found here |
| --- | --- |
| Python | 3.12.3 |
| Node.js | 22.23.4 |
| pnpm | 10.33.4 |
| Rust | 1.83.0 |

macOS Keychain, launchd, and the `.app` bundle cannot be built or exercised here. Those pieces sit behind interfaces. On Linux and in CI the secret store is an encrypted file (or a read-only environment variable). On a Mac, `TRACKER_SECRET_BACKEND=auto` selects Keychain.

## Install on your Mac

These are the tools to install on an Apple Silicon Mac (including a MacBook Pro M3 or a Mac Mini M4) before running the app locally. macOS 13 or newer is the floor set in the Tauri config.

1. Xcode Command Line Tools: `xcode-select --install`
2. Python 3.12 or newer, from [python.org](https://www.python.org/downloads/macos/) or Homebrew (`brew install python@3.12`).
3. Node.js 22 or newer, then pnpm 10: `corepack enable && corepack prepare pnpm@10.33.4 --activate`
4. Rust via [rustup](https://rustup.rs/), current stable. The Tauri 2 crates resolved for this phase need Rust 1.90 or newer (their manifests use newer edition features). This VM's preinstalled compiler was 1.83.0, which is too old, so the shell was checked with a stable toolchain installed beside it. Tauri's macOS notes also expect the C compiler from the Xcode tools above.
5. Optional, only when you want the desktop window: the Tauri CLI, `pnpm add -D @tauri-apps/cli` inside `frontend/`, then the steps under "Desktop shell" below. Phase 1 does not bundle the Python API inside the app.

You do not install an Amazon password anywhere. There is no field for one.

## Run it

From the repository root:

```bash
python3.12 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -e "./backend[dev]"
cp .env.example .env
```

Generate a Fernet key and put it in `.env` as `TRACKER_SECRET_KEY` if you want to store a Keepa key. Leave it blank and the API still starts; the secret store stays locked.

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

On a Mac you can instead set `TRACKER_SECRET_BACKEND=keychain` and leave the file key empty. The Keychain service name is `com.local.amazonpricetracker`. The current implementation calls the `security` command. A later phase can switch that to the Security framework. The password is passed as an argument because that is what `security` accepts, so a local user can see it briefly in the process list. It is not written to the log.

For a read-only key in CI or a shell, set `TRACKER_SECRET_BACKEND=env` and `TRACKER_SECRET_VALUE_KEEPA_API_KEY`. That store refuses writes.

Install the interface and start both processes:

```bash
pnpm --dir frontend install
chmod +x scripts/dev.sh
./scripts/dev.sh
```

Open `http://127.0.0.1:1420`. The API listens on `127.0.0.1:8787` only.

To run them separately:

```bash
source backend/.venv/bin/activate
tracker-api
```

```bash
pnpm --dir frontend dev
```

## Tests

```bash
source backend/.venv/bin/activate
pytest
```

Run that from `backend/`, or pass `backend/tests` from the repository root after the editable install.

```bash
pnpm --dir frontend test
pnpm --dir frontend exec tsc --noEmit
```

GitHub Actions runs the same backend and frontend checks on Ubuntu. It does not build the Mac app.

## Desktop shell

`src-tauri/` is a Tauri 2.1 project aimed at an Apple Silicon `.app` and `.dmg`. It was not packaged here. The window loads the Vite app and the app calls the local API. The Python process is not yet embedded. Packaging both together is Phase 6.

`cargo check` completed on this Linux VM with Rust 1.99.1 after the WebKitGTK headers were installed. That only proves the shell compiles. It does not produce the Mac `.app`, and a Mac does not need those Linux libraries.

On a Mac, after the toolchain above is installed and `frontend/dist` can be produced:

```bash
cd src-tauri
cargo check
```

`cargo tauri dev` uses `scripts/dev.sh`, which starts the API and Vite. Before a release build, regenerate the icon set on the Mac with `pnpm --dir frontend exec tauri icon src-tauri/icons/128x128.png` so the bundle gets a real `.icns`. The committed icons are a simple generated mark.

The launchd plist at `packaging/macos/com.local.amazonpricetracker.monitor.plist` is disabled. `install_background_scheduler()` raises an error in Phase 1. Do not copy the plist into `~/Library/LaunchAgents`.

## Data and secrets

The database file defaults to `./data/tracker.sqlite`. The directory is mode `0700` and the file is mode `0600`. Purchase history is not encrypted at rest yet. See the open questions before importing real orders.

Money is stored as integer cents. A savings row cannot be marked guaranteed. A refund submission method can only be empty or `manual_user`.

Settings that are not secrets live in SQLite. The only secret name accepted in this version is `keepa_api_key`. Names that look like a password, card, or Amazon password are rejected.

Logs pass through a redaction filter. Audit rows refuse values that look like `api_key=...` or `Bearer ...`. Price-check and delete routes do not record order identifiers in the purge audit line.

Deleting purchase data requires the header `X-Confirm-Delete: DELETE-PURCHASE-DATA`. The Settings screen asks you to type `DELETE` first. Profiles, settings, and secret references stay. The secret value itself is not in SQLite.

## Sample clock

Sample return deadlines are calculated from 11 November 2026, not from today's date, so the 7-day, 3-day, and 1-day examples stay stable. The screen says so. Dashboard totals are computed from those rows:

- 5 products illustrated as monitored
- $31.00 estimated price gap, excluding the sample row that already has a confirmed amount
- $10.00 sample confirmed refund
- 1 pending sample request

The confirmed amount is a label in the sample. This application did not receive a refund.

Return-and-repurchase math, used for the sample skillet only:

`net = (purchase unit price - current unit price) × quantity + (original tax - repurchase tax) - return shipping - restocking fee - repurchase shipping`

Original outbound shipping is treated as already spent. The result is an estimate. Nothing is submitted.

## External APIs and cost

Phase 1 calls none of these. Notes so the later phases do not invent a source:

**Your Amazon orders.** Amazon does not offer a public API for a buyer's own purchase history. The Selling Partner Orders API is for sellers looking at orders placed with them, not for a personal account. Unofficial libraries that ask for an Amazon password and then read the website are out of scope: this app will not ask for that password, will not store it, and will not bypass CAPTCHA, MFA, or other Amazon controls. Phase 2 should import a file you download yourself while you are logged in.

**Keepa.** Keepa's API documentation describes a token bucket. A plan adds tokens every minute, unused tokens expire after 60 minutes, and a basic product request costs 1 token (more if you ask for offers or other options). Official reference: [Keepa plans and tokens](https://keepa.com/api-docs/plans-tokens.html). Third-party summaries in late 2026 listed a starter plan around €49 per month for 20 tokens per minute. Those euro figures are not copied from a Keepa checkout page. Read the current price on Keepa's own pricing page before buying anything. A personal list of about 30 items, checked once an hour with basic product requests, is a small number of tokens, but offer and coupon data costs more, and Phase 3 has to follow `tokensLeft` rather than a fixed hour. The settings screen rejects intervals shorter than 60 minutes until a provider limit is known.

No other price provider is configured. There is no Amazon Product Advertising API integration. That API is an affiliate catalog, not your order history.

## Layout

```text
backend/src/tracker     Python package: API, schema, secrets, sample data
backend/tests           Unit and integration tests
frontend/src            React + TypeScript interface
src-tauri               Tauri 2 shell config
packaging/macos         Disabled launchd template
scripts/dev.sh          API plus Vite
scripts/macos-scheduler.sh
```

## Security choices already in force

- The API binds to loopback.
- CORS allows only the Vite origin and the Tauri origins.
- No Amazon session, cookie, or password is collected.
- Sample product URLs are null, so the UI does not link out to Amazon.
- Logs and the purge audit avoid secret values and order identifiers.
- Email and Telegram toggles exist in the schema and stay off. Enabling them returns an error.

## Open questions before Phase 2

1. Which file should the importer accept first: an order report you download from Amazon, or a CSV template this app defines? Please share a redacted sample of the real export if you want the mapping based on your file. I will not guess the columns.
2. Is the marketplace amazon.com only?
3. Should the SQLite file be encrypted (for example SQLCipher) before any real order is imported? Phase 1 only locks down file permissions and encrypts secrets.
4. Do you already have a Keepa key, and do you want hourly checks to wait until you confirm that plan's token rate?
5. Is `~/Library/Application Support/Amazon Price Tracker/` the right place for the database on your Mac?
6. Is storing order id, ASIN, title, prices, dates, quantity, seller, condition, and a coarse region acceptable, with street addresses left out?
7. Is a single local profile enough until a later multi-user version?

Phase 2 has not been started.
