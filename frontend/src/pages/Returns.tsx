import { ErrorState, LoadingState, Money } from "../components/Money";
import { formatMoney } from "../format";
import { useCatalog } from "../catalog";
import { OpportunityList, OriginTag } from "../live";

export function ReturnsPage() {
  const state = useCatalog();
  return (
    <section>
      <header className="page-header">
        <h1>Returns and Deadlines</h1>
        <p>
          A return or a new order is never submitted from this application without your explicit
          confirmation. Phase 1 cannot submit either one.
        </p>
      </header>
      {state.status === "loading" ? <LoadingState /> : null}
      {state.status === "error" ? <ErrorState message={state.message} /> : null}
      {state.status === "ready" ? (
        <div className="stack">
          <section>
            <h2>Live from Amazon</h2>
            <OpportunityList
              items={state.opportunities.items.filter((item) => item.verdict === "return_possible")}
              empty="No live return window is on file. This app does not start a return."
            />
          </section>
          <p className="hint">{state.catalog.clock_note}</p>
          {state.catalog.returns.map((row) => (
            <article className="panel" key={row.order_id}>
              <h2>
                <OriginTag live={false} /> {row.title}
              </h2>
              <p>
                Deadline {row.return_deadline_at ?? "unknown"}
                {row.warning ? <span className="warn-chip">{row.warning}</span> : null}
              </p>
              <p className="recommendation">{row.recommended_action}</p>
              {row.repurchase ? (
                <div>
                  <h3>Sample return and repurchase estimate</h3>
                  <ul className="plain">
                    <li>Price difference {formatMoney(row.repurchase.price_delta_cents)}</li>
                    <li>Tax difference {formatMoney(row.repurchase.tax_delta_cents)}</li>
                    <li>Return shipping {formatMoney(row.repurchase.return_shipping_cents)}</li>
                    <li>Restocking fee {formatMoney(row.repurchase.restocking_fee_cents)}</li>
                    <li>Repurchase shipping {formatMoney(row.repurchase.repurchase_shipping_cents)}</li>
                    <li>
                      Estimated net <Money cents={row.repurchase.net_savings_cents} />
                    </li>
                  </ul>
                  <p className="muted">{row.repurchase.formula}</p>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
