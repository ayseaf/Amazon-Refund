# Amazon Price Tracker & Refund Assistant

Independent local tool for reading orders you already placed on amazon.com, comparing public prices, and preparing notes for you to review. It is not affiliated with Amazon. It does not submit orders, returns, refund requests, or customer-service messages.

Phase 2 adds a sign-in window that you use yourself, a read-only review of the last 30 days, and an eligibility verdict for each item. Sample rows remain on screen and stay labeled **Sample data**. Rows from a review on your Mac are labeled **Live from Amazon**. A refund is not guaranteed.

This repository was developed and tested against redacted HTML fixtures. The cloud agent does not have your Amazon password, cookies, or session, and those values are not in git.

## Sign in on your Mac

Amazon does not offer a public API for a buyer's own purchase history. The Selling Partner Orders API is for sellers, not for a personal account. This app does not ask for your Amazon password and it does not type into Amazon's form.

You sign in yourself:

1. Install the tools under "Install on your Mac", then install the Python package with the `amazon` extra and Chromium:

```bash
python3.12 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -e "./backend[dev,amazon]"
python -m playwright install chromium
pnpm --dir frontend install
cp .env.example .env
```

2. Generate a Fernet key and put it in `.env` as `TRACKER_SECRET_KEY`. The session cookies are encrypted with that key (or with the macOS Keychain when `TRACKER_SECRET_BACKEND=keychain`). Leave the key blank and the secret store stays locked, so a session cannot be saved.

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

3. Start the app from the repository root:

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh
```

4. Open `http://127.0.0.1:1420`. Go to **Settings** and press **Open Amazon sign-in**.

5. A normal Chromium window opens on amazon.com's sign-in page. Type your email, password, and any MFA or one-time code in that window. This app has no password field and does not read the one you type.

6. When Amazon shows your orders, the app stores the amazon.com session cookies in the encrypted secret store and closes the temporary browser profile. The cookies stay on this computer. They are not written to SQLite in plain text and they are not sent anywhere else.

7. Press **Review orders from the last 30 days**. The app opens order history, then each order detail, then each product page. It waits a random 4 to 8 seconds between pages. It will not start another full review until an hour has passed. It only reads. It never clicks buy, return, checkout, or contact.

8. Read the verdicts under **Amazon Orders** and **Opportunities**. Draft text is for you to edit. You submit anything yourself on Amazon after you decide to. Pressing nothing in this app does not contact Amazon's customer service.

9. Press **Sign out / delete Amazon session** to wipe the encrypted cookies. **Delete stored purchase data** still removes orders, prices, and verdicts from SQLite and does not remove the sample illustrations.

If Amazon shows a CAPTCHA, an unusual-activity page, or a rate-limit page during a review, the run stops on that page so you can see it. The app records the kind of page and does not try to get around it. During sign-in, a verification-code page stays on screen for you to complete. The app does not read or enter the code.

Keepa is not called in this phase. A stored Keepa key is unused until a later phase, after you confirm that plan's token rate. Prices in a live review come from the public product page.

## What the review stores

For orders placed in the last 30 days, when the page shows them:

- Order ID and order date
- ASIN, title, product URL, quantity, and price paid
- Seller and fulfilled-by
- Condition, delivery date, and the return-window end date

Addresses, payment instruments, and the Amazon password are not stored.

Each item gets one verdict:

| Verdict | Rule |
| --- | --- |
| Return possible | The order shows the item is returnable and today is still on or before the return-window end. If the current price is lower, the screen shows the item-price difference. Shipping, tax, and restocking are included only when the page showed them. |
| Price adjustment: ask support | The current price is lower and the item is not inside a shown return window. The label says this is not guaranteed. Amazon does not generally offer automatic price protection. |
| Not eligible | The window has ended, the item is not returnable, or there is no price drop. |
| Unknown | A fact needed for the verdict was not on the page. The screen names the missing fact. |

## What this version does not do

- It does not submit a return, order, purchase, refund claim, or customer-service message.
- It does not mark a refund as guaranteed or automatic.
- It does not bypass CAPTCHA, MFA, rate limits, or other Amazon controls.
- It does not send order history to a third party.
- It does not store a card.
- It does not run a background launchd agent. The plist under `packaging/macos/` is still disabled.
- It was not packaged as a Mac `.app` here. The Tauri project is configured.

If a live page does not match the parser, the review says so and does not invent orders or prices.

## This environment

Phase 2 was assembled and tested on a Linux x86_64 cloud VM, not on a Mac, and not with a real Amazon account.

| Tool | Found here |
| --- | --- |
| Python | 3.12 |
| Node.js | 22 |
| pnpm | 10 |

macOS Keychain, a visible Chromium window, and the `.app` bundle were not exercised here. On Linux and in CI the secret store is an encrypted file. On a Mac, `TRACKER_SECRET_BACKEND=auto` selects Keychain. The Keychain value is passed to the `security` command, so it can appear briefly in the local process list. It is not written to the log.

## Install on your Mac

These are the tools to install on an Apple Silicon Mac (including a MacBook Pro M3 or a Mac Mini M4). macOS 13 or newer is the floor set in the Tauri config.

1. Xcode Command Line Tools: `xcode-select --install`
2. Python 3.12 or newer, from [python.org](https://www.python.org/downloads/macos/) or Homebrew (`brew install python@3.12`).
3. Node.js 22 or newer, then pnpm 10: `corepack enable && corepack prepare pnpm@10.33.4 --activate`
4. Rust via [rustup](https://rustup.rs/), current stable, only if you want to compile the Tauri shell. The app runs in the browser without it.
5. Chromium for Playwright, from the `playwright install chromium` command above. That download is the visible window. It is not a hidden browser.

You do not install an Amazon password anywhere.

## Run it without signing in

The API still starts with no Amazon session. Sample data stays on screen.

```bash
source backend/.venv/bin/activate
tracker-api
```

```bash
pnpm --dir frontend dev
```

Open `http://127.0.0.1:1420`. The API listens on `127.0.0.1:8787` only.

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

Parser tests use the HTML files in `backend/tests/fixtures/amazon/`. Those pages are synthetic. Personal data in them is the literal text `ADDRESS REDACTED`. They are not a recording of a real account.

## Data and secrets

The database file defaults to `./data/tracker.sqlite`. The directory is mode `0700` and the file is mode `0600`. Purchase history is not encrypted at rest. Session cookies are encrypted in the secret store, not stored as plain text in SQLite.

Money is stored as integer cents. A savings row cannot be marked guaranteed. A refund submission method can only be empty or `manual_user`. This version does not create a submitted refund.

The only secret names are `keepa_api_key`, stored if you add one, and `amazon_session`, written only by the sign-in flow. The generic secrets endpoint rejects an uploaded session and rejects anything named like a password or a card.

Logs pass through a redaction filter for passwords, bearer tokens, and cookie assignments. Deleting purchase data requires the header `X-Confirm-Delete: DELETE-PURCHASE-DATA`. The Settings screen asks you to type `DELETE` first.

## Sample clock

Sample return deadlines are calculated from 11 November 2026 so the examples stay stable. Dashboard sample totals are still the fictional illustration:

- 5 products illustrated as monitored
- $31.00 estimated price gap
- $10.00 sample confirmed refund
- 1 pending sample request

Those numbers are not from an Amazon account.

## External APIs and cost

**Your Amazon orders.** Read-only pages on `www.amazon.com` after you sign in yourself. No fee from this app. Amazon can show a CAPTCHA or throttle the browser. This app stops when that happens. One full order review per hour, one page at a time, with a delay of several seconds.

**Keepa.** Not called. Keepa's API documentation describes a token bucket. Official reference: [Keepa plans and tokens](https://keepa.com/api-docs/plans-tokens.html). Third-party summaries in late 2026 listed a starter plan around €49 per month for 20 tokens per minute. Those euro figures are not copied from a Keepa checkout page. Read the current price on Keepa's own pricing page before buying anything.

No other price provider is configured. There is no Amazon Product Advertising API integration.

## Layout

```text
backend/src/tracker     Python package: API, schema, secrets, Amazon review
backend/tests/fixtures  Synthetic Amazon HTML with personal data removed
frontend/src            React + TypeScript interface
src-tauri               Tauri 2 shell config
packaging/macos         Disabled launchd template
scripts/dev.sh          API plus Vite
```

## Security choices already in force

- The API binds to loopback.
- CORS allows only the Vite origin and the Tauri origins.
- No password field for Amazon. The password is not read, logged, or stored.
- Session cookies are encrypted. Sign-out deletes them.
- The browser is sent only to read-only amazon.com order and product URLs.
- Logs and SQLite do not receive cookie values or the password.
- Sample rows and live rows use different labels.
- Email and Telegram toggles stay off.

## Open questions

1. Should the SQLite file be encrypted (for example SQLCipher) before you review a real account? Session cookies are encrypted. Order rows are protected by file permissions only.
2. Is `~/Library/Application Support/Amazon Price Tracker/` the right place for the database on your Mac? The default is `./data/tracker.sqlite` in the repository.
3. If Amazon changes the order-page markup, the parser will report that it found nothing instead of guessing. A redacted copy of a current page, with address and payment removed by you, would show whether the selectors still match.
4. Do you want a later phase to call Keepa when a key is present, or should the product page remain the only price source?
5. The visible window is Playwright Chromium, not the Tauri webview. Say if you want the sign-in window inside the desktop shell instead.
