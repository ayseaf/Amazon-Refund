import { useState } from "react";
import { Money } from "./components/Money";
import type { LiveItem } from "./types";

export function OriginTag({ live }: { live: boolean }) {
  return live ? <span className="live-tag">Live from Amazon</span> : <span className="sample-tag">Sample data</span>;
}

export function OpportunityList({ items, empty }: { items: LiveItem[]; empty: string }) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  if (items.length === 0) {
    return <p className="muted">{empty}</p>;
  }
  return (
    <div className="stack">
      {items.map((item) => {
        const key = `${item.order_id ?? "order"}-${item.verdict ?? "unknown"}`;
        const draft = item.draft_text ?? "";
        return (
          <article className="panel" key={key}>
            <h3>
              <OriginTag live /> {item.verdict_label ?? "Unknown"}
            </h3>
            <p>
              {item.title ?? "Item"} · {item.order_id}
            </p>
            <p>{item.rule}</p>
            {item.missing.length > 0 ? <p>Missing: {item.missing.join(", ")}.</p> : null}
            <p>
              Paid <Money cents={item.unit_price_cents} /> · Current <Money cents={item.current_price_cents} />
              {item.potential_savings_cents !== null ? (
                <>
                  {" "}
                  · Potential difference <Money cents={item.potential_savings_cents} />
                </>
              ) : null}
            </p>
            <p className="muted">{item.savings_note}</p>
            <p className="muted">Not guaranteed. Nothing is submitted from this app.</p>
            {draft ? (
              <>
                <label htmlFor={`live-draft-${key}`}>Draft for you to review</label>
                <textarea
                  id={`live-draft-${key}`}
                  rows={8}
                  value={drafts[key] ?? draft}
                  onChange={(event) => setDrafts((current) => ({ ...current, [key]: event.target.value }))}
                />
                <p className="muted">Edits stay in this window. Nothing is sent.</p>
              </>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
