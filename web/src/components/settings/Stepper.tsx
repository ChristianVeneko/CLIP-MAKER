interface Props {
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
  label: string;
}

export function Stepper({ value, min, max, onChange, label }: Props) {
  const set = (v: number) => onChange(Math.min(max, Math.max(min, v)));
  return (
    <div className="stepper" role="group" aria-label={label}>
      <button type="button" className="step-btn" aria-label="Disminuir" disabled={value <= min} onClick={() => set(value - 1)}>
        −
      </button>
      <output className="step-value" aria-live="polite">
        {value}
      </output>
      <button type="button" className="step-btn" aria-label="Aumentar" disabled={value >= max} onClick={() => set(value + 1)}>
        +
      </button>
      <input
        className="step-slider"
        type="range"
        min={min}
        max={max}
        value={value}
        aria-label={label}
        onChange={(e) => set(Number(e.target.value))}
      />
    </div>
  );
}
