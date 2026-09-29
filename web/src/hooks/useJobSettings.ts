import { useCallback, useState } from "react";
import { api } from "../api/client";
import type { JobSettings } from "../api/types";
import { defaultSettings } from "../lib/validation";

export function useJobSettings() {
  const [settings, setSettings] = useState<JobSettings>(defaultSettings);
  const [srtBusy, setSrtBusy] = useState(false);
  const [srtError, setSrtError] = useState<string | null>(null);

  const update = useCallback((patch: Partial<JobSettings>) => setSettings((s) => ({ ...s, ...patch })), []);

  const uploadSrt = useCallback(async (file: File) => {
    setSrtBusy(true);
    setSrtError(null);
    try {
      const srt = await api.uploadSrt(file);
      setSettings((s) => ({ ...s, srt }));
    } catch (e) {
      setSrtError((e as Error).message);
    } finally {
      setSrtBusy(false);
    }
  }, []);

  const removeSrt = useCallback(() => setSettings((s) => ({ ...s, srt: null })), []);

  return { settings, update, srtBusy, srtError, uploadSrt, removeSrt };
}
