import { describe, expect, it } from "vitest";
import { defaultSettings, generateBlocker } from "./validation";

describe("generateBlocker", () => {
  it("allows generation with a key", () => {
    expect(generateBlocker(defaultSettings(), true)).toBeNull();
  });
  it("blocks without a key unless explicit ranges are present", () => {
    const s = defaultSettings();
    expect(generateBlocker(s, false)).toMatch(/OPENAI_API_KEY/);
    expect(generateBlocker({ ...s, specific_moments: "la parte graciosa" }, false)).toMatch(/OPENAI_API_KEY/);
    expect(generateBlocker({ ...s, specific_moments: "10:40-11:35, 6:10-6:58" }, false)).toBeNull();
  });
  it("blocks a processing window that is too short", () => {
    expect(generateBlocker({ ...defaultSettings(), time_range: [10, 12] }, true)).toMatch(/rango/i);
  });
});
