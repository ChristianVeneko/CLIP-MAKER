import type { AspectRatio, Clip } from "../../api/types";
import { formatClock, formatDuration } from "../../lib/time";
import { ScoreBadge } from "./ScoreBadge";

interface Props {
  clip: Clip;
  aspect: AspectRatio;
}

export function ClipCard({ clip, aspect }: Props) {
  return (
    <article className="clip">
      <div className="clip-media" style={{ aspectRatio: aspect.replace(":", " / ") }}>
        <video src={clip.video_url} poster={clip.thumbnail_url} controls preload="none" playsInline />
      </div>
      <div className="clip-body">
        <div className="clip-top">
          <ScoreBadge score={clip.score} />
          <span className="muted">
            {formatDuration(clip.duration)} · {formatClock(clip.start)}–{formatClock(clip.end)}
          </span>
        </div>
        <h3 className="clip-title">{clip.title}</h3>
        {clip.hook && <p className="clip-hook">{clip.hook}</p>}
        <a className="btn btn-sm" href={clip.download_url} download>
          Descargar
        </a>
      </div>
    </article>
  );
}
