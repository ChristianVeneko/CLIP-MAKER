import { useCallback, useState } from "react";
import { api } from "../api/client";
import type { VideoSource } from "../api/types";

/** Owns the "pick a video" step: URL probing and local uploads. */
export function useVideoSource() {
  const [url, setUrl] = useState("");
  const [source, setSource] = useState<VideoSource | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (task: () => Promise<VideoSource>) => {
    setBusy(true);
    setError(null);
    try {
      setSource(await task());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  const probe = useCallback(
    () =>
      run(async () => {
        const trimmed = url.trim();
        const info = await api.probe(trimmed);
        return { kind: "url", url: trimmed, title: info.title, duration: info.duration, thumbnail: info.thumbnail };
      }),
    [run, url],
  );

  const upload = useCallback(
    (file: File) =>
      run(async () => {
        const up = await api.uploadVideo(file);
        return { kind: "upload", uploadId: up.id, title: up.title, duration: up.duration, thumbnail: up.thumbnail };
      }),
    [run],
  );

  const clear = useCallback(() => {
    setSource(null);
    setError(null);
  }, []);

  return { url, setUrl, source, busy, error, probe, upload, clear };
}
