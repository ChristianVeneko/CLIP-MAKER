import type { CaptionPreset } from "../../api/types";
import { CaptionSample } from "./CaptionSample";

interface Props {
  preset: CaptionPreset;
  selected: boolean;
  onSelect: (id: string) => void;
}

export function CaptionCard({ preset, selected, onSelect }: Props) {
  const isNone = preset.id === "none";
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      className={`cap-card${selected ? " is-selected" : ""}`}
      onClick={() => onSelect(preset.id)}
    >
      <span className="cap-stage">
        {isNone ? (
          <svg width="34" height="34" viewBox="0 0 34 34" fill="none" stroke="currentColor" strokeWidth="2.6" aria-hidden>
            <circle cx="17" cy="17" r="12" />
            <path d="M8.5 25.5l17-17" />
          </svg>
        ) : (
          <CaptionSample preset={preset} />
        )}
      </span>
      <span className="cap-name">{isNone ? "Sin subtítulos" : preset.name}</span>
    </button>
  );
}
