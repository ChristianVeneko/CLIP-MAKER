import type { ReactNode } from "react";

interface Props {
  label: string;
  hint?: ReactNode;
  wide?: boolean;
  children: ReactNode;
  id?: string;
}

export function Field({ label, hint, wide, children, id }: Props) {
  return (
    <div className={`field${wide ? " field-wide" : ""}`}>
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      {children}
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  );
}
