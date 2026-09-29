import { useEffect, useState } from "react";

/** Seconds since `key` last changed, ticking once per second while `active`. */
export function useElapsed(key: string | null, active: boolean): number {
  const [start, setStart] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setStart(Date.now());
    setNow(Date.now());
  }, [key]);

  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);

  return Math.max(0, Math.floor((now - start) / 1000));
}
