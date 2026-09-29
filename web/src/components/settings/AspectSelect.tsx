import { useEffect, useRef, useState } from "react";
import type { AspectRatio } from "../../api/types";
import { ASPECT_HINTS } from "../../lib/labels";

function RatioIcon({ ratio }: { ratio: AspectRatio }) {
  const [w, h] = ratio.split(":").map(Number);
  const scale = 18 / Math.max(w, h);
  const rw = w * scale;
  const rh = h * scale;
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
      <rect x={(22 - rw) / 2} y={(22 - rh) / 2} width={rw} height={rh} rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

interface Props {
  value: AspectRatio;
  options: AspectRatio[];
  onChange: (v: AspectRatio) => void;
  id?: string;
}

export function AspectSelect({ value, options, onChange, id }: Props) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  return (
    <div className="aspect" ref={root}>
      <button id={id} type="button" className="select-like" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen(!open)}>
        <RatioIcon ratio={value} />
        <span>
          {value} <small>{ASPECT_HINTS[value]}</small>
        </span>
        <span className="caret" aria-hidden>
          ▾
        </span>
      </button>
      {open && (
        <ul className="aspect-menu" role="listbox" aria-label="Relación de aspecto">
          {options.map((o) => (
            <li key={o} role="option" aria-selected={o === value}>
              <button
                type="button"
                className={o === value ? "is-active" : ""}
                onClick={() => {
                  onChange(o);
                  setOpen(false);
                }}
              >
                <RatioIcon ratio={o} />
                <span>
                  {o} <small>{ASPECT_HINTS[o]}</small>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
