import { Difference, ErrorState, LoadingState, Money, StatusPill } from "../components/Money";
import { useCatalog } from "../catalog";

export function OrdersPage() {
  const state = useCatalog();
  return (
    <section>
      <header className="page-header">
        <h1>Amazon Orders</h1>
        <p>Sample rows only. Product links are omitted so this screen cannot be mistaken for a live account.</p>
      </header>
      {state.status === "loading" ? <LoadingState /> : null}
      {state.status === "error" ? <ErrorState message={state.message} /> : null}
      {state.status === "ready" ? (
        <div className="table-wrap">
          <table>
            <caption>Sample orders. Not from an Amazon account.</caption>
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
                    <span className="sample-tag">{item.sample_label}</span>
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
      ) : null}
    </section>
  );
}
