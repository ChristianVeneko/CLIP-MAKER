import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Job } from "../api/types";

const POLL_MS = 1500;

/** Loads a job and polls it until it finishes or fails. */
export function useJob(id: string) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setJob(null);
    setError(null);
    const tick = async () => {
      try {
        const next = await api.job(id);
        if (cancelled) return;
        setJob(next);
        if (next.status === "queued" || next.status === "running") timer = setTimeout(tick, POLL_MS);
      } catch (e) {
        if (cancelled) return;
        setError((e as Error).message);
        timer = setTimeout(tick, POLL_MS * 2);
      }
    };
    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  return { job, error };
}
