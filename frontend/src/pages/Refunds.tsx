import { useState } from "react";
import { ErrorState, LoadingState, Money, StatusPill } from "../components/Money";
import { useCatalog } from "../catalog";

export function RefundsPage() {
  const state = useCatalog();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  return (
    <section>
      <header className="page-header">
        <h1>Refund Assistant</h1>
        <p>
          Drafts are for you to read and edit. Phase 1 does not contact Amazon, and a refund is not
          guaranteed. A final denial is not submitted again.
        </p>
      </header>
      {state.status === "loading" ? <LoadingState /> : null}
      {state.status === "error" ? <ErrorState message={state.message} /> : null}
      {state.status === "ready" ? (
        <div className="stack">
          <p className="policy">{state.catalog.policy_note}</p>
          {state.catalog.refund_requests.map((refund) => {
            const value = drafts[refund.order_id] ?? refund.draft_message;
            return (
              <article className="panel" key={refund.order_id}>
                <header className="row-title">
                  <h2>
                    <span className="sample-tag">{refund.sample_label}</span> {refund.title}
                  </h2>
                  <StatusPill value={refund.status} />
                </header>
                <p className="muted">{refund.order_id}</p>
                <p>
                  Requested <Money cents={refund.requested_amount_cents} /> · Confirmed{" "}
                  <Money cents={refund.confirmed_refund_cents} />
                </p>
                <p>{refund.note}</p>
                {refund.final_denial ? (
                  <p className="error-text">
                    Final denial is recorded on this sample request. Another request will not be prepared.
                  </p>
                ) : (
                  <p className="muted">Edits stay in this window. Nothing is sent.</p>
                )}
                <label htmlFor={`draft-${refund.order_id}`}>Draft message</label>
                <textarea
                  id={`draft-${refund.order_id}`}
                  value={value}
                  readOnly={refund.final_denial}
                  rows={8}
                  onChange={(event) =>
                    setDrafts((current) => ({ ...current, [refund.order_id]: event.target.value }))
                  }
                />
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
