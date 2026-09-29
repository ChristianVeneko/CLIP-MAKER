import { useEffect } from "react";
import type { CaptionPreset } from "../api/types";

export const fontFace = (p: CaptionPreset) => `cm-${p.font_file.replace(/\.ttf$/, "")}`;

/** Registers @font-face rules for the caption fonts served by the backend. */
export function useCaptionFonts(presets: CaptionPreset[]) {
  useEffect(() => {
    const seen = new Set<string>();
    const rules = presets
      .filter((p) => p.font_url && !seen.has(p.font_file) && seen.add(p.font_file))
      .map((p) => `@font-face{font-family:"${fontFace(p)}";src:url("${p.font_url}") format("truetype");font-display:swap;}`)
      .join("\n");
    const el = document.createElement("style");
    el.dataset.captionFonts = "";
    el.textContent = rules;
    document.head.appendChild(el);
    return () => el.remove();
  }, [presets]);
}
