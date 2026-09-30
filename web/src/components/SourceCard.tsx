import type { VideoSource } from "../api/types";
import { platformLabel, sourceSubtitle } from "../lib/platform";

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
          {source.kind === "url" ? (
            <>
              <span className={`platform-chip platform-${source.platform}`}>{platformLabel(source.platform)}</span>
              {sourceSubtitle({ duration: source.duration, kind: source.contentKind, uploader: source.uploader })}
            </>
          ) : (
            <>
              <span className="platform-chip platform-file">Archivo local</span>
              {sourceSubtitle({ duration: source.duration })}
            </>
          )}
        </div>
      </div>
      <button className="btn btn-sm btn-ghost" onClick={onClear}>
        Cambiar video
      </button>
    </div>
  );
}
