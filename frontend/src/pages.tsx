import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api } from "./api";
import { CheckPrices, LoadGate, ProductTable } from "./components";
import { centsToDollarInput, deadlinePhrase, dollarsToCents, formatUsd, formatWhen, windowRank } from "./format";
import type { Dashboard, Item, Settings } from "./types";
import { useApi } from "./useApi";

function sentence(data: Dashboard): string {
  const products = `${data.monitored_count} product${data.monitored_count === 1 ? "" : "s"}`;
  return `${products} on the ledger. Estimated difference ${formatUsd(data.estimated_savings_cents)}. Confirmed refunds ${formatUsd(data.confirmed_refunds_cents)}. Pending requests: ${data.pending_refund_requests}.`;
}

export function DashboardPage() {
  const board = useApi<Dashboard>("/api/dashboard");
  const orders = useApi<{ items: Item[]; data_mode: string }>("/api/orders");
  const notices = useApi<{ notifications: { title: string; body: string; delivered_to_macos: boolean }[] }>(
    "/api/notifications",
  );

  function refresh() {
    board.reload();
    orders.reload();
    notices.reload();
  }

  return (
    <LoadGate loading={board.loading || orders.loading} error={board.error ?? orders.error}>
      {board.data && orders.data ? (
        <>
        <div className="sheet">
          <section className="lead">
            <h1>Dashboard</h1>
            <p className="lede">{sentence(board.data)}</p>
            {board.data.data_mode === "sample" ? (
              <p>These rows are fabricated sample orders. Amazon has not been contacted, and no refund has been requested.</p>
            ) : null}
          </section>
          <aside className="act">
            <h2>Before you act</h2>
            <p>{board.data.disclaimer}</p>
            <h2>Last synchronization</h2>
            {board.data.last_successful_sync ? (
              <p>
                {formatWhen(board.data.last_successful_sync.finished_at)}. {board.data.last_successful_sync.message}
              </p>
            ) : (
              <p>No synchronization yet.</p>
            )}
            <CheckPrices onDone={refresh} />
          </aside>
          <div className="ledger">
            <ProductTable
              items={orders.data.items}
              caption="Purchases ordered by the soonest return deadline, then by estimated difference."
            />
          </div>
        </div>
        <div className="work">
          <section>
            <h2>Recent checks</h2>
            {board.data.recent_price_changes.length === 0 ? (
              <p>No price has been checked yet.</p>
            ) : (
              <ul className="plain">
                {board.data.recent_price_changes.map((change) => (
                  <li key={`${change.asin}-${change.checked_at}`}>
                    <span className="product-title">{change.title}</span>
                    <span className="sub">
                      {formatWhen(change.checked_at)} · source {change.source}
                      {change.is_sample ? " · sample" : ""} ·{" "}
                      {change.comparable && change.savings_cents != null
                        ? formatUsd(change.savings_cents)
                        : "not counted as the same offer"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <aside>
            <h2>Return windows inside 7 days</h2>
            {board.data.upcoming_return_deadlines.length === 0 ? (
              <p>None.</p>
            ) : (
              <ul className="plain">
                {board.data.upcoming_return_deadlines.map((item) => (
                  <li key={item.asin}>
                    {item.title}
                    <span className="sub">
                      {deadlinePhrase(item.window, item.return_deadline)} · {windowRank(item.window)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <h2>Recorded notices</h2>
            {notices.data && notices.data.notifications.length > 0 ? (
              <ul className="plain">
                {notices.data.notifications.map((note, index) => (
                  <li key={`${note.title}-${index}`}>
                    {note.title}
                    <span className="sub">
                      {note.body} {note.delivered_to_macos ? "" : "Not sent to Notification Center."}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>None yet. macOS banners are not sent in this version.</p>
            )}
          </aside>
        </div>
        </>
      ) : null}
    </LoadGate>
  );
}

export function OrdersPage() {
  const orders = useApi<{ items: Item[]; data_mode: string }>("/api/orders");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const items = useMemo(() => {
    const source = orders.data?.items ?? [];
    const needle = query.trim().toLowerCase();
    return source.filter((item) => {
      const matchesText =
        needle.length === 0 ||
        item.title.toLowerCase().includes(needle) ||
        item.asin.toLowerCase().includes(needle) ||
        item.amazon_order_id.toLowerCase().includes(needle);
      const matchesFilter =
        filter === "all" ||
        (filter === "lower" && (item.savings_cents ?? 0) > 0) ||
        (filter === "due" && (item.deadline_window === "1" || item.deadline_window === "3" || item.deadline_window === "7"));
      return matchesText && matchesFilter;
    });
  }, [orders.data, query, filter]);

  return (
    <LoadGate loading={orders.loading} error={orders.error}>
      <h1>Amazon Orders</h1>
      <p className="lede">
        {orders.data?.data_mode === "sample"
          ? "Showing labeled sample orders. This is not your Amazon account."
          : "No Amazon account is connected. An order-file import is the next phase."}
      </p>
      <div className="filters">
        <label>
          Find
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Title, ASIN, or order id" />
        </label>
        <label>
          Show
          <select value={filter} onChange={(event) => setFilter(event.target.value)}>
            <option value="all">All products</option>
            <option value="lower">Lower than paid</option>
            <option value="due">Return window inside 7 days</option>
          </select>
        </label>
      </div>
      <ProductTable items={items} caption="Filtered purchases. Clearing the filter shows every stored product." />
    </LoadGate>
  );
}

export function MonitoringPage() {
  const status = useApi<{
    scheduler_installed: boolean;
    keepa_called: boolean;
    interval_minutes: number;
    desktop_delivery: string;
    last_check: { checked_at: string; source: string } | null;
    note: string;
  }>("/api/monitoring");

  return (
    <LoadGate loading={status.loading} error={status.error}>
      {status.data ? (
        <div className="work">
          <section>
            <h1>Price Monitoring</h1>
            <p className="lede">{status.data.note}</p>
            <CheckPrices onDone={status.reload} />
            <h2>Last check</h2>
            <p>
              {status.data.last_check
                ? `${formatWhen(status.data.last_check.checked_at)} from ${status.data.last_check.source}.`
                : "No check has been run."}
            </p>
          </section>
          <aside>
            <h2>Limits</h2>
            <p>Stored interval: {status.data.interval_minutes} minutes. The minimum is 60, for a later external source.</p>
            <p>Scheduler installed: {status.data.scheduler_installed ? "yes" : "no"}.</p>
            <p>Keepa called: {status.data.keepa_called ? "yes" : "no"}.</p>
            <p>Desktop delivery: {status.data.desktop_delivery.replaceAll("_", " ")}.</p>
          </aside>
        </div>
      ) : null}
    </LoadGate>
  );
}

export function RefundsPage() {
  const refunds = useApi<{
    requests: { asin: string; title: string; status: string; confirmed_refund_cents: number | null }[];
    confirmed_refunds_cents: number;
    policy: string;
    drafts_available: boolean;
  }>("/api/refunds");
  return (
    <LoadGate loading={refunds.loading} error={refunds.error}>
      {refunds.data ? (
        <>
          <h1>Refund Assistant</h1>
          <p className="lede">{refunds.data.policy}</p>
          <p>
            Confirmed refunds: {formatUsd(refunds.data.confirmed_refunds_cents)}. Message drafts are{" "}
            {refunds.data.drafts_available ? "available" : "not in this version"}. A lower price does not create a request.
          </p>
          {refunds.data.requests.length === 0 ? (
            <p>No refund request is stored.</p>
          ) : (
            <ul className="plain">
              {refunds.data.requests.map((request) => (
                <li key={request.asin}>
                  {request.title} · {request.status}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
    </LoadGate>
  );
}

export function ReturnsPage() {
  const returns = useApi<{
    submission_available: boolean;
    formula: string;
    restocking_fee_cents: number;
    return_shipping_cents: number;
    items: Item[];
  }>("/api/returns");
  return (
    <LoadGate loading={returns.loading} error={returns.error}>
      {returns.data ? (
        <>
          <h1>Returns and Deadlines</h1>
          <p className="lede">{returns.data.formula}</p>
          <p>
            Restocking {formatUsd(returns.data.restocking_fee_cents)}. Return shipping{" "}
            {formatUsd(returns.data.return_shipping_cents)}. Submission from this app:{" "}
            {returns.data.submission_available ? "available" : "off"}.
          </p>
          {returns.data.items.length === 0 ? (
            <p>No purchases are stored.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <caption>Return window and a read-only repurchase estimate.</caption>
                <thead>
                  <tr>
                    <th scope="col">Product</th>
                    <th scope="col">Deadline</th>
                    <th scope="col">Eligible</th>
                    <th scope="col" className="num">Estimate</th>
                  </tr>
                </thead>
                <tbody>
                  {returns.data.items.map((item) => (
                    <tr key={item.id}>
                      <td data-label="Product">{item.title}</td>
                      <td data-label="Deadline">{deadlinePhrase(item.deadline_window, item.return_deadline)}</td>
                      <td data-label="Eligible">{item.return_eligible ? "Eligible in the sample record" : "Not eligible"}</td>
                      <td className="num" data-label="Estimate">
                        <span className="figure">
                          {item.repurchase_estimate_cents == null
                            ? "—"
                            : formatUsd(item.repurchase_estimate_cents)}
                        </span>
                        <span className="sub">
                          {item.repurchase_estimate_cents == null
                            ? !item.price_checked_at
                              ? "Check a price first"
                              : !item.return_eligible
                                ? "Return is closed"
                                : "Not an equivalent offer"
                            : "Read-only. Nothing is submitted."}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </LoadGate>
  );
}

export function SavingsPage() {
  const savings = useApi<{
    snapshots: {
      asin: string;
      title: string;
      checked_at: string;
      source: string;
      comparable: boolean;
      savings_cents: number | null;
      total_cents: number | null;
      is_sample: boolean;
      note: string;
    }[];
    amazon_contacted: boolean;
  }>("/api/savings");
  return (
    <LoadGate loading={savings.loading} error={savings.error}>
      {savings.data ? (
        <>
          <h1>Savings History</h1>
          <p className="lede">
            Each row is one check. Amazon contacted: {savings.data.amazon_contacted ? "yes" : "no"}.
          </p>
          {savings.data.snapshots.length === 0 ? (
            <p>No checks are stored. Use Check prices on the dashboard.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <caption>Price checks, newest first.</caption>
                <thead>
                  <tr>
                    <th scope="col">When</th>
                    <th scope="col">Product</th>
                    <th scope="col">Source</th>
                    <th scope="col" className="num">Current total</th>
                    <th scope="col" className="num">Counted difference</th>
                  </tr>
                </thead>
                <tbody>
                  {savings.data.snapshots.map((row) => (
                    <tr key={`${row.asin}-${row.checked_at}`}>
                      <td className="when" data-label="When">{formatWhen(row.checked_at)}</td>
                      <td data-label="Product">
                        {row.title}
                        <span className="sub">{row.note}</span>
                      </td>
                      <td data-label="Source">{row.is_sample ? `${row.source} · sample` : row.source}</td>
                      <td className="num" data-label="Current total">{row.total_cents == null ? "—" : formatUsd(row.total_cents)}</td>
                      <td className="num" data-label="Counted difference">
                        {row.comparable && row.savings_cents != null ? formatUsd(row.savings_cents) : "Not counted"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </LoadGate>
  );
}

export function SettingsPage() {
  const settings = useApi<Settings>("/api/settings");
  const secrets = useApi<{ secrets: { name: string; stored: boolean }[] }>("/api/secrets");
  const [interval, setInterval] = useState("60");
  const [threshold, setThreshold] = useState("5.00");
  const [restocking, setRestocking] = useState("0.00");
  const [returnShip, setReturnShip] = useState("0.00");
  const [notifyDrops, setNotifyDrops] = useState(true);
  const [notifyDeadlines, setNotifyDeadlines] = useState(true);
  const [notifyFailures, setNotifyFailures] = useState(true);
  const [keyValue, setKeyValue] = useState("");
  const [phrase, setPhrase] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    if (!settings.data) {
      return;
    }
    setInterval(String(settings.data.monitoring_interval_minutes));
    setThreshold(centsToDollarInput(settings.data.notify_min_savings_cents));
    setRestocking(centsToDollarInput(settings.data.restocking_fee_cents));
    setReturnShip(centsToDollarInput(settings.data.return_shipping_cents));
    setNotifyDrops(settings.data.notify_price_decreases);
    setNotifyDeadlines(settings.data.notify_return_deadlines);
    setNotifyFailures(settings.data.notify_price_check_failures);
  }, [settings.data]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    setMessage(null);
    const minutes = Number(interval);
    const thresholdCents = dollarsToCents(threshold);
    const restockingCents = dollarsToCents(restocking);
    const shippingCents = dollarsToCents(returnShip);
    if (!Number.isInteger(minutes) || thresholdCents == null || restockingCents == null || shippingCents == null) {
      setProblem("Use whole minutes and dollar amounts with at most two decimal places.");
      return;
    }
    try {
      await api("/api/settings", {
        method: "PUT",
        body: JSON.stringify({
          monitoring_interval_minutes: minutes,
          notify_min_savings_cents: thresholdCents,
          restocking_fee_cents: restockingCents,
          return_shipping_cents: shippingCents,
          notify_price_decreases: notifyDrops,
          notify_return_deadlines: notifyDeadlines,
          notify_price_check_failures: notifyFailures,
        }),
      });
      setMessage("Settings saved on this Mac's local database.");
      settings.reload();
    } catch (reason) {
      setProblem(reason instanceof Error ? reason.message : "Settings were not saved.");
    }
  }

  async function loadSample() {
    setProblem(null);
    setMessage(null);
    try {
      await api("/api/sample-data", { method: "POST" });
      setMessage("Loaded 6 labeled sample orders. Amazon was not contacted.");
    } catch (reason) {
      setProblem(reason instanceof Error ? reason.message : "Sample data was not loaded.");
    }
  }

  async function clearSample() {
    setProblem(null);
    try {
      await api("/api/sample-data", { method: "DELETE" });
      setMessage("Removed labeled sample orders.");
    } catch (reason) {
      setProblem(reason instanceof Error ? reason.message : "Sample data was not removed.");
    }
  }

  async function storeKey(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    try {
      await api("/api/secrets/keepa_api_key", {
        method: "PUT",
        body: JSON.stringify({ value: keyValue }),
      });
      setKeyValue("");
      setMessage("Key stored locally. It was not sent to Keepa.");
      secrets.reload();
    } catch (reason) {
      setProblem(reason instanceof Error ? reason.message : "The key was not stored.");
    }
  }

  async function removeKey() {
    setProblem(null);
    try {
      await api("/api/secrets/keepa_api_key", { method: "DELETE" });
      setMessage("Removed the stored Keepa key.");
      secrets.reload();
    } catch (reason) {
      setProblem(reason instanceof Error ? reason.message : "The key was not removed.");
    }
  }

  async function purge(event: FormEvent) {
    event.preventDefault();
    setProblem(null);
    try {
      await api("/api/purchase-data", {
        method: "DELETE",
        body: JSON.stringify({ confirmation: phrase }),
      });
      setPhrase("");
      setMessage("Deleted local purchase data. Stored keys were kept.");
    } catch (reason) {
      setProblem(reason instanceof Error ? reason.message : "Purchase data was not deleted.");
    }
  }

  const keyStored = secrets.data?.secrets.some((item) => item.name === "keepa_api_key" && item.stored) ?? false;

  return (
    <LoadGate loading={settings.loading} error={settings.error}>
      <h1>Settings</h1>
      <p className="lede">
        Phase 1 stays on this computer. There is no Amazon login, and an Amazon password is not accepted.
      </p>
      {message ? <p>{message}</p> : null}
      {problem ? (
        <p className="problem" role="alert">
          {problem}
        </p>
      ) : null}
      <form onSubmit={save}>
        <fieldset>
          <legend>Price checks</legend>
          <label>
            Minutes between future scheduled checks
            <input value={interval} onChange={(event) => setInterval(event.target.value)} inputMode="numeric" />
          </label>
          <label>
            Record a notice when the difference is at least
            <input value={threshold} onChange={(event) => setThreshold(event.target.value)} inputMode="decimal" />
          </label>
        </fieldset>
        <fieldset>
          <legend>Notices</legend>
          <label className="check-row">
            <input type="checkbox" checked={notifyDrops} onChange={(event) => setNotifyDrops(event.target.checked)} />
            Record price decreases
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={notifyDeadlines}
              onChange={(event) => setNotifyDeadlines(event.target.checked)}
            />
            Record return deadlines
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={notifyFailures}
              onChange={(event) => setNotifyFailures(event.target.checked)}
            />
            Record price-check failures
          </label>
          <p>Email, Telegram, and macOS banners are not sent in this version. Notices stay in the dashboard.</p>
        </fieldset>
        <fieldset>
          <legend>Return estimate</legend>
          <label>
            Restocking fee in dollars
            <input value={restocking} onChange={(event) => setRestocking(event.target.value)} inputMode="decimal" />
          </label>
          <label>
            Return shipping in dollars
            <input value={returnShip} onChange={(event) => setReturnShip(event.target.value)} inputMode="decimal" />
          </label>
        </fieldset>
        <button className="primary" type="submit">
          Save settings
        </button>
      </form>
      <form onSubmit={storeKey}>
        <fieldset>
          <legend>Keepa key</legend>
          <p>{keyStored ? "A key is stored locally." : "No key is stored."} Saving it does not contact Keepa.</p>
          <label>
            Keepa API key
            <input
              type="password"
              value={keyValue}
              autoComplete="off"
              onChange={(event) => setKeyValue(event.target.value)}
              placeholder={keyStored ? "Enter a replacement key" : "Paste a key"}
            />
          </label>
          <div className="button-row">
            <button className="secondary" type="submit">
              Store key locally
            </button>
            <button className="secondary" type="button" onClick={removeKey} disabled={!keyStored}>
              Remove key
            </button>
          </div>
        </fieldset>
      </form>
      <fieldset>
        <legend>Sample data</legend>
        <p>Six invented orders for trying the ledger. They are marked Sample and do not come from an account.</p>
        <div className="button-row">
          <button className="secondary" type="button" onClick={loadSample}>
            Load sample orders
          </button>
          <button className="secondary" type="button" onClick={clearSample}>
            Remove sample orders
          </button>
        </div>
      </fieldset>
      <form onSubmit={purge}>
        <fieldset>
          <legend>Delete purchase data</legend>
          <p>Removes orders, checks, and notices from this computer. Stored API keys stay until you remove them.</p>
          <label>
            Type DELETE PURCHASE DATA
            <input value={phrase} onChange={(event) => setPhrase(event.target.value)} autoComplete="off" />
          </label>
          <button className="primary" type="submit" disabled={phrase !== "DELETE PURCHASE DATA"}>
            Delete local purchase data
          </button>
        </fieldset>
      </form>
    </LoadGate>
  );
}
