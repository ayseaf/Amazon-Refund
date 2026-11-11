import { describe, expect, it } from "vitest";
import { centsToDollars, dollarsToCents, formatDifference, formatMoney } from "./format";

describe("money formatting", () => {
  it("formats cents", () => {
    expect(formatMoney(7999)).toBe("$79.99");
    expect(formatMoney(10)).toBe("$0.10");
    expect(formatMoney(null)).toBe("—");
    expect(formatDifference(1500)).toBe("Down $15.00");
    expect(formatDifference(0)).toBe("No change");
    expect(formatDifference(null)).toBe("No current price");
  });

  it("converts dollar input to cents", () => {
    expect(dollarsToCents("5")).toBe(500);
    expect(dollarsToCents("5.5")).toBe(550);
    expect(dollarsToCents("5.50")).toBe(550);
    expect(centsToDollars(500)).toBe("5.00");
    expect(dollarsToCents("5.555")).toBeNull();
    expect(dollarsToCents("-1")).toBeNull();
    expect(dollarsToCents("")).toBeNull();
  });
});
