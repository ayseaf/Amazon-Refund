-- Phase 2. Live amazon.com reads. No password, card, cookie, or address columns.

PRAGMA foreign_keys = OFF;

CREATE TABLE amazon_connections_v2 (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    marketplace TEXT NOT NULL DEFAULT 'amazon.com',
    method TEXT NOT NULL CHECK (method IN ('not_connected', 'order_export', 'official_api', 'browser_session')),
    status TEXT NOT NULL CHECK (status IN ('disconnected', 'pending_authorization', 'authorized', 'revoked', 'error')),
    display_label TEXT,
    authorized_at TEXT,
    last_sync_at TEXT,
    last_sync_status TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT INTO amazon_connections_v2 (
    id, profile_id, marketplace, method, status, display_label, authorized_at,
    last_sync_at, last_sync_status, last_error, created_at, updated_at
)
SELECT
    id, profile_id, marketplace, method, status, display_label, authorized_at,
    last_sync_at, last_sync_status, last_error, created_at, updated_at
FROM amazon_connections;

DROP TABLE amazon_connections;
ALTER TABLE amazon_connections_v2 RENAME TO amazon_connections;

CREATE TABLE orders_v2 (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    connection_id TEXT REFERENCES amazon_connections(id) ON DELETE SET NULL,
    amazon_order_id TEXT NOT NULL,
    purchased_at TEXT NOT NULL,
    order_status TEXT,
    currency TEXT NOT NULL DEFAULT 'USD',
    shipping_amount_cents INTEGER NOT NULL DEFAULT 0 CHECK (shipping_amount_cents >= 0),
    tax_amount_cents INTEGER NOT NULL DEFAULT 0 CHECK (tax_amount_cents >= 0),
    order_total_cents INTEGER CHECK (order_total_cents IS NULL OR order_total_cents >= 0),
    ship_to_region TEXT,
    source TEXT NOT NULL CHECK (source IN ('sample', 'order_export', 'official_api', 'amazon_browser')),
    imported_at TEXT NOT NULL,
    UNIQUE (profile_id, amazon_order_id)
);

INSERT INTO orders_v2 (
    id, profile_id, connection_id, amazon_order_id, purchased_at, order_status,
    currency, shipping_amount_cents, tax_amount_cents, order_total_cents,
    ship_to_region, source, imported_at
)
SELECT
    id, profile_id, connection_id, amazon_order_id, purchased_at, order_status,
    currency, shipping_amount_cents, tax_amount_cents, order_total_cents,
    ship_to_region, source, imported_at
FROM orders;

DROP TABLE orders;
ALTER TABLE orders_v2 RENAME TO orders;

CREATE INDEX idx_orders_profile_purchased ON orders (profile_id, purchased_at);

ALTER TABLE order_items ADD COLUMN delivery_at TEXT;
ALTER TABLE order_items ADD COLUMN fulfilled_by TEXT;

CREATE TABLE amazon_session_meta (
    profile_id TEXT PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    marketplace TEXT NOT NULL DEFAULT 'amazon.com' CHECK (marketplace = 'amazon.com'),
    status TEXT NOT NULL CHECK (status IN ('signed_out', 'awaiting_user', 'signed_in', 'challenge', 'error')),
    saved_at TEXT,
    last_scan_started_at TEXT,
    last_scan_finished_at TEXT,
    last_scan_status TEXT,
    last_challenge TEXT,
    last_error TEXT,
    cookie_count INTEGER CHECK (cookie_count IS NULL OR cookie_count >= 0),
    updated_at TEXT NOT NULL
);

CREATE TABLE amazon_scan_runs (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (status IN (
        'running', 'succeeded', 'challenge', 'failed', 'rate_limited', 'skipped', 'signed_out'
    )),
    pages_read INTEGER NOT NULL DEFAULT 0 CHECK (pages_read >= 0),
    orders_seen INTEGER NOT NULL DEFAULT 0 CHECK (orders_seen >= 0),
    challenge_kind TEXT,
    message TEXT,
    next_eligible_at TEXT
);

CREATE TABLE item_verdicts (
    id TEXT PRIMARY KEY,
    order_item_id TEXT NOT NULL REFERENCES order_items(id) ON DELETE CASCADE,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    verdict TEXT NOT NULL CHECK (verdict IN (
        'return_possible', 'price_adjustment_ask_support', 'not_eligible', 'unknown'
    )),
    label TEXT NOT NULL,
    rule TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    missing_json TEXT NOT NULL DEFAULT '[]',
    policy_text TEXT NOT NULL,
    policy_url TEXT,
    potential_savings_cents INTEGER,
    savings_note TEXT NOT NULL,
    not_guaranteed INTEGER NOT NULL DEFAULT 1 CHECK (not_guaranteed = 1),
    draft_kind TEXT CHECK (draft_kind IS NULL OR draft_kind IN ('price_adjustment_message', 'return_steps')),
    draft_text TEXT,
    computed_at TEXT NOT NULL
);

CREATE INDEX idx_item_verdicts_profile ON item_verdicts (profile_id, computed_at);

CREATE TABLE review_gaps (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    amazon_order_id TEXT,
    title TEXT,
    label TEXT NOT NULL,
    missing_json TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_review_gaps_profile ON review_gaps (profile_id, created_at);

PRAGMA foreign_keys = ON;
