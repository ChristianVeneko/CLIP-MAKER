interface Props {
  blocker: string | null;
  busy: boolean;
  error: string | null;
  onGenerate: () => void;
}

export function GenerateBar({ blocker, busy, error, onGenerate }: Props) {
  return (
    <div className="generate-bar">
      <button className="btn btn-primary btn-lg" disabled={!!blocker || busy} onClick={onGenerate}>
        {busy ? "Enviando…" : "Generar clips"}
      </button>
      {blocker && <p className="field-hint">{blocker}</p>}
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
