import type { AspectRatio, StageId } from "../api/types";

export const GENRE_LABELS: Record<string, string> = {
  podcast: "Podcast",
  interview: "Entrevista",
  educational: "Educativo",
  comedy: "Comedia",
  motivational: "Motivacional",
  gaming: "Videojuegos",
  sports: "Deportes",
  news: "Noticias",
  vlog: "Vlog",
  other: "Otro",
};

export const CLIP_LENGTH_LABELS: Record<string, string> = {
  auto: "Auto",
  "<30s": "<30 s",
  "30-60s": "30–60 s",
  "60-90s": "60–90 s",
  "90s-3m": "90 s–3 min",
};

export const STAGE_LABELS: Record<StageId, string> = {
  download: "Descarga",
  transcribe: "Transcripción",
  select: "Selección de momentos",
  render: "Renderizado",
};

export const ASPECT_HINTS: Record<AspectRatio, string> = {
  "9:16": "Vertical",
  "1:1": "Cuadrado",
  "4:5": "Retrato",
  "16:9": "Horizontal",
};

const displayNames =
  typeof Intl !== "undefined" && "DisplayNames" in Intl ? new Intl.DisplayNames(["es"], { type: "language" }) : null;

export function languageLabel(code: string, fallback: string): string {
  if (code === "auto") return "Automático";
  const name = displayNames?.of(code) ?? fallback;
  return name.charAt(0).toUpperCase() + name.slice(1);
}

export const STATUS_LABELS = {
  queued: "En cola",
  running: "Procesando",
  done: "Listo",
  failed: "Con error",
} as const;
