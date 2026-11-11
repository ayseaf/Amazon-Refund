# Architecture

The first version is one local user on one computer. The seams below are where a later hosted service can grow without replacing the ledger.

## Processes

- `backend/` is a FastAPI app bound to `127.0.0.1`. It owns SQLite, settings, and secret storage.
- `frontend/` is a React interface. In development, Vite proxies `/api` to the local app.
- `src-tauri/` is the macOS window. It loads the interface and expects the API on port 8787. It was not compiled in the Linux environment where Phase 1 was built.

## Data

Every order is stored under a `user_id`. The local install uses `local`. Queries filter on that id, which is the later account boundary. Money is integer cents. A snapshot records the source, whether the seller and condition matched, and the compared total. A different seller or condition is stored and is not added to estimated savings.

Secrets are not columns in SQLite. On macOS the store is Keychain via the `security` command. Elsewhere it is a Fernet file created mode `0600`. The API can say that a key exists. It does not return the value.

## Providers and scheduling

`decide_run` is the rule for a future scheduler: do not start a second run while one is in progress, and do not start again before the interval. Phase 1 does not start a timer and does not install launchd. The plist under `packaging/macos/` is disabled and is not loaded by any script.

Sample checks are an in-process table. There is no HTTP client on that path. A non-sample row is skipped with a reason, including when a Keepa key is already stored.

## Notifications

Price drops at or above the threshold are written to the local `notifications` table once per item and total. A second check of the same total does not add another row. Nothing is sent to Notification Center, email, or Telegram.

## What a later service would replace

The host binding, the single local user, the file secret store, and the "not called" price provider can be swapped without changing the order and snapshot tables. Billing is intentionally absent.
