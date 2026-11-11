-- Phase 1 schema. Forward-only. No credential, card, or secret-value columns.

CREATE TABLE profiles (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE settings (
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (profile_id, key)
);

CREATE TABLE notification_preferences (
    profile_id TEXT PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    desktop_enabled INTEGER NOT NULL DEFAULT 1 CHECK (desktop_enabled IN (0, 1)),
    email_enabled INTEGER NOT NULL DEFAULT 0 CHECK (email_enabled IN (0, 1)),
    telegram_enabled INTEGER NOT NULL DEFAULT 0 CHECK (telegram_enabled IN (0, 1)),
    min_savings_cents INTEGER NOT NULL DEFAULT 500 CHECK (min_savings_cents >= 0),
    notify_price_decrease INTEGER NOT NULL DEFAULT 1 CHECK (notify_price_decrease IN (0, 1)),
    notify_savings INTEGER NOT NULL DEFAULT 1 CHECK (notify_savings IN (0, 1)),
    notify_return_deadlines INTEGER NOT NULL DEFAULT 1 CHECK (notify_return_deadlines IN (0, 1)),
    notify_price_check_failures INTEGER NOT NULL DEFAULT 1 CHECK (notify_price_check_failures IN (0, 1)),
    notify_refund_status INTEGER NOT NULL DEFAULT 1 CHECK (notify_refund_status IN (0, 1)),
    notify_monitoring_unavailable INTEGER NOT NULL DEFAULT 1 CHECK (notify_monitoring_unavailable IN (0, 1)),
    updated_at TEXT NOT NULL
);

CREATE TABLE amazon_connections (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    marketplace TEXT NOT NULL DEFAULT 'amazon.com',
    method TEXT NOT NULL CHECK (method IN ('not_connected', 'order_export', 'official_api')),
    status TEXT NOT NULL CHECK (status IN ('disconnected', 'pending_authorization', 'authorized', 'revoked', 'error')),
    display_label TEXT,
    authorized_at TEXT,
    last_sync_at TEXT,
    last_sync_status TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE orders (
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
    source TEXT NOT NULL CHECK (source IN ('sample', 'order_export', 'official_api')),
    imported_at TEXT NOT NULL,
    UNIQUE (profile_id, amazon_order_id)
);

CREATE TABLE order_items (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    asin TEXT,
    title TEXT NOT NULL,
    product_url TEXT,
    seller_name TEXT,
    condition TEXT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    item_shipping_cents INTEGER NOT NULL DEFAULT 0 CHECK (item_shipping_cents >= 0),
    item_tax_cents INTEGER NOT NULL DEFAULT 0 CHECK (item_tax_cents >= 0),
    variation_json TEXT,
    return_eligible INTEGER CHECK (return_eligible IS NULL OR return_eligible IN (0, 1)),
    return_deadline_at TEXT,
    monitoring_status TEXT NOT NULL DEFAULT 'not_monitored'
        CHECK (monitoring_status IN (
            'not_monitored', 'eligible', 'monitoring', 'paused', 'unavailable', 'ineligible'
        )),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE price_observations (
    id TEXT PRIMARY KEY,
    order_item_id TEXT NOT NULL REFERENCES order_items(id) ON DELETE CASCADE,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    observed_at TEXT NOT NULL,
    source TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    shipping_cents INTEGER NOT NULL DEFAULT 0 CHECK (shipping_cents >= 0),
    currency TEXT NOT NULL DEFAULT 'USD',
    seller_name TEXT,
    condition TEXT,
    offer_notes TEXT,
    is_equivalent_offer INTEGER NOT NULL DEFAULT 1 CHECK (is_equivalent_offer IN (0, 1)),
    coupon_cents INTEGER NOT NULL DEFAULT 0 CHECK (coupon_cents >= 0)
);

CREATE TABLE price_check_runs (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    order_item_id TEXT REFERENCES order_items(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (status IN (
        'queued', 'running', 'succeeded', 'failed', 'rate_limited', 'skipped'
    )),
    source TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT,
    next_eligible_at TEXT
);

CREATE TABLE savings_estimates (
    id TEXT PRIMARY KEY,
    order_item_id TEXT NOT NULL REFERENCES order_items(id) ON DELETE CASCADE,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    computed_at TEXT NOT NULL,
    purchase_price_cents INTEGER NOT NULL CHECK (purchase_price_cents >= 0),
    current_price_cents INTEGER NOT NULL CHECK (current_price_cents >= 0),
    estimated_savings_cents INTEGER NOT NULL,
    fees_cents INTEGER NOT NULL DEFAULT 0 CHECK (fees_cents >= 0),
    confidence TEXT NOT NULL CHECK (confidence IN ('sample', 'low', 'medium', 'high')),
    explanation TEXT NOT NULL,
    is_guaranteed INTEGER NOT NULL DEFAULT 0 CHECK (is_guaranteed = 0)
);

CREATE TABLE refund_requests (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    order_item_id TEXT NOT NULL REFERENCES order_items(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN (
        'draft', 'ready_for_review', 'submitted', 'pending', 'accepted', 'denied', 'withdrawn'
    )),
    requested_amount_cents INTEGER CHECK (requested_amount_cents IS NULL OR requested_amount_cents >= 0),
    confirmed_refund_cents INTEGER CHECK (confirmed_refund_cents IS NULL OR confirmed_refund_cents >= 0),
    draft_message TEXT,
    user_edited_message TEXT,
    policy_note TEXT NOT NULL DEFAULT 'Amazon does not generally guarantee post-purchase price matching. A refund is not guaranteed.',
    submitted_at TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    submission_method TEXT CHECK (submission_method IS NULL OR submission_method = 'manual_user')
);

CREATE TABLE refund_events (
    id TEXT PRIMARY KEY,
    refund_request_id TEXT NOT NULL REFERENCES refund_requests(id) ON DELETE CASCADE,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    occurred_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    note TEXT
);

CREATE TABLE notifications (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    dedupe_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    delivered_at TEXT,
    channel TEXT NOT NULL DEFAULT 'desktop',
    UNIQUE (profile_id, dedupe_key)
);

CREATE TABLE secret_refs (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    backend TEXT NOT NULL CHECK (backend IN ('keychain', 'encrypted_file', 'env')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (profile_id, name)
);

CREATE TABLE task_reservations (
    profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    task_key TEXT NOT NULL,
    locked_until TEXT NOT NULL,
    owner TEXT NOT NULL,
    PRIMARY KEY (profile_id, task_key)
);

CREATE TABLE audit_log (
    id TEXT PRIMARY KEY,
    profile_id TEXT,
    occurred_at TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    detail TEXT
);

CREATE INDEX idx_orders_profile_purchased ON orders (profile_id, purchased_at);
CREATE INDEX idx_order_items_profile ON order_items (profile_id);
CREATE INDEX idx_order_items_asin ON order_items (asin);
CREATE INDEX idx_price_obs_item_time ON price_observations (order_item_id, observed_at);
CREATE INDEX idx_refund_requests_profile_status ON refund_requests (profile_id, status);
CREATE INDEX idx_notifications_profile ON notifications (profile_id, created_at);
