import { describe, expect, it } from "vitest";
import { centsToDollarInput, deadlinePhrase, dollarsToCents, formatUsd, formatWhen } from "./format";

describe("money formatting", () => {
  it("keeps cents exact", () => {
    expect(formatUsd(1260)).toBe("$12.60");
    expect(formatUsd(-320)).toBe("-$3.20");
    expect(formatUsd(0)).toBe("$0.00");
    expect(formatUsd(150000)).toBe("$1,500.00");
  });

  it("round-trips dollar inputs", () => {
    expect(dollarsToCents("5")).toBe(500);
    expect(dollarsToCents("12.60")).toBe(1260);
    expect(dollarsToCents("12.6")).toBe(1260);
    expect(dollarsToCents("12.601")).toBeNull();
    expect(centsToDollarInput(990)).toBe("9.90");
  });
});

describe("timestamps", () => {
  it("drops fractional seconds", () => {
    expect(formatWhen("2026-11-11T00:39:30.547331+00:00")).not.toContain("547331");
    expect(formatWhen(null)).toBe("Not checked");
  });
});

describe("deadline phrases", () => {
  it("names the approaching windows", () => {
    expect(deadlinePhrase("1", "2026-11-12")).toBe("2026-11-12 · due within 1 day");
    expect(deadlinePhrase("3", "2026-11-14")).toBe("2026-11-14 · due within 3 days");
    expect(deadlinePhrase("7", "2026-11-18")).toBe("2026-11-18 · due within 7 days");
    expect(deadlinePhrase("past", "2026-11-01")).toContain("passed");
    expect(deadlinePhrase(null, null)).toBe("No deadline stored");
  });
});
