import type { Job } from "../../api/types";
import { STATUS_LABELS } from "../../lib/labels";
import { StageStepper } from "./StageStepper";

interface Props {
  job: Job;
}

export function ProgressView({ job }: Props) {
  const failed = job.status === "failed";
  return (
    <section className="panel progress" aria-live="polite">
      <div className="progress-head">
        <div>
          <h2 className="panel-title">{failed ? "No se pudo generar" : "Generando tus clips"}</h2>
          <p className="muted">{job.source.title ?? "Video"}</p>
        </div>
        <span className={`status-pill is-${job.status}`}>{STATUS_LABELS[job.status]}</span>
      </div>
      <StageStepper stages={job.stages} failed={failed} />
      <div
        className="bar"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={job.percent}
        aria-label="Progreso"
      >
        <div className={`bar-fill${failed ? " is-failed" : ""}`} style={{ width: `${job.percent}%` }} />
      </div>
      <div className="progress-foot">
        <span className="muted">{failed ? "Se detuvo el proceso" : job.message}</span>
        <strong>{job.percent}%</strong>
      </div>
      {failed && (
        <div className="banner banner-error" role="alert">
          <span aria-hidden>⚠</span>
          <div>{job.error ?? "Ocurrió un error inesperado."}</div>
        </div>
      )}
    </section>
  );
}
