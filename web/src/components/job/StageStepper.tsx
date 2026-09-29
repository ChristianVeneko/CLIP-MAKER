import type { Stage } from "../../api/types";
import { STAGE_LABELS } from "../../lib/labels";

interface Props {
  stages: Stage[];
  failed?: boolean;
}

function Icon({ status, failed }: { status: Stage["status"]; failed?: boolean }) {
  if (status === "done") return <span className="stage-dot is-done">✓</span>;
  if (status === "running") return <span className={`stage-dot is-running${failed ? " is-failed" : ""}`}>{failed ? "!" : ""}</span>;
  return <span className="stage-dot" />;
}

export function StageStepper({ stages, failed }: Props) {
  return (
    <ol className="stages">
      {stages.map((s) => (
        <li key={s.id} className={`stage is-${s.status}`}>
          <Icon status={s.status} failed={failed} />
          <span className="stage-label">{STAGE_LABELS[s.id]}</span>
          {s.status === "skipped" && <small>Omitido</small>}
        </li>
      ))}
    </ol>
  );
}
