import { useRef, type FormEvent } from "react";

interface Props {
  url: string;
  busy: boolean;
  error: string | null;
  onUrlChange: (url: string) => void;
  onSubmit: () => void;
  onFile: (file: File) => void;
}

export function Hero({ url, busy, error, onUrlChange, onSubmit, onFile }: Props) {
  const fileInput = useRef<HTMLInputElement>(null);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (url.trim() && !busy) onSubmit();
  };
  return (
    <section className="hero">
      <h1>
        Convierte videos largos en <em>clips virales</em>
      </h1>
      <p>Pega un enlace de YouTube, Twitch o Kick (clips y VODs) o sube un archivo. Elegimos los mejores momentos y los subtitulamos por ti.</p>
      <form className="url-form" onSubmit={submit}>
        <input
          type="url"
          inputMode="url"
          placeholder="https://… (YouTube, Twitch o Kick)"
          aria-label="Enlace del video"
          value={url}
          onChange={(e) => onUrlChange(e.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={!url.trim() || busy}>
          {busy ? "Buscando…" : "Obtener video"}
        </button>
      </form>
      <p className="hero-alt">
        ¿Tienes el archivo?{" "}
        <button className="link-btn" type="button" onClick={() => fileInput.current?.click()}>
          Subir archivo
        </button>
      </p>
      <input
        ref={fileInput}
        type="file"
        accept="video/*,.mkv,.mov,.mp4,.webm,.m4v,.avi"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.target.value = "";
        }}
      />
      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
