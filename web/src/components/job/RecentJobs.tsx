import type { JobSummary } from "../../api/types";
import { STATUS_LABELS } from "../../lib/labels";

interface Props {
  jobs: JobSummary[];
  onOpen: (id: string) => void;
  onRetry: (id: string) => void;
}

export function RecentJobs({ jobs, onOpen, onRetry }: Props) {
  if (jobs.length === 0) return null;
  return (
    <section className="recent" aria-label="Trabajos recientes">
      <h2 className="panel-title">Trabajos recientes</h2>
      <ul className="recent-list">
        {jobs.slice(0, 8).map((j) => {
          const thumb = j.cover ?? j.source.thumbnail;
          return (
            <li key={j.id} className="recent-row">
              <button className="recent-item" onClick={() => onOpen(j.id)}>
                {thumb ? <img src={thumb} alt="" loading="lazy" referrerPolicy="no-referrer" /> : <span className="recent-ph" />}
                <span className="recent-info">
                  <span className="recent-title">{j.source.title ?? "Video"}</span>
                  <span className="muted">
                    {j.status === "done" ? `${j.clip_count} clips` : j.status === "running" ? `${j.percent}%` : ""}
                  </span>
                  {j.status === "failed" && j.error && <span className="recent-error">{j.error}</span>}
                </span>
                <span className={`status-pill is-${j.status}`}>{STATUS_LABELS[j.status]}</span>
              </button>
              {j.status === "failed" && (
                <button className="btn btn-sm" onClick={() => onRetry(j.id)}>
                  Reintentar
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
