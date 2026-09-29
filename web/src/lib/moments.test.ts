import { describe, expect, it } from "vitest";
import { hasExplicitRanges } from "./moments";

describe("hasExplicitRanges", () => {
  it("detects mm:ss ranges", () => {
    expect(hasExplicitRanges("10:30-11:15")).toBe(true);
    expect(hasExplicitRanges("10:40-11:35, 6:10-6:58")).toBe(true);
    expect(hasExplicitRanges("el chiste de 1:00 a 1:30")).toBe(true);
    expect(hasExplicitRanges("1:02:00 - 1:03:10")).toBe(true);
  });
  it("ignores plain text and bare numbers", () => {
    expect(hasExplicitRanges("")).toBe(false);
    expect(hasExplicitRanges("la parte graciosa")).toBe(false);
    expect(hasExplicitRanges("top 10-15")).toBe(false);
  });
  it("ignores reversed ranges", () => {
    expect(hasExplicitRanges("11:00-10:00")).toBe(false);
  });
});
