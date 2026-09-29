import type { Job } from "../../api/types";
import { ClipCard } from "./ClipCard";

export function ResultsGallery({ job }: { job: Job }) {
  const wide = job.options.aspect_ratio === "16:9";
  return (
    <section aria-label="Clips generados">
      <div className="results-head">
        <h2 className="panel-title">
          {job.clips.length} {job.clips.length === 1 ? "clip listo" : "clips listos"}
        </h2>
        <p className="muted">{job.source.title}</p>
      </div>
      <div className={`clip-grid${wide ? " is-wide" : ""}`}>
        {job.clips.map((c) => (
          <ClipCard key={c.index} clip={c} aspect={job.options.aspect_ratio} />
        ))}
      </div>
    </section>
  );
}
