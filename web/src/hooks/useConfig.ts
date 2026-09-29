import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AppConfig } from "../api/types";

export function useConfig() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.config().then(setConfig, (e: Error) => setError(e.message));
  }, []);
  return { config, error };
}
