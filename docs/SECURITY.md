# Security

- The API listens on loopback and refuses any other bind address.
- Requests whose client address is not local are rejected.
- Amazon passwords are rejected by name. There is no password field.
- Card numbers are not a concept in the schema.
- Secret values are encrypted at rest off macOS, and they are redacted if a log line is shaped like `api_key=...` or `Authorization: Bearer ...`.
- Logs record counts and setting names, not product titles and not secret values.
- Purchase delete requires the exact phrase `DELETE PURCHASE DATA`. It removes orders, checks, and notices. It leaves keys in place so a delete of the ledger is not also a silent delete of a credential. Keys have their own remove control.
- Sample product links use `example.invalid`. The app does not request them.
- Order history is not sent to a third party by this version, because this version makes no outbound price or account request.
- A Keepa key entered in Settings is still a secret. Do not commit `.env` files, database files, or the data directory.
