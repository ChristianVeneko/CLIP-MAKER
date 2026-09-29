"""FastAPI application: config, probing, uploads, jobs and media serving."""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..captions import FONTS_DIR, preset_catalog
from ..download import probe_url as real_probe_url
from ..paths import default_output, default_workdir
from ..options import ASPECT_RATIOS, CLIP_LENGTHS, GENRES, MODEL_DEFAULTS, resolve_model_id
from ..render import slugify
from ..selection import LANGUAGE_NAMES
from .media import MEDIA_TYPES, make_thumbnail as real_make_thumbnail, safe_media_path
from .runner import find_upload_video, run_job
from .schemas import CreateJobRequest, RequestError, build_options
from .store import ID_RE, JobStore, new_id
from .worker import JobWorker

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


def default_web_dist() -> Path | None:
    dist = Path(__file__).resolve().parents[3] / "web" / "dist"
    return dist if (dist / "index.html").exists() else None


@dataclass
class Settings:
    workdir: Path = field(default_factory=default_workdir)
    output_dir: Path = field(default_factory=default_output)
    web_dist: Path | None = field(default_factory=default_web_dist)

    @property
    def jobs_dir(self) -> Path:
        return self.output_dir / "jobs"

    @property
    def uploads_dir(self) -> Path:
        return self.workdir / "uploads"


def real_probe_file(path: Path) -> dict:
    from ..detection import probe_video

    w, h, _, duration = probe_video(path)
    return {"duration": duration, "width": w, "height": h}


@dataclass
class Services:
    """Everything with side effects, injectable so tests can use fakes."""

    probe_url: Callable[[str], dict] = real_probe_url
    probe_file: Callable[[Path], dict] = real_probe_file
    make_thumbnail: Callable[..., None] = real_make_thumbnail
    runner: Callable[[dict, Callable, Path], list[dict]] | None = None
    has_api_key: Callable[[], bool] = lambda: bool(__import__("os").environ.get("OPENAI_API_KEY"))  # noqa: E731


class ProbeRequest(BaseModel):
    url: str


def _clip_views(job: dict) -> list[dict]:
    base = f"/api/jobs/{job['id']}/media/"
    out = []
    for i, c in enumerate(job.get("clips", []), start=1):
        out.append(
            {"index": i, "title": c["title"], "score": c.get("score", 0), "hook": c.get("hook", ""),
             "start": c.get("start", 0), "end": c.get("end", 0), "duration": c.get("duration", 0),
             "video_url": base + c["video"], "thumbnail_url": base + c["thumbnail"],
             "download_url": base + c["video"] + "?download=1"}
        )  # fmt: skip
    return out


def _public(job: dict, detail: bool) -> dict:
    view = {k: v for k, v in job.items() if k not in ("seq", "clips")}
    clips = _clip_views(job)
    view["clip_count"] = len(clips)
    view["cover"] = clips[0]["thumbnail_url"] if clips else None
    if detail:
        view["clips"] = clips
    return view


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or Settings()
    services = services or Services()
    store = JobStore(settings.jobs_dir)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)

    runner = services.runner or partial(run_job, workdir=settings.workdir)

    def call_runner(job: dict, report: Callable) -> list[dict]:
        return runner(job, report, store.job_dir(job["id"]))

    worker = JobWorker(store, call_runner)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        worker.stop()

    app = FastAPI(title="clipmaker", lifespan=lifespan)
    app.state.store, app.state.worker, app.state.services = store, worker, services
    worker.start()

    fonts = {p["font_file"] for p in preset_catalog() if p["font_file"]}

    def upload_dir(upload_id: str) -> Path:
        if not ID_RE.match(upload_id):
            raise HTTPException(404, "Unknown upload")
        return settings.uploads_dir / upload_id

    def resolve_srt(upload_id: str) -> Path | None:
        if not ID_RE.match(upload_id):
            return None
        path = settings.uploads_dir / upload_id / "subs.srt"
        return path if path.is_file() else None

    def save_upload(file: UploadFile, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as fh:
            shutil.copyfileobj(file.file, fh)

    # -- config ---------------------------------------------------------------------
    @app.get("/api/config")
    def config() -> dict:
        presets = [
            {**p, "font_url": f"/api/fonts/{p['font_file']}" if p["font_file"] else ""} for p in preset_catalog()
        ]
        languages = [{"code": "auto", "name": "Auto"}] + [
            {"code": code, "name": name} for code, name in LANGUAGE_NAMES.items()
        ]
        return {
            "openai_key_present": bool(services.has_api_key()),
            "models": {tier: resolve_model_id(tier) for tier in MODEL_DEFAULTS},
            "caption_presets": presets,
            "genres": list(GENRES),
            "clip_lengths": list(CLIP_LENGTHS),
            "aspect_ratios": list(ASPECT_RATIOS),
            "languages": languages,
        }

    @app.get("/api/fonts/{name}")
    def font(name: str) -> FileResponse:
        if name not in fonts or not (FONTS_DIR / name).is_file():
            raise HTTPException(404, "Unknown font")
        return FileResponse(FONTS_DIR / name, media_type="font/ttf", headers={"Cache-Control": "public, max-age=86400"})

    # -- sources ----------------------------------------------------------------------
    @app.post("/api/probe")
    def probe(req: ProbeRequest) -> dict:
        try:
            return services.probe_url(req.url.strip())
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, str(exc) or "Could not read that URL") from exc

    @app.post("/api/uploads/video")
    def upload_video(file: UploadFile = File(...)) -> dict:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in VIDEO_EXTS:
            raise HTTPException(400, f"Unsupported video type. Allowed: {', '.join(sorted(VIDEO_EXTS))}")
        uid = new_id()
        target = settings.uploads_dir / uid / f"source{ext}"
        save_upload(file, target)
        try:
            meta = services.probe_file(target)
            services.make_thumbnail(target, target.parent / "thumb.jpg", min(1.0, (meta["duration"] or 0) / 2))
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(target.parent, ignore_errors=True)
            raise HTTPException(400, f"Could not read this video: {exc}") from exc
        return {
            "id": uid, "title": file.filename, "duration": meta["duration"],
            "thumbnail": f"/api/uploads/{uid}/thumbnail",
        }  # fmt: skip

    @app.post("/api/uploads/srt")
    def upload_srt(file: UploadFile = File(...)) -> dict:
        if Path(file.filename or "").suffix.lower() != ".srt":
            raise HTTPException(400, "The subtitle file must be an .srt")
        uid = new_id()
        save_upload(file, settings.uploads_dir / uid / "subs.srt")
        return {"id": uid, "filename": file.filename}

    @app.get("/api/uploads/{upload_id}/thumbnail")
    def upload_thumbnail(upload_id: str) -> FileResponse:
        path = upload_dir(upload_id) / "thumb.jpg"
        if not path.is_file():
            raise HTTPException(404, "No thumbnail")
        return FileResponse(path, media_type="image/jpeg")

    # -- jobs -------------------------------------------------------------------------
    @app.post("/api/jobs")
    def create_job(req: CreateJobRequest) -> dict:
        src = req.source
        if src.type == "upload":
            udir = upload_dir(src.upload_id or "")
            if not udir.is_dir() or find_upload_video(udir) is None:
                raise HTTPException(400, "The uploaded video was not found; upload it again.")
            source = {"type": "upload", "upload_id": src.upload_id, "title": src.title,
                      "duration": src.duration, "thumbnail": f"/api/uploads/{src.upload_id}/thumbnail"}  # fmt: skip
        else:
            source = {"type": "url", "url": (src.url or "").strip(), "title": src.title,
                      "duration": src.duration, "thumbnail": src.thumbnail}  # fmt: skip
        try:
            options = build_options(req, services.has_api_key(), resolve_srt)
        except RequestError as exc:
            raise HTTPException(422, str(exc)) from exc
        job = store.create(source, options.model_dump(mode="json"), src.type == "url", options.srt_path is None)
        worker.submit(job["id"])
        return _public(job, detail=True)

    def get_job(job_id: str) -> dict:
        job = store.get(job_id) if ID_RE.match(job_id) else None
        if job is None:
            raise HTTPException(404, "Unknown job")
        return job

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        return [_public(j, detail=False) for j in store.list()]

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str) -> dict:
        return _public(get_job(job_id), detail=True)

    @app.post("/api/jobs/{job_id}/retry")
    def retry_job(job_id: str) -> dict:
        job = get_job(job_id)
        if job["status"] != "failed" or not store.retry(job_id):
            raise HTTPException(409, "Only failed jobs can be retried")
        worker.submit(job_id)
        return _public(store.get(job_id), detail=True)

    @app.get("/api/jobs/{job_id}/clips")
    def job_clips(job_id: str) -> list[dict]:
        return _clip_views(get_job(job_id))

    @app.get("/api/jobs/{job_id}/media/{name}")
    def job_media(job_id: str, name: str, download: bool = Query(False)) -> FileResponse:
        job = get_job(job_id)
        path = safe_media_path(store.job_dir(job["id"]), name)
        if path is None:
            raise HTTPException(404, "Not found")
        media_type = MEDIA_TYPES[path.suffix.lower()]
        if download:
            title = next((c["title"] for c in job["clips"] if c["video"] == name), path.stem)
            return FileResponse(path, media_type=media_type, filename=f"{slugify(title)}{path.suffix}")
        return FileResponse(path, media_type=media_type)

    # -- frontend (built with `npm run build` in web/) ---------------------------------
    dist = settings.web_dist
    if dist is not None and (dist / "index.html").exists():
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(404, "Not found")
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and dist.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app
