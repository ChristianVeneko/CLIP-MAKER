import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { JobSummary } from "../api/types";

export function useRecentJobs() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [nonce, setNonce] = useState(0);
  const reload = useCallback(() => setNonce((n) => n + 1), []);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      try {
        const list = await api.jobs();
        if (cancelled) return;
        setJobs(list);
        if (list.some((j) => j.status === "queued" || j.status === "running")) timer = setTimeout(tick, 3000);
      } catch {
        /* the list is a convenience; ignore transient errors */
      }
    };
    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [nonce]);
  return { jobs, reload };
}
