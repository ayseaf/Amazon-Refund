import type { DeadlineWindow } from "./types";

export function formatUsd(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const amount = Math.abs(cents);
  const dollars = Math.floor(amount / 100).toLocaleString("en-US");
  const pennies = String(amount % 100).padStart(2, "0");
  return `${sign}$${dollars}.${pennies}`;
}

export function dollarsToCents(value: string): number | null {
  if (!/^\d+(\.\d{0,2})?$/.test(value.trim())) {
    return null;
  }
  const [whole, fraction = ""] = value.trim().split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

export function centsToDollarInput(cents: number): string {
  return `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, "0")}`;
}

export function deadlinePhrase(window: DeadlineWindow, deadline: string | null): string {
  if (!deadline) {
    return "No deadline stored";
  }
  if (window === "1") {
    return `${deadline} · due within 1 day`;
  }
  if (window === "3") {
    return `${deadline} · due within 3 days`;
  }
  if (window === "7") {
    return `${deadline} · due within 7 days`;
  }
  if (window === "past") {
    return `${deadline} · deadline passed`;
  }
  return deadline;
}

export function monitoringLabel(status: string): string {
  switch (status) {
    case "sample":
      return "Sample";
    case "unconfigured":
      return "No price source";
    case "paused":
      return "Paused";
    case "unmonitorable":
      return "Cannot monitor";
    default:
      return status;
  }
}

export function formatWhen(iso: string | null): string {
  if (!iso) {
    return "Not checked";
  }
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(parsed);
}

export function justInked(iso: string | null): boolean {
  if (!iso) {
    return false;
  }
  const then = new Date(iso).getTime();
  return !Number.isNaN(then) && Date.now() - then < 8000;
}

export function windowRank(window: DeadlineWindow): string {
  if (window === "1") {
    return "1 day";
  }
  if (window === "3") {
    return "3 days";
  }
  if (window === "7") {
    return "7 days";
  }
  return "Later";
}
