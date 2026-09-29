import type { AppConfig } from "../api/types";
import { Hero } from "../components/Hero";
import { NoKeyBanner } from "../components/NoKeyBanner";
import { SourceCard } from "../components/SourceCard";
import { useVideoSource } from "../hooks/useVideoSource";

interface Props {
  config: AppConfig;
}

export function CreateJobContainer({ config }: Props) {
  const video = useVideoSource();
  return (
    <main className="container">
      {!config.openai_key_present && <NoKeyBanner />}
      <Hero
        url={video.url}
        busy={video.busy}
        error={video.error}
        onUrlChange={video.setUrl}
        onSubmit={video.probe}
        onFile={video.upload}
      />
      {video.source && <SourceCard source={video.source} onClear={video.clear} />}
    </main>
  );
}
