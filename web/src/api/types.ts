export type ModelTier = "powerful" | "light";
export type AspectRatio = "9:16" | "1:1" | "4:5" | "16:9";

export interface CaptionPreset {
  id: string;
  name: string;
  font_family: string;
  font_file: string;
  font_url: string;
  uppercase: boolean;
  italic: boolean;
  fill_mode: "active" | "progressive" | "none";
  box: "none" | "line" | "word";
  max_lines: number;
  max_words: number;
  size_ratio: number;
  outline_ratio: number;
  shadow_ratio: number;
  pop: string;
  colors: { text?: string; active?: string; outline?: string; box?: string; line2?: string };
}

export interface LanguageOption {
  code: string;
  name: string;
}

export interface AppConfig {
  openai_key_present: boolean;
  models: Record<ModelTier, string>;
  caption_presets: CaptionPreset[];
  genres: string[];
  clip_lengths: string[];
  aspect_ratios: AspectRatio[];
  languages: LanguageOption[];
}

export interface ProbeResult {
  id: string;
  title: string;
  duration: number;
  thumbnail: string;
  platform: "youtube" | "twitch" | "kick" | "other";
  kind: "clip" | "vod";
  uploader: string;
}

export interface UploadedVideo {
  id: string;
  title: string;
  duration: number;
  thumbnail: string;
}

export interface UploadedSrt {
  id: string;
  filename: string;
}

/** The video the user picked, either by URL or by uploading a file. */
export type VideoSource =
  | {
      kind: "url";
      url: string;
      title: string;
      duration: number;
      thumbnail: string;
      platform: ProbeResult["platform"];
      contentKind: ProbeResult["kind"];
      uploader: string;
    }
  | { kind: "upload"; uploadId: string; title: string; duration: number; thumbnail: string };

export interface JobSettings {
  model_tier: ModelTier;
  genre: string;
  clip_length: string;
  max_clips: number;
  auto_zoom: boolean;
  specific_moments: string;
  /** Selected window in seconds; null means the whole video. */
  time_range: [number, number] | null;
  aspect_ratio: AspectRatio;
  language: string;
  srt: UploadedSrt | null;
  caption_style: string;
}

export type JobStatus = "queued" | "running" | "done" | "failed";
export type StageId = "download" | "transcribe" | "select" | "render";
export type StageStatus = "pending" | "running" | "done" | "skipped";

export interface Stage {
  id: StageId;
  status: StageStatus;
}

export interface Clip {
  index: number;
  title: string;
  score: number;
  hook: string;
  start: number;
  end: number;
  duration: number;
  video_url: string;
  thumbnail_url: string;
  download_url: string;
}

export interface JobSummary {
  id: string;
  status: JobStatus;
  stage: StageId | null;
  percent: number;
  message: string;
  stages: Stage[];
  source: { type: "url" | "upload"; title: string | null; thumbnail: string | null; duration: number | null };
  error: string | null;
  created_at: string;
  clip_count: number;
  cover: string | null;
}

export interface Job extends JobSummary {
  clips: Clip[];
  options: { aspect_ratio: AspectRatio; caption_style: string };
}
