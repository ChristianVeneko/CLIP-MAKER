import type { VideoSource } from "../api/types";
import { formatClock } from "../lib/time";

interface Props {
  source: VideoSource;
  onClear: () => void;
}

export function SourceCard({ source, onClear }: Props) {
  return (
    <div className="source-card">
      {source.thumbnail ? (
        <img className="source-thumb" src={source.thumbnail} alt="" referrerPolicy="no-referrer" />
      ) : (
        <div className="source-thumb" />
      )}
      <div className="source-info">
        <div className="source-title">{source.title}</div>
        <div className="source-meta">
          {formatClock(source.duration)} · {source.kind === "url" ? "YouTube" : "Archivo local"}
        </div>
      </div>
      <button className="btn btn-sm btn-ghost" onClick={onClear}>
        Cambiar video
      </button>
    </div>
  );
}
