import type { CSSProperties } from "react";
import type { CaptionPreset } from "../../api/types";
import { fontFace } from "../../hooks/useCaptionFonts";

const SIZE_BOOST = 1.45; // the mini card is much smaller than a real 1080px frame

interface Props {
  preset: CaptionPreset;
}

/** Live CSS approximation of a caption preset, using the catalog as the only source of truth. */
export function CaptionSample({ preset }: Props) {
  const emCqw = preset.size_ratio * SIZE_BOOST * 100; // font size in container-width units
  const em = `${emCqw}cqw`;
  const c = preset.colors;
  const text = c.text ?? "#fff";
  const active = c.active ?? text;
  const stack = preset.fill_mode === "none" && !!c.line2;
  const base: CSSProperties = {
    fontFamily: `"${fontFace(preset)}", system-ui, sans-serif`,
    fontSize: em,
    fontStyle: preset.italic ? "italic" : "normal",
    textTransform: preset.uppercase ? "uppercase" : "none",
    color: text,
    lineHeight: 1.1,
    textAlign: "center",
  };
  if (preset.outline_ratio > 0) {
    base.WebkitTextStroke = `${(emCqw * preset.outline_ratio * 1.7).toFixed(2)}cqw ${c.outline ?? "#000"}`;
    base.paintOrder = "stroke fill";
  }
  if (preset.shadow_ratio > 0) {
    base.textShadow = `0 ${(emCqw * preset.shadow_ratio * 3).toFixed(2)}cqw 0 rgba(0,0,0,0.55)`;
  }
  const wordStyle: CSSProperties = { color: active };
  if (preset.box === "word") {
    Object.assign(wordStyle, { background: c.box, borderRadius: "0.22em", padding: "0 0.18em" });
  }
  if (stack) wordStyle.color = c.line2;
  const boxStyle: CSSProperties =
    preset.box === "line" ? { background: c.box, borderRadius: "0.3em", padding: "0.12em 0.4em" } : {};
  return (
    <span className="cap-sample" style={{ ...base, ...boxStyle }}>
      <span>Empieza</span>
      {stack ? <br /> : " "}
      <span style={wordStyle}>aquí</span>
    </span>
  );
}
