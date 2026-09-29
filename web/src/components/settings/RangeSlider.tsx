import { formatClock, formatDuration } from "../../lib/time";

interface Props {
  min: number;
  max: number;
  value: [number, number];
  onChange: (value: [number, number]) => void;
  step?: number;
  minGap?: number;
}

export function RangeSlider({ min, max, value, onChange, step = 1, minGap = 5 }: Props) {
  const [lo, hi] = value;
  const pct = (v: number) => ((v - min) / (max - min || 1)) * 100;
  return (
    <div className="range">
      <div className="range-labels">
        <span>{formatClock(lo)}</span>
        <span className="range-length">{formatDuration(hi - lo)} seleccionados</span>
        <span>{formatClock(hi)}</span>
      </div>
      <div className="range-track">
        <div className="range-fill" style={{ left: `${pct(lo)}%`, right: `${100 - pct(hi)}%` }} />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={lo}
          aria-label="Inicio del rango"
          onChange={(e) => onChange([Math.min(Number(e.target.value), hi - minGap), hi])}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={hi}
          aria-label="Fin del rango"
          onChange={(e) => onChange([lo, Math.max(Number(e.target.value), lo + minGap)])}
        />
      </div>
    </div>
  );
}
