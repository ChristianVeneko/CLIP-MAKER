import { describe, expect, it } from "vitest";
import { kindLabel, platformLabel, sourceSubtitle } from "./platform";

describe("platformLabel", () => {
  it("names the known platforms", () => {
    expect(platformLabel("youtube")).toBe("YouTube");
    expect(platformLabel("twitch")).toBe("Twitch");
    expect(platformLabel("kick")).toBe("Kick");
  });
  it("falls back to a generic label", () => {
    expect(platformLabel("other")).toBe("Enlace");
    expect(platformLabel(undefined)).toBe("Enlace");
  });
});

describe("kindLabel", () => {
  it("translates clip and vod", () => {
    expect(kindLabel("clip")).toBe("Clip");
    expect(kindLabel("vod")).toBe("VOD");
    expect(kindLabel(undefined)).toBe("");
  });
});

describe("sourceSubtitle", () => {
  it("joins duration, kind and uploader", () => {
    expect(sourceSubtitle({ duration: 27, kind: "clip", uploader: "elxokas" })).toBe("0:27 · Clip · elxokas");
  });
  it("omits missing parts", () => {
    expect(sourceSubtitle({ duration: 3725 })).toBe("1:02:05");
  });
});
