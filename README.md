# Amazon Price Tracker & Refund Assistant

A local ledger for purchases and later price checks. Phase 1 stores data on this computer, loads six labeled sample orders, and compares those samples when you press **Check prices**.

It does not log into Amazon, does not store an Amazon password, and does not call Keepa. A lower price is an estimate. Amazon does not generally guarantee a post-purchase price adjustment, and this app will not submit a return, a reorder, or a refund request.

## This environment

Phase 1 was built and tested on Linux x86_64 (Python 3.12, Node 22). It was not run on a Mac, so the Keychain path, macOS notification banners, launchd, and the `.app` package are present as source and were not executed here. The Tauri window targets Apple Silicon and Intel Macs (`macOS 12+`) and still needs a Mac to compile.

## Run it

```sh
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e "./backend[dev]"
npm --prefix frontend install
chmod +x scripts/dev.sh scripts/test.sh
scripts/dev.sh
```

Open http://127.0.0.1:5173 . The API listens on http://127.0.0.1:8787 and refuses any other bind address. The database defaults to `~/.local/share/amazon-price-tracker/`.

In the app, open Settings and choose **Load sample orders**, then **Check prices**. The sample banner stays up so those rows are not mistaken for an account.

## Tests

```sh
scripts/test.sh
```

That runs the Python tests, the interface unit tests, and the production build of the interface.

## What is stored

Orders, price checks, notices, and settings live in SQLite. A Keepa key, if you save one, goes to the macOS Keychain or to an encrypted file mode `0600`. It is not written into SQLite and it is not sent anywhere in this version. Deleting purchase data asks you to type `DELETE PURCHASE DATA` and leaves the key in place.

## Later phases

Order import, a real price provider under that provider's rate limit, refund drafts you can edit, and macOS banners are not in this build. See `docs/API_LIMITATIONS.md`, `docs/ARCHITECTURE.md`, and `docs/SECURITY.md`.

The launchd file in `packaging/macos/` is disabled. Nothing installs it.
