import type { JobSettings } from "../api/types";
import { hasExplicitRanges } from "./moments";

export const MIN_WINDOW_SECONDS = 5;

export function defaultSettings(): JobSettings {
  return {
    model_tier: "powerful",
    genre: "podcast",
    clip_length: "auto",
    max_clips: 5,
    auto_zoom: false,
    specific_moments: "",
    time_range: null,
    aspect_ratio: "9:16",
    language: "auto",
    srt: null,
    caption_style: "mozi",
  };
}

/** Returns a Spanish reason why generation is not allowed, or null when it is. */
export function generateBlocker(s: JobSettings, hasApiKey: boolean): string | null {
  if (!hasApiKey && !hasExplicitRanges(s.specific_moments)) {
    return "Sin OPENAI_API_KEY solo puedes generar con rangos explícitos, por ejemplo 10:30-11:15 en “Momentos específicos”.";
  }
  if (s.time_range && s.time_range[1] - s.time_range[0] < MIN_WINDOW_SECONDS) {
    return "El rango de procesamiento es demasiado corto.";
  }
  return null;
}
