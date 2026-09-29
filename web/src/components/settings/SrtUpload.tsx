import { useRef } from "react";
import type { UploadedSrt } from "../../api/types";

interface Props {
  srt: UploadedSrt | null;
  busy: boolean;
  error: string | null;
  onFile: (file: File) => void;
  onRemove: () => void;
}

export function SrtUpload({ srt, busy, error, onFile, onRemove }: Props) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className="srt">
      {srt ? (
        <span className="file-chip">
          <span aria-hidden>📄</span>
          <span className="file-name">{srt.filename}</span>
          <button type="button" aria-label="Quitar archivo SRT" onClick={onRemove}>
            ×
          </button>
        </span>
      ) : (
        <button type="button" className="btn btn-sm" disabled={busy} onClick={() => input.current?.click()}>
          {busy ? "Subiendo…" : "Subir SRT"}
        </button>
      )}
      <input
        ref={input}
        type="file"
        accept=".srt"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.target.value = "";
        }}
      />
      {srt && <p className="field-hint">Se omitirá la transcripción: se usarán los subtítulos de este archivo.</p>}
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
