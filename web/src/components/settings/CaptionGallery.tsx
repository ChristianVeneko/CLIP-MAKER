import type { CaptionPreset } from "../../api/types";
import { useCaptionFonts } from "../../hooks/useCaptionFonts";
import { CaptionCard } from "./CaptionCard";

interface Props {
  presets: CaptionPreset[];
  value: string;
  onChange: (id: string) => void;
}

export function CaptionGallery({ presets, value, onChange }: Props) {
  useCaptionFonts(presets);
  // "none" first, as in the Opus Clip picker
  const ordered = [...presets.filter((p) => p.id === "none"), ...presets.filter((p) => p.id !== "none")];
  return (
    <div className="cap-grid" role="radiogroup" aria-label="Estilo de subtítulos">
      {ordered.map((p) => (
        <CaptionCard key={p.id} preset={p} selected={p.id === value} onSelect={onChange} />
      ))}
    </div>
  );
}
