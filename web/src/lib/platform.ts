import { formatClock } from "./time";

export type Platform = "youtube" | "twitch" | "kick" | "other";
export type ContentKind = "clip" | "vod";

const PLATFORM_LABELS: Record<string, string> = { youtube: "YouTube", twitch: "Twitch", kick: "Kick" };

export function platformLabel(platform: string | undefined): string {
  return (platform && PLATFORM_LABELS[platform]) || "Enlace";
}

export function kindLabel(kind: string | undefined): string {
  if (kind === "clip") return "Clip";
  if (kind === "vod") return "VOD";
  return "";
}

/** "1:02:05 · VOD · channel" style line under the source title. */
export function sourceSubtitle(s: { duration: number; kind?: string; uploader?: string }): string {
  return [formatClock(s.duration), kindLabel(s.kind), s.uploader ?? ""].filter(Boolean).join(" · ");
}
