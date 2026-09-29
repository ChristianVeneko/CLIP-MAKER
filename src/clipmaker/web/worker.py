"""Background worker: runs queued jobs one at a time in a daemon thread."""

from __future__ import annotations

import queue
import threading
import traceback
from collections.abc import Callable

from .store import JobStore

Report = Callable[[str, float, str], None]
Runner = Callable[[dict, Report], list[dict]]


class JobWorker:
    def __init__(self, store: JobStore, runner: Runner) -> None:
        self.store = store
        self.runner = runner
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="clipmaker-worker", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._queue.put(None)
            self._thread.join(timeout=5)
            self._thread = None

    def submit(self, job_id: str) -> None:
        self._queue.put(job_id)

    def wait_idle(self) -> None:
        self._queue.join()

    def _loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                if job_id is None:
                    return
                self._run(job_id)
            finally:
                self._queue.task_done()

    def _run(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if job is None:
            return
        self.store.mark_running(job_id)

        def report(stage: str, fraction: float, message: str = "") -> None:
            self.store.report(job_id, stage, fraction, message)

        try:
            clips = self.runner(job, report)
        except BaseException as exc:  # noqa: BLE001 - a failed job must never kill the worker
            traceback.print_exc()
            detail = getattr(exc, "stderr", None)
            text = str(exc).strip() or exc.__class__.__name__
            if isinstance(detail, str) and detail.strip():
                text = f"{text} — {detail.strip().splitlines()[-1]}"
            self.store.mark_failed(job_id, text)
        else:
            self.store.mark_done(job_id, clips)
