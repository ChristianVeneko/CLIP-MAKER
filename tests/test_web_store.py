import json

from clipmaker.web.store import JobStore


def make(store, **kw):
    return store.create(
        source={"type": "url", "url": "https://youtu.be/x", "title": "T"},
        options={"max_clips": 3},
        has_download=True, has_transcribe=True, **kw,
    )


def test_create_and_get(tmp_path):
    store = JobStore(tmp_path)
    job = make(store)
    assert job["status"] == "queued" and job["percent"] == 0
    assert store.get(job["id"])["options"] == {"max_clips": 3}
    assert (tmp_path / job["id"] / "job.json").exists()


def test_transitions_running_progress_done(tmp_path):
    store = JobStore(tmp_path)
    job = make(store)
    store.mark_running(job["id"])
    store.report(job["id"], "transcribe", 0.5, "working")
    cur = store.get(job["id"])
    assert cur["status"] == "running" and cur["stage"] == "transcribe" and cur["message"] == "working"
    statuses = {s["id"]: s["status"] for s in cur["stages"]}
    assert statuses == {"download": "done", "transcribe": "running", "select": "pending", "render": "pending"}
    assert 0 < cur["percent"] < 100
    clips = [{"title": "A", "score": 80, "video": "01_a.mp4"}]
    store.mark_done(job["id"], clips)
    done = store.get(job["id"])
    assert done["status"] == "done" and done["percent"] == 100
    assert all(s["status"] in ("done", "skipped") for s in done["stages"])
    assert done["clips"] == clips and done["finished_at"]


def test_mark_failed_keeps_message(tmp_path):
    store = JobStore(tmp_path)
    job = make(store)
    store.mark_running(job["id"])
    store.mark_failed(job["id"], "boom: yt-dlp failed")
    cur = store.get(job["id"])
    assert cur["status"] == "failed" and cur["error"] == "boom: yt-dlp failed"


def test_percent_never_decreases(tmp_path):
    store = JobStore(tmp_path)
    job = make(store)
    store.mark_running(job["id"])
    store.report(job["id"], "select", 0.5, "")
    p = store.get(job["id"])["percent"]
    store.report(job["id"], "select", 0.1, "")
    assert store.get(job["id"])["percent"] >= p


def test_list_newest_first_and_survives_restart(tmp_path):
    store = JobStore(tmp_path)
    a = make(store)
    b = make(store)
    store.mark_running(a["id"])
    store.mark_done(a["id"], [])
    reloaded = JobStore(tmp_path)
    ids = [j["id"] for j in reloaded.list()]
    assert set(ids) == {a["id"], b["id"]}
    assert ids[0] == b["id"]
    assert reloaded.get(a["id"])["status"] == "done"


def test_unfinished_jobs_fail_after_restart(tmp_path):
    store = JobStore(tmp_path)
    a = make(store)
    b = make(store)
    store.mark_running(b["id"])
    reloaded = JobStore(tmp_path)
    for jid in (a["id"], b["id"]):
        job = reloaded.get(jid)
        assert job["status"] == "failed" and "restart" in job["error"].lower()


def test_corrupt_job_file_is_ignored(tmp_path):
    (tmp_path / "abc123abc123").mkdir()
    (tmp_path / "abc123abc123" / "job.json").write_text("{not json")
    assert JobStore(tmp_path).list() == []


def test_get_unknown_returns_none(tmp_path):
    assert JobStore(tmp_path).get("nope") is None
    assert JobStore(tmp_path).get("../etc") is None


def test_json_is_valid_on_disk(tmp_path):
    store = JobStore(tmp_path)
    job = make(store)
    data = json.loads((tmp_path / job["id"] / "job.json").read_text())
    assert data["id"] == job["id"]


def test_retry_resets_failed_job_keeping_id(tmp_path):
    store = JobStore(tmp_path)
    job = make(store)
    store.mark_running(job["id"])
    store.report(job["id"], "select", 0.0)
    store.mark_failed(job["id"], "boom")
    assert store.retry(job["id"]) is True
    j = store.get(job["id"])
    assert j["status"] == "queued" and j["error"] is None and j["finished_at"] is None
    assert j["percent"] == 0 and j["stage"] is None
    assert [s["status"] for s in j["stages"]] == ["pending"] * 4


def test_retry_only_failed_jobs(tmp_path):
    store = JobStore(tmp_path)
    job = make(store)
    assert store.retry(job["id"]) is False
    assert store.retry("aaaaaaaaaaaa") is False
