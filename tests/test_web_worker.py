from clipmaker.web.store import JobStore
from clipmaker.web.worker import JobWorker


def new_job(store):
    return store.create(source={"type": "url", "url": "u"}, options={}, has_download=True, has_transcribe=True)


def test_worker_runs_job_to_done(tmp_path):
    store = JobStore(tmp_path)

    def runner(job, report):
        report("download", 1.0, "d")
        report("render", 0.5, "clip 1/2")
        return [{"title": "A", "video": "01_a.mp4"}]

    worker = JobWorker(store, runner)
    worker.start()
    job = new_job(store)
    worker.submit(job["id"])
    worker.wait_idle()
    cur = store.get(job["id"])
    assert cur["status"] == "done" and cur["clips"][0]["title"] == "A"
    worker.stop()


def test_worker_marks_failure_with_message(tmp_path):
    store = JobStore(tmp_path)

    def runner(job, report):
        raise RuntimeError("yt-dlp could not download")

    worker = JobWorker(store, runner)
    worker.start()
    job = new_job(store)
    worker.submit(job["id"])
    worker.wait_idle()
    cur = store.get(job["id"])
    assert cur["status"] == "failed" and "yt-dlp could not download" in cur["error"]
    worker.stop()


def test_worker_processes_queue_in_order_one_at_a_time(tmp_path):
    store = JobStore(tmp_path)
    order, active = [], []

    def runner(job, report):
        active.append(1)
        assert len(active) == 1
        order.append(job["id"])
        active.pop()
        return []

    worker = JobWorker(store, runner)
    worker.start()
    jobs = [new_job(store) for _ in range(3)]
    for j in jobs:
        worker.submit(j["id"])
    worker.wait_idle()
    assert order == [j["id"] for j in jobs]
    assert all(store.get(j["id"])["status"] == "done" for j in jobs)
    worker.stop()


def test_worker_survives_failure_and_continues(tmp_path):
    store = JobStore(tmp_path)

    def runner(job, report):
        if job["options"].get("boom"):
            raise ValueError("bad")
        return []

    worker = JobWorker(store, runner)
    worker.start()
    a = store.create(source={}, options={"boom": True}, has_download=True, has_transcribe=True)
    b = new_job(store)
    worker.submit(a["id"])
    worker.submit(b["id"])
    worker.wait_idle()
    assert store.get(a["id"])["status"] == "failed"
    assert store.get(b["id"])["status"] == "done"
    worker.stop()


def test_worker_stores_friendly_message_for_openai_errors(tmp_path):
    import httpx
    import openai

    store = JobStore(tmp_path)

    def runner(job, report):
        req = httpx.Request("POST", "https://api.openai.com/v1/x")
        raise openai.PermissionDeniedError(
            "Error code: 403", response=httpx.Response(403, request=req),
            body={"code": "unsupported_country_region_territory"},
        )

    worker = JobWorker(store, runner)
    worker.start()
    job = new_job(store)
    worker.submit(job["id"])
    worker.wait_idle()
    worker.stop()
    assert "VPN" in store.get(job["id"])["error"]
