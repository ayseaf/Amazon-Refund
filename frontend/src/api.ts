import type {
  AmazonActionResult,
  AmazonSession,
  ApiFailure,
  AppInfo,
  AppSettings,
  Catalog,
  LiveOrders,
  Opportunities,
  PriceCheckResult,
  SecretStatus,
  Stats,
} from "./types";

function apiBase(): string {
  return import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8787";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${path}`, {
      ...init,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch (error) {
    const failure = new Error("The local API did not respond.") as ApiFailure;
    failure.cause = error;
    throw failure;
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  const payload = text ? (JSON.parse(text) as { error?: { code?: string; message?: string } }) : null;
  if (!response.ok) {
    const failure = new Error(payload?.error?.message ?? `Request failed (${response.status})`) as ApiFailure;
    failure.code = payload?.error?.code;
    failure.status = response.status;
    failure.payload = payload;
    throw failure;
  }
  return payload as T;
}

export function getCatalog(): Promise<Catalog> {
  return request("/api/v1/sample/catalog");
}

export function getInfo(): Promise<AppInfo> {
  return request("/api/v1/info");
}

export function getStats(): Promise<Stats> {
  return request("/api/v1/stats");
}

export function getSettings(): Promise<AppSettings> {
  return request("/api/v1/settings");
}

export function saveSettings(patch: Partial<AppSettings>): Promise<AppSettings> {
  return request("/api/v1/settings", { method: "PUT", body: JSON.stringify(patch) });
}

export function getSecret(name: string): Promise<SecretStatus> {
  return request(`/api/v1/secrets/${name}`);
}

export function putSecret(name: string, value: string): Promise<void> {
  return request(`/api/v1/secrets/${name}`, { method: "PUT", body: JSON.stringify({ value }) });
}

export async function requestPriceCheck(): Promise<PriceCheckResult> {
  const response = await fetch(`${apiBase()}/api/v1/price-checks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  return (await response.json()) as PriceCheckResult;
}

export function getAmazonSession(): Promise<AmazonSession> {
  return request("/api/v1/amazon/session");
}

export function getLiveOrders(): Promise<LiveOrders> {
  return request("/api/v1/orders");
}

export function getOpportunities(): Promise<Opportunities> {
  return request("/api/v1/opportunities");
}

export function startAmazonSignIn(): Promise<AmazonActionResult> {
  return request("/api/v1/amazon/sign-in", { method: "POST", body: "{}" });
}

export function scanAmazonOrders(): Promise<AmazonActionResult> {
  return request("/api/v1/amazon/scan", { method: "POST", body: "{}" });
}

export function deleteAmazonSession(): Promise<{ status: string; deleted: boolean; accepts_amazon_password: false }> {
  return request("/api/v1/amazon/session", { method: "DELETE" });
}

export function deletePurchases(): Promise<{ deleted: { orders: number }; sample_data_affected: boolean }> {
  return request("/api/v1/purchases", {
    method: "DELETE",
    headers: { "X-Confirm-Delete": "DELETE-PURCHASE-DATA" },
  });
}
