import { useState, type ReactNode } from "react";
import { api } from "./api";
import { deadlinePhrase, formatUsd, justInked, monitoringLabel } from "./format";
import type { Item, PriceCheck } from "./types";

export function Mark() {
  return (
    <svg className="mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect x="5" y="7" width="22" height="18" rx="2" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5 13h22" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M11 7v3M21 7v3" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function LoadGate({
  loading,
  error,
  children,
}: {
  loading: boolean;
  error: string | null;
  children: ReactNode;
}) {
  if (loading) {
    return <p className="status">Loading the local ledger…</p>;
  }
  if (error) {
    return (
      <p className="problem" role="alert">
        The local service did not respond. Start it with <code>scripts/dev.sh</code>, then reload this page. {error}
      </p>
    );
  }
  return children;
}

export function Stamp({
  word,
  form,
  fresh,
}: {
  word: string;
  form: Item["stamp_form"];
  fresh: boolean;
}) {
  return <span className={`stamp stamp-${form}${fresh ? " inking" : ""}`}>{word}</span>;
}

export function ProductTable({ items, caption }: { items: Item[]; caption: string }) {
  if (items.length === 0) {
    return (
      <p>
        No purchases are stored. Load the labeled sample from <a href="#/settings">Settings</a>, or bring in an
        order file in a later phase. Amazon has not been contacted.
      </p>
    );
  }
  return (
    <div className="table-wrap">
      <table>
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Product</th>
            <th scope="col" className="num">Paid</th>
            <th scope="col" className="num">Latest</th>
            <th scope="col">Difference</th>
            <th scope="col">Purchased</th>
            <th scope="col">Return deadline</th>
            <th scope="col">Monitoring</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td data-label="Product">
                <span className="product-title">{item.title}</span>
                <span className="sub">
                  {item.amazon_order_id} · {item.asin} · {item.seller} · {item.condition}
                  {item.quantity > 1 ? ` · qty ${item.quantity}` : ""}
                </span>
                {item.variation_note ? <span className="sub">{item.variation_note}</span> : null}
              </td>
              <td className="num" data-label="Paid">
                <span className="figure">{formatUsd(item.purchase_total_cents)}</span>
                <span className="sub">Includes shipping and tax</span>
              </td>
              <td className="num" data-label="Latest">
                <span className="figure">
                  {item.latest_total_cents == null ? "—" : formatUsd(item.latest_total_cents)}
                </span>
                <span className="sub">{item.price_source ? `Source: ${item.price_source}` : "Not checked"}</span>
              </td>
              <td className="diff" data-label="Difference">
                <Stamp word={item.stamp_word} form={item.stamp_form} fresh={justInked(item.price_checked_at)} />
                {item.savings_cents != null ? (
                  <span className="figure">{formatUsd(Math.abs(item.savings_cents))}</span>
                ) : null}
                <span className="sub">{item.difference_label}</span>
              </td>
              <td className="when" data-label="Purchased">{item.purchased_on}</td>
              <td className="when" data-label="Deadline">{deadlinePhrase(item.deadline_window, item.return_deadline)}</td>
              <td data-label="Monitoring">{monitoringLabel(item.monitoring_status)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function CheckPrices({ onDone }: { onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setProblem(null);
    try {
      const body = await api<PriceCheck>("/api/price-checks", { method: "POST" });
      const checked = body.results.filter((row) => row.status === "checked").length;
      const skipped = body.results.length - checked;
      const count = `${checked} item${checked === 1 ? "" : "s"}`;
      const skip = skipped ? `, skipped ${skipped}` : "";
      setMessage(`Checked ${count}${skip}. No network request was sent, and Keepa was not called.`);
      onDone();
    } catch (reason) {
      setProblem(reason instanceof Error ? reason.message : "The price check failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="check">
      <button className="primary" type="button" onClick={run} disabled={busy}>
        {busy ? "Checking…" : "Check prices"}
      </button>
      {message ? <p>{message}</p> : <p>Uses the labeled sample source only. Nothing is purchased or returned.</p>}
      {problem ? (
        <p className="problem" role="alert">
          {problem}
        </p>
      ) : null}
    </div>
  );
}
