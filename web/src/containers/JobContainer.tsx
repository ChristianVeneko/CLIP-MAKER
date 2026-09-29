import { ProgressView } from "../components/job/ProgressView";
import { ResultsGallery } from "../components/job/ResultsGallery";
import { useJob } from "../hooks/useJob";

interface Props {
  id: string;
  onBack: () => void;
}

export function JobContainer({ id, onBack }: Props) {
  const { job, error } = useJob(id);
  return (
    <main className="container">
      <button className="btn btn-sm btn-ghost back" onClick={onBack}>
        ← Nuevo video
      </button>
      {error && !job && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}
      {!job && !error && <p className="muted">Cargando…</p>}
      {job && job.status !== "done" && <ProgressView job={job} />}
      {job && job.status === "done" && <ResultsGallery job={job} />}
    </main>
  );
}
