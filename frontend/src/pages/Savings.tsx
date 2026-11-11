import { ErrorState, LoadingState, Money } from "../components/Money";
import { useCatalog } from "../catalog";

export function SavingsPage() {
  const state = useCatalog();
  return (
    <section>
      <header className="page-header">
        <h1>Savings History</h1>
        <p>Estimated gaps and the one sample confirmed amount are listed separately. Neither is a promise.</p>
      </header>
      {state.status === "loading" ? <LoadingState /> : null}
      {state.status === "error" ? <ErrorState message={state.message} /> : null}
      {state.status === "ready" ? (
        <div className="table-wrap">
          <table>
            <caption>Sample savings history</caption>
            <thead>
              <tr>
                <th scope="col">Item</th>
                <th scope="col">Kind</th>
                <th scope="col">Amount</th>
                <th scope="col">Note</th>
              </tr>
            </thead>
            <tbody>
              {state.catalog.savings_history.map((entry) => (
                <tr key={`${entry.kind}-${entry.order_id}`}>
                  <td>
                    <span className="sample-tag">{entry.sample_label}</span> {entry.title}
                  </td>
                  <td>{entry.kind === "confirmed_refund" ? "Confirmed refund (sample)" : "Estimated gap"}</td>
                  <td>
                    <Money cents={entry.amount_cents} />
                  </td>
                  <td>{entry.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
