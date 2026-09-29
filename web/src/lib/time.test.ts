import { describe, expect, it } from "vitest";
import { formatClock, formatDuration, parseClock } from "./time";

describe("formatClock", () => {
  it("formats mm:ss and h:mm:ss", () => {
    expect(formatClock(0)).toBe("0:00");
    expect(formatClock(65)).toBe("1:05");
    expect(formatClock(3725)).toBe("1:02:05");
  });
  it("floors fractions and clamps negatives", () => {
    expect(formatClock(59.9)).toBe("0:59");
    expect(formatClock(-4)).toBe("0:00");
  });
});

describe("formatDuration", () => {
  it("uses a compact Spanish form", () => {
    expect(formatDuration(45)).toBe("45 s");
    expect(formatDuration(125)).toBe("2 min 5 s");
    expect(formatDuration(3600)).toBe("1 h");
    expect(formatDuration(3725)).toBe("1 h 2 min");
  });
});

describe("parseClock", () => {
  it("parses clock strings and bare seconds", () => {
    expect(parseClock("10:30")).toBe(630);
    expect(parseClock("1:02:03")).toBe(3723);
    expect(parseClock("90")).toBe(90);
  });
  it("returns null for garbage", () => {
    expect(parseClock("abc")).toBeNull();
    expect(parseClock("1:75")).toBeNull();
  });
});
