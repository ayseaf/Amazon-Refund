export function formatMoney(cents: number | null | undefined): string {
  if (cents === null || cents === undefined) {
    return "—";
  }
  const sign = cents < 0 ? "-" : "";
  const amount = Math.abs(cents);
  return `${sign}$${Math.floor(amount / 100)}.${String(amount % 100).padStart(2, "0")}`;
}

export function centsToDollars(cents: number): string {
  return (cents / 100).toFixed(2);
}

export function dollarsToCents(value: string): number | null {
  const trimmed = value.trim();
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) {
    return null;
  }
  const [dollars, fraction = ""] = trimmed.split(".");
  return Number(dollars) * 100 + Number(fraction.padEnd(2, "0"));
}

export function formatDifference(cents: number | null): string {
  if (cents === null) {
    return "No current price";
  }
  if (cents === 0) {
    return "No change";
  }
  if (cents > 0) {
    return `Down ${formatMoney(cents)}`;
  }
  return `Up ${formatMoney(Math.abs(cents))}`;
}
