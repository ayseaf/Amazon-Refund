import { Difference, ErrorState, LoadingState, Money, StatusPill } from "../components/Money";
import { useCatalog } from "../catalog";
import { OpportunityList, OriginTag } from "../live";

export function OrdersPage() {
  const state = useCatalog();
  return (
    <section>
      <header className="page-header">
        <h1>Amazon Orders</h1>
        <p>
          Sample rows stay labeled Sample data. Rows from a review on this computer are labeled Live
          from Amazon. Nothing on this page submits a return or a refund.
        </p>
      </header>
      {state.status === "loading" ? <LoadingState /> : null}
      {state.status === "error" ? <ErrorState message={state.message} /> : null}
      {state.status === "ready" ? (
        <div className="stack">
          <section>
            <h2>Live from Amazon</h2>
            {state.live.items.length === 0 ? (
              <p className="muted">No live orders yet. Sign in from Settings and review the last 30 days.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <caption>Live from Amazon. Read from your own sign-in on this computer.</caption>
                  <thead>
                    <tr>
                      <th scope="col">Order</th>
                      <th scope="col">Product</th>
                      <th scope="col">Paid</th>
                      <th scope="col">Current</th>
                      <th scope="col">Verdict</th>
                    </tr>
                  </thead>
                  <tbody>
                    {state.live.items.map((item) => (
                      <tr key={`${item.order_id}-${item.asin ?? item.title}`}>
                        <td>
                          <OriginTag live />
                          <div className="mono">{item.order_id}</div>
                        </td>
                        <td>
                          <div>{item.title}</div>
                          <div className="muted">
                            {item.asin ? `ASIN ${item.asin}` : "ASIN not shown"} · {item.seller_name ?? "Seller not shown"}
                            {item.fulfilled_by ? ` · Fulfilled by ${item.fulfilled_by}` : ""}
                          </div>
                        </td>
                        <td>
                          <Money cents={item.unit_price_cents} />
                        </td>
                        <td>
                          <Money cents={item.current_price_cents} />
                        </td>
                        <td>{item.verdict_label ?? "Unknown"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <section data-testid="opportunities">
            <h2>Opportunities</h2>
            <OpportunityList
              items={state.opportunities.items}
              empty="No live opportunities yet. A refund is not guaranteed."
            />
          </section>
          <div className="table-wrap">
          <table>
            <caption>Sample data. Not from an Amazon account.</caption>
            <thead>
              <tr>
                <th scope="col">Order</th>
                <th scope="col">Product</th>
                <th scope="col">Purchased</th>
                <th scope="col">Purchase price</th>
                <th scope="col">Latest price</th>
                <th scope="col">Difference</th>
                <th scope="col">Return deadline</th>
                <th scope="col">Monitoring</th>
              </tr>
            </thead>
            <tbody>
              {state.catalog.items.map((item) => (
                <tr key={item.order_id}>
                  <td>
                    <OriginTag live={false} />
                    <div className="mono">{item.order_id}</div>
                  </td>
                  <td>
                    <div>{item.title}</div>
                    <div className="muted">
                      ASIN {item.asin} · {item.seller_name} · {item.condition} · qty {item.quantity}
                    </div>
                  </td>
                  <td>{item.purchased_at}</td>
                  <td>
                    <Money cents={item.unit_price_cents} />
                    <div className="muted">
                      Shipping <Money cents={item.shipping_cents} /> · Tax <Money cents={item.tax_cents} />
                    </div>
                  </td>
                  <td>
                    <Money cents={item.latest_price_cents} />
                    <div className="muted">{item.price_source ?? "No source"}</div>
                  </td>
                  <td>
                    <Difference cents={item.line_difference_cents} />
                  </td>
                  <td>
                    {item.return_deadline_at ?? "Unknown"}
                    <div className="muted">{item.return_eligible ? "Eligible in the sample" : "Not eligible in the sample"}</div>
                  </td>
                  <td>
                    <StatusPill value={item.monitoring_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}
