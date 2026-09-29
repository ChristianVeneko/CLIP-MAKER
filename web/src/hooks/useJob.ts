import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Job } from "../api/types";

const POLL_MS = 1500;

/** Loads a job and polls it until it finishes or fails. */
export function useJob(id: string) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
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
  }, [id, attempt]);

  /** Re-queues a failed job and resumes polling. */
  const retry = useCallback(async () => {
    try {
      setJob(await api.retryJob(id));
      setError(null);
      setAttempt((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  return { job, error, retry };
}
