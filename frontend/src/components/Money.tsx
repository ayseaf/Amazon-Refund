import { formatDifference, formatMoney } from "../format";

export function Difference({ cents }: { cents: number | null }) {
  const label = formatDifference(cents);
  const tone = cents === null || cents === 0 ? "muted" : cents > 0 ? "down" : "up";
  return <span className={tone}>{label}</span>;
}

export function Money({ cents }: { cents: number | null }) {
  return <span>{formatMoney(cents)}</span>;
}

export function StatusPill({ value }: { value: string }) {
  return <span className={`pill pill-${value}`}>{value.replaceAll("_", " ")}</span>;
}

export function LoadingState() {
  return <p className="status-line">Loading sample catalog…</p>;
}

export function ErrorState({ message }: { message: string }) {
  return (
    <p className="status-line error" role="alert">
      Local API is unavailable. {message} Start it on 127.0.0.1:8787.
    </p>
  );
}
