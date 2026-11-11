export type DeadlineWindow = "1" | "3" | "7" | "past" | null;

export type Item = {
  id: number;
  asin: string;
  title: string;
  product_url: string;
  quantity: number;
  unit_price_cents: number;
  purchase_total_cents: number;
  shipping_cents: number;
  tax_cents: number;
  seller: string;
  condition: string;
  variation_note: string;
  amazon_order_id: string;
  purchased_on: string;
  currency: string;
  is_sample: boolean;
  order_source: string;
  return_eligible: boolean;
  return_deadline: string | null;
  deadline_window: DeadlineWindow;
  monitoring_status: string;
  price_checked_at: string | null;
  price_source: string | null;
  latest_price_cents: number | null;
  latest_total_cents: number | null;
  savings_cents: number | null;
  comparable: boolean | null;
  difference_label: string;
  stamp_word: string;
  stamp_form: "dashed" | "solid" | "double";
  price_note: string;
  repurchase_estimate_cents: number | null;
};

export type Sync = {
  finished_at: string;
  source: string;
  message: string;
  orders_seen: number;
  amazon_contacted: boolean;
};

export type Dashboard = {
  monitored_count: number;
  estimated_savings_cents: number;
  confirmed_refunds_cents: number;
  pending_refund_requests: number;
  upcoming_return_deadlines: {
    asin: string;
    title: string;
    return_deadline: string | null;
    window: DeadlineWindow;
    is_sample: boolean;
  }[];
  recent_price_changes: {
    asin: string;
    title: string;
    checked_at: string;
    source: string;
    savings_cents: number | null;
    comparable: boolean;
    is_sample: boolean;
    note: string;
  }[];
  last_successful_sync: Sync | null;
  data_mode: string;
  amazon_connected: false;
  disclaimer: string;
};

export type Settings = {
  monitoring_interval_minutes: number;
  notify_min_savings_cents: number;
  notify_price_decreases: boolean;
  notify_return_deadlines: boolean;
  notify_price_check_failures: boolean;
  notify_refund_status: boolean;
  notify_unmonitorable: boolean;
  desktop_notifications: boolean;
  email_notifications: boolean;
  telegram_notifications: boolean;
  restocking_fee_cents: number;
  return_shipping_cents: number;
  email_notifications_available: boolean;
  telegram_notifications_available: boolean;
  desktop_notifications_available: boolean;
  minimum_interval_minutes: number;
};

export type PriceCheck = {
  network_requests: number;
  keepa_called: boolean;
  desktop_delivery: string;
  results: { asin: string; status: string; source: string | null; reason: string }[];
};
