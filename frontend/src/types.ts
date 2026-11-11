export interface CatalogItem {
  data_origin: "sample";
  sample_label: "SAMPLE";
  order_id: string;
  asin: string;
  title: string;
  product_url: string | null;
  purchased_at: string;
  quantity: number;
  unit_price_cents: number;
  shipping_cents: number;
  tax_cents: number;
  seller_name: string;
  condition: string;
  currency: "USD";
  return_eligible: boolean | null;
  return_deadline_at: string | null;
  days_until_deadline: number | null;
  monitoring_status: string;
  latest_price_cents: number | null;
  latest_price_checked_at: string | null;
  price_source: string | null;
  line_difference_cents: number | null;
  price_adjustment_available: boolean | null;
  price_adjustment_note: string;
  monitoring_note: string | null;
  guaranteed: false;
}

export interface RefundRequest {
  data_origin: "sample";
  sample_label: "SAMPLE";
  order_id: string;
  title: string;
  asin: string;
  status: string;
  requested_amount_cents: number;
  confirmed_refund_cents: number | null;
  draft_message: string;
  policy_note: string;
  final_denial: boolean;
  automated_submission: false;
  submission_method: string | null;
  guaranteed: false;
  note: string;
}

export interface RepurchaseEstimate {
  price_delta_cents: number;
  tax_delta_cents: number;
  return_shipping_cents: number;
  restocking_fee_cents: number;
  repurchase_shipping_cents: number;
  net_savings_cents: number;
  worth_considering: boolean;
  guaranteed: false;
  formula: string;
  data_origin: "sample";
  sample_label: "SAMPLE";
}

export interface ReturnRow {
  data_origin: "sample";
  sample_label: "SAMPLE";
  order_id: string;
  title: string;
  return_eligible: boolean | null;
  return_deadline_at: string | null;
  days_until_deadline: number | null;
  warning: string | null;
  repurchase: RepurchaseEstimate | null;
  recommended_action: string;
  guaranteed: false;
}

export interface SavingsEntry {
  data_origin: "sample";
  sample_label: "SAMPLE";
  order_id: string;
  title: string;
  kind: "estimated_gap" | "confirmed_refund";
  amount_cents: number;
  guaranteed: false;
  note: string;
}

export interface Catalog {
  data_origin: "sample";
  sample_label: "SAMPLE";
  disclaimer: string;
  policy_note: string;
  amazon_connected: boolean;
  last_successful_sync_at: string | null;
  as_of: string;
  clock_note: string;
  items: CatalogItem[];
  refund_requests: RefundRequest[];
  returns: ReturnRow[];
  savings_history: SavingsEntry[];
  monitoring: {
    provider: string | null;
    checks_running: boolean;
    minimum_interval_minutes: number;
    note: string;
    rows: Array<{
      data_origin: "sample";
      sample_label: "SAMPLE";
      order_id: string;
      title: string;
      monitoring_status: string;
      latest_price_cents: number | null;
      latest_price_checked_at: string | null;
      price_source: string | null;
      line_difference_cents: number | null;
      monitoring_note: string | null;
      guaranteed: false;
    }>;
  };
  dashboard: {
    products_monitored: number;
    estimated_savings_cents: number;
    confirmed_refunds_cents: number;
    pending_refund_requests: number;
    upcoming_return_deadlines: Array<{
      data_origin: "sample";
      sample_label: "SAMPLE";
      order_id: string;
      title: string;
      return_deadline_at: string;
      days_until_deadline: number;
      warning: string | null;
    }>;
    recent_price_changes: Array<{
      data_origin: "sample";
      sample_label: "SAMPLE";
      order_id: string;
      title: string;
      difference_cents: number;
      guaranteed: false;
    }>;
    last_successful_sync_at: string | null;
    amazon_connected: boolean;
    data_origin: "sample";
    sample_label: "SAMPLE";
  };
}

export interface AppInfo {
  name: string;
  version: string;
  phase: number;
  sample_data_only: boolean;
  amazon_connected: boolean;
  accepts_amazon_password: boolean;
  secret_backend: string;
  secret_store: string;
  scheduler: {
    backend: string;
    running: boolean;
    available: boolean;
    installed: boolean;
    detail: string;
  };
  platform: string;
  database: string;
  price_provider: string | null;
  disclaimer: string;
}

export interface Stats {
  data_origin: "database";
  stored_orders: number;
  stored_items: number;
  sample_rows_included: boolean;
}

export interface AppSettings {
  monitoring_interval_minutes: number;
  min_savings_cents: number;
  desktop_notifications: boolean;
  email_notifications: boolean;
  telegram_notifications: boolean;
  notify_price_decrease: boolean;
  notify_savings: boolean;
  notify_return_deadlines: boolean;
  notify_price_check_failures: boolean;
  notify_refund_status: boolean;
  notify_monitoring_unavailable: boolean;
  email_available: boolean;
  telegram_available: boolean;
  phase: number;
}

export interface SecretStatus {
  name: string;
  configured: boolean;
  backend: string;
}

export interface PriceCheckResult {
  error: { code: string; message: string };
  checked: boolean;
  price_cents: number | null;
  recorded_run_status: string;
}

export interface ApiFailure extends Error {
  code?: string;
  status?: number;
  payload?: unknown;
}
