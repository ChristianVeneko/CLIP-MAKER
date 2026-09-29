import { useState } from "react";
import { api } from "../api/client";
import type { AppConfig } from "../api/types";
import { GenerateBar } from "../components/GenerateBar";
import { Hero } from "../components/Hero";
import { NoKeyBanner } from "../components/NoKeyBanner";
import { SourceCard } from "../components/SourceCard";
import { SettingsPanel } from "../components/settings/SettingsPanel";
import { RecentJobsContainer } from "./RecentJobsContainer";
import { useJobSettings } from "../hooks/useJobSettings";
import { useVideoSource } from "../hooks/useVideoSource";
import { generateBlocker } from "../lib/validation";

interface Props {
  config: AppConfig;
  onJobCreated: (id: string) => void;
}

export function CreateJobContainer({ config, onJobCreated }: Props) {
  const video = useVideoSource();
  const job = useJobSettings();
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const blocker = generateBlocker(job.settings, config.openai_key_present);

  const generate = async () => {
    if (!video.source) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api.createJob(video.source, job.settings);
      onJobCreated(created.id);
    } catch (e) {
      setSubmitError((e as Error).message);
      setSubmitting(false);
    }
  };

  return (
    <main className="container">
      {!config.openai_key_present && <NoKeyBanner />}
      {!video.source && (
        <Hero
          url={video.url}
          busy={video.busy}
          error={video.error}
          onUrlChange={video.setUrl}
          onSubmit={video.probe}
          onFile={video.upload}
        />
      )}
      {video.source && (
        <>
          <SourceCard source={video.source} onClear={video.clear} />
          <SettingsPanel
            config={config}
            settings={job.settings}
            duration={video.source.duration}
            srtBusy={job.srtBusy}
            srtError={job.srtError}
            onChange={job.update}
            onSrtFile={job.uploadSrt}
            onSrtRemove={job.removeSrt}
          />
          <GenerateBar blocker={blocker} busy={submitting} error={submitError} onGenerate={generate} />
        </>
      )}
      {!video.source && <RecentJobsContainer onOpen={onJobCreated} />}
    </main>
  );
}
