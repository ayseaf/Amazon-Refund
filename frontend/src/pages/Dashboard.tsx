import { Difference, ErrorState, LoadingState } from "../components/Money";
import { formatMoney } from "../format";
import { useCatalog } from "../catalog";
import { OriginTag } from "../live";

export function DashboardPage() {
  const state = useCatalog();
  return (
    <section>
      <header className="page-header">
        <h1>Dashboard</h1>
        <p>
          The totals below are sample data. Live orders from a review on this computer are listed
          separately and are never mixed into those totals.
        </p>
      </header>
      {state.status === "loading" ? <LoadingState /> : null}
      {state.status === "error" ? <ErrorState message={state.message} /> : null}
      {state.status === "ready" ? (
        <>
          <dl className="facts">
            <div>
              <dt>Amazon account</dt>
              <dd>{state.info.amazon_connected ? "Connected" : "Not connected"}</dd>
            </div>
            <div>
              <dt>Orders in the local database</dt>
              <dd data-testid="stored-orders">{state.stats.stored_orders}</dd>
            </div>
            <div>
              <dt>Last successful synchronization</dt>
              <dd>{state.catalog.last_successful_sync_at ?? "Never"}</dd>
            </div>
            <div>
              <dt>Scheduler</dt>
              <dd>{state.info.scheduler.running ? "Running" : "Not running"}</dd>
            </div>
          </dl>
          <p className="hint">{state.catalog.clock_note}</p>
          <section className="panel">
            <h2>Live from Amazon</h2>
            <p>
              {state.session.status === "signed_in"
                ? "A session is stored on this computer. The password is not."
                : "Not signed in. Amazon has not been contacted."}
            </p>
            <p>
              Live orders {state.live.items.length}. Opportunities {state.opportunities.items.length}. Last scan{" "}
              {state.session.last_scan_finished_at ?? "never"}.
            </p>
            {state.session.last_error ? <p className="error-text">{state.session.last_error}</p> : null}
          </section>
          <div className="stats">
            <article className="stat">
              <p className="stat-label">Products monitored</p>
              <p className="stat-value">{state.catalog.dashboard.products_monitored}</p>
            </article>
            <article className="stat">
              <p className="stat-label">Estimated savings</p>
              <p className="stat-value" data-testid="stat-estimated-savings">
                {formatMoney(state.catalog.dashboard.estimated_savings_cents)}
              </p>
            </article>
            <article className="stat">
              <p className="stat-label">Confirmed refunds</p>
              <p className="stat-value">{formatMoney(state.catalog.dashboard.confirmed_refunds_cents)}</p>
            </article>
            <article className="stat">
              <p className="stat-label">Pending requests</p>
              <p className="stat-value">{state.catalog.dashboard.pending_refund_requests}</p>
            </article>
          </div>
          <div className="split">
            <section className="panel">
              <h2>Recent price changes</h2>
              <ul className="plain">
                {state.catalog.dashboard.recent_price_changes.map((change) => (
                  <li key={change.order_id}>
                    <OriginTag live={false} /> {change.title}{" "}
                    <Difference cents={change.difference_cents} />
                  </li>
                ))}
              </ul>
            </section>
            <section className="panel">
              <h2>Upcoming return deadlines</h2>
              <ul className="plain">
                {state.catalog.dashboard.upcoming_return_deadlines.map((deadline) => (
                  <li key={deadline.order_id}>
                    <OriginTag live={false} /> {deadline.title}
                    <span className="warn-chip">{deadline.warning}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}
