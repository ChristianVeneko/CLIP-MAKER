import type {
  AppConfig,
  Clip,
  Job,
  JobSettings,
  JobSummary,
  ProbeResult,
  UploadedSrt,
  UploadedVideo,
  VideoSource,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("No se pudo conectar con el servidor.", 0);
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

function fileForm(file: File): RequestInit {
  const form = new FormData();
  form.append("file", file);
  return { method: "POST", body: form };
}

/** Maps the UI state to the body of POST /api/jobs. */
export function buildCreateJobBody(source: VideoSource, s: JobSettings) {
  return {
    source:
      source.kind === "url"
        ? { type: "url", url: source.url, title: source.title, thumbnail: source.thumbnail, duration: source.duration }
        : { type: "upload", upload_id: source.uploadId, title: source.title, duration: source.duration },
    model_tier: s.model_tier,
    genre: s.genre,
    clip_length: s.clip_length,
    max_clips: s.max_clips,
    auto_zoom: s.auto_zoom,
    specific_moments: s.specific_moments,
    time_range: s.time_range,
    aspect_ratio: s.aspect_ratio,
    language: s.language,
    srt_upload_id: s.srt?.id ?? null,
    caption_style: s.caption_style,
  };
}

export const api = {
  config: () => request<AppConfig>("/api/config"),
  probe: (url: string) => request<ProbeResult>("/api/probe", json({ url })),
  uploadVideo: (file: File) => request<UploadedVideo>("/api/uploads/video", fileForm(file)),
  uploadSrt: (file: File) => request<UploadedSrt>("/api/uploads/srt", fileForm(file)),
  createJob: (source: VideoSource, settings: JobSettings) =>
    request<Job>("/api/jobs", json(buildCreateJobBody(source, settings))),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  jobs: () => request<JobSummary[]>("/api/jobs"),
  clips: (id: string) => request<Clip[]>(`/api/jobs/${id}/clips`),
};
