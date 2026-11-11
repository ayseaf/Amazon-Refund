import { useState } from "react";
import { requestPriceCheck } from "../api";
import { Difference, ErrorState, LoadingState, Money, StatusPill } from "../components/Money";
import { useCatalog } from "../catalog";
import type { PriceCheckResult } from "../types";

export function MonitoringPage() {
  const state = useCatalog();
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<PriceCheckResult | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  async function onCheck() {
    setPending(true);
    setFailure(null);
    try {
      setResult(await requestPriceCheck());
    } catch (error) {
      setFailure(error instanceof Error ? error.message : "The price check could not be requested.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section>
      <header className="page-header">
        <h1>Price Monitoring</h1>
        <p>
          A signed-in review reads public product pages one at a time, no more than once an hour.
          This button does not invent a price, and it does not run until you are signed in on this Mac.
        </p>
      </header>
      {state.status === "loading" ? <LoadingState /> : null}
      {state.status === "error" ? <ErrorState message={state.message} /> : null}
      {state.status === "ready" ? (
        <>
          <div className="panel action-row">
            <p>{state.catalog.monitoring.note}</p>
            <p className="muted">
              Provider: {state.catalog.monitoring.provider ?? "none"}. Minimum interval{" "}
              {state.catalog.monitoring.minimum_interval_minutes} minutes. Checks running:{" "}
              {state.catalog.monitoring.checks_running ? "yes" : "no"}.
            </p>
            <button type="button" onClick={onCheck} disabled={pending}>
              {pending ? "Checking…" : "Check prices now"}
            </button>
            {result ? (
              <div data-testid="price-check-result" role="status">
                <p>{result.error.message}</p>
                {result.price_cents === null ? <p>No price was recorded.</p> : null}
              </div>
            ) : null}
            {failure ? (
              <p role="alert" className="error-text">
                {failure}
              </p>
            ) : null}
          </div>
          <div className="table-wrap">
            <table>
              <caption>Sample monitoring rows</caption>
              <thead>
                <tr>
                  <th scope="col">Product</th>
                  <th scope="col">Status</th>
                  <th scope="col">Latest price</th>
                  <th scope="col">Checked</th>
                  <th scope="col">Difference</th>
                </tr>
              </thead>
              <tbody>
                {state.catalog.monitoring.rows.map((row) => (
                  <tr key={row.order_id}>
                    <td>
                      <span className="sample-tag">Sample data</span> {row.title}
                      {row.monitoring_note ? <div className="muted">{row.monitoring_note}</div> : null}
                    </td>
                    <td>
                      <StatusPill value={row.monitoring_status} />
                    </td>
                    <td>
                      <Money cents={row.latest_price_cents} />
                    </td>
                    <td>{row.latest_price_checked_at ?? "Never"}</td>
                    <td>
                      <Difference cents={row.line_difference_cents} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  );
}
