"""Thread-safe in-memory job store persisted as one JSON file per job."""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .progress import initial_stages, overall_percent

ID_RE = re.compile(r"^[a-f0-9]{12}$")
RESTART_ERROR = "The server was restarted before this job finished."


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._jobs: dict[str, dict] = {}
        self._load()

    # -- persistence ---------------------------------------------------------------
    def job_dir(self, job_id: str) -> Path:
        return self.root / job_id

    def _load(self) -> None:
        for path in self.root.glob("*/job.json"):
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
                if not ID_RE.match(str(job["id"])):
                    continue
            except (OSError, ValueError, KeyError):
                continue
            if job.get("status") in ("queued", "running"):
                job.update(status="failed", error=RESTART_ERROR, finished_at=job.get("finished_at") or now())
                self._write(job)
            self._jobs[job["id"]] = job

    def _write(self, job: dict) -> None:
        d = self.job_dir(job["id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "job.json.tmp"
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, d / "job.json")

    # -- queries -------------------------------------------------------------------
    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return json.loads(json.dumps(job)) if job else None

    def list(self) -> list[dict]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: (j["created_at"], j["seq"]), reverse=True)
            return json.loads(json.dumps(jobs))

    # -- transitions -----------------------------------------------------------------
    def create(self, source: dict, options: dict, has_download: bool, has_transcribe: bool) -> dict:
        with self._lock:
            job = {
                "id": new_id(),
                "seq": len(self._jobs),
                "status": "queued",
                "stage": None,
                "percent": 0,
                "message": "Queued",
                "stages": initial_stages(has_download, has_transcribe),
                "source": source,
                "options": options,
                "clips": [],
                "error": None,
                "created_at": now(),
                "finished_at": None,
            }
            self._jobs[job["id"]] = job
            self._write(job)
            return json.loads(json.dumps(job))

    def _update(self, job_id: str, fn) -> None:
        with self._lock:
            job = self._jobs[job_id]
            fn(job)
            self._write(job)

    def mark_running(self, job_id: str) -> None:
        self._update(job_id, lambda j: j.update(status="running", message="Starting"))

    def report(self, job_id: str, stage: str, fraction: float, message: str = "") -> None:
        def apply(job: dict) -> None:
            reached = False
            for s in job["stages"]:
                if s["id"] == stage:
                    reached = True
                    s["status"] = "done" if fraction >= 1.0 and stage == "render" else "running"
                elif s["status"] != "skipped":
                    s["status"] = "pending" if reached else "done"
            job["stage"] = stage
            job["message"] = message or job["message"]
            job["percent"] = max(job["percent"], min(99, overall_percent(job["stages"], stage, fraction)))

        self._update(job_id, apply)

    def mark_done(self, job_id: str, clips: list[dict]) -> None:
        def apply(job: dict) -> None:
            for s in job["stages"]:
                if s["status"] != "skipped":
                    s["status"] = "done"
            job.update(status="done", percent=100, clips=clips, message="Done", finished_at=now())

        self._update(job_id, apply)

    def mark_failed(self, job_id: str, error: str) -> None:
        self._update(job_id, lambda j: j.update(status="failed", error=error, message="Failed", finished_at=now()))
