import { describe, expect, it } from "vitest";
import { inr, label, shortDate, tone } from "./format";

describe("inr", () => {
  it("groups digits the Indian way", () => {
    expect(inr(12345678)).toBe("₹1,23,456.78");
    expect(inr(100)).toBe("₹1.00");
    expect(inr(99)).toBe("₹0.99");
    expect(inr(100000000)).toBe("₹10,00,000.00");
  });
  it("shows the sign of negatives and optionally of positives", () => {
    expect(inr(-250)).toBe("-₹2.50");
    expect(inr(250, { signed: true })).toBe("+₹2.50");
    expect(inr(0, { signed: true })).toBe("₹0.00");
  });
  it("shows a dash for missing values", () => {
    expect(inr(null)).toBe("-");
    expect(inr(undefined)).toBe("-");
  });
});

describe("shortDate", () => {
  it("formats an ISO date without timezone drift", () => {
    expect(shortDate("2026-09-05")).toBe("05 Sep 2026");
  });
  it("handles missing", () => expect(shortDate(null)).toBe("-"));
});

describe("label and tone", () => {
  it("makes codes readable", () => expect(label("PARTIALLY_PAID")).toBe("Partially paid"));
  it("maps statuses to tones", () => {
    expect(tone("PAID")).toBe("ok");
    expect(tone("OVERDUE")).toBe("bad");
    expect(tone("ISSUED")).toBe("warn");
    expect(tone("VOID")).toBe("mute");
  });
});
