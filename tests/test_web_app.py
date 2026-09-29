import pytest
from fastapi.testclient import TestClient

from clipmaker.web.app import Services, Settings, create_app

URL_SOURCE = {"type": "url", "url": "https://youtu.be/abc"}


def fake_runner(job, report, job_dir):
    report("download", 1.0, "downloaded")
    report("render", 0.5, "clip 1/1")
    (job_dir / "01_hello.mp4").write_bytes(b"0123456789" * 100)
    (job_dir / "01_hello.jpg").write_bytes(b"\xff\xd8jpeg")
    return [{"title": "Hello", "score": 91, "hook": "Because", "start": 10.0, "end": 55.0,
             "duration": 45.0, "video": "01_hello.mp4", "thumbnail": "01_hello.jpg"}]  # fmt: skip


def failing_runner(job, report, job_dir):
    raise RuntimeError("yt-dlp could not download the video")


def make_client(tmp_path, runner=fake_runner, api_key=True):
    (tmp_path / "secret.txt").write_text("top secret")
    services = Services(
        probe_url=lambda url: {"id": "abc", "title": "A talk", "duration": 600.0, "thumbnail": "https://img/x.jpg"},
        probe_file=lambda path: {"duration": 42.0, "width": 1920, "height": 1080},
        make_thumbnail=lambda video, out, at=1.0: out.write_bytes(b"\xff\xd8thumb"),
        runner=runner,
        has_api_key=lambda: api_key,
    )
    settings = Settings(workdir=tmp_path / "work", output_dir=tmp_path / "out", web_dist=None)
    app = create_app(settings, services)
    return TestClient(app), app


def run_job(client, app, body):
    r = client.post("/api/jobs", json=body)
    assert r.status_code == 200, r.text
    app.state.worker.wait_idle()
    return r.json()["id"]


def test_config(tmp_path):
    client, _ = make_client(tmp_path)
    cfg = client.get("/api/config").json()
    assert cfg["openai_key_present"] is True
    assert set(cfg["models"]) == {"powerful", "light"}
    ids = [p["id"] for p in cfg["caption_presets"]]
    assert "mozi" in ids and "none" in ids
    mozi = next(p for p in cfg["caption_presets"] if p["id"] == "mozi")
    assert mozi["font_url"].startswith("/api/fonts/") and mozi["colors"]["active"]
    assert "podcast" in cfg["genres"] and "auto" in cfg["clip_lengths"]
    assert cfg["aspect_ratios"] == ["9:16", "1:1", "4:5", "16:9"]
    assert cfg["languages"][0]["code"] == "auto" and any(x["code"] == "es" for x in cfg["languages"])
    assert make_client(tmp_path, api_key=False)[0].get("/api/config").json()["openai_key_present"] is False


def test_fonts_served_only_from_catalog(tmp_path):
    client, _ = make_client(tmp_path)
    ok = client.get("/api/fonts/Montserrat-Black.ttf")
    assert ok.status_code == 200 and len(ok.content) > 1000
    assert client.get("/api/fonts/OFL-anton.txt").status_code == 404
    assert client.get("/api/fonts/..%2F..%2Fpyproject.toml").status_code == 404


def test_probe(tmp_path):
    client, _ = make_client(tmp_path)
    r = client.post("/api/probe", json={"url": "https://youtu.be/abc"})
    assert r.status_code == 200 and r.json()["title"] == "A talk" and r.json()["duration"] == 600.0


def test_probe_error_is_readable(tmp_path):
    client, app = make_client(tmp_path)
    app.state.services.probe_url = lambda url: (_ for _ in ()).throw(RuntimeError("Unsupported URL"))
    r = client.post("/api/probe", json={"url": "nope"})
    assert r.status_code == 400 and "Unsupported URL" in r.json()["detail"]


def test_upload_video_and_srt(tmp_path):
    client, _ = make_client(tmp_path)
    r = client.post("/api/uploads/video", files={"file": ("my talk.mp4", b"video-bytes", "video/mp4")})
    assert r.status_code == 200
    up = r.json()
    assert up["title"] == "my talk.mp4" and up["duration"] == 42.0 and up["thumbnail"].endswith(f"{up['id']}/thumbnail")
    assert client.get(up["thumbnail"]).status_code == 200
    s = client.post("/api/uploads/srt", files={"file": ("subs.srt", b"1\n00:00:01,000 --> 00:00:02,000\nhi\n", "text/plain")})
    assert s.status_code == 200 and s.json()["filename"] == "subs.srt"


def test_upload_rejects_bad_extension(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.post("/api/uploads/video", files={"file": ("x.exe", b"x", "application/octet-stream")}).status_code == 400
    assert client.post("/api/uploads/srt", files={"file": ("x.txt", b"x", "text/plain")}).status_code == 400


def test_create_job_validation(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.post("/api/jobs", json={"source": URL_SOURCE, "caption_style": "nope"}).status_code == 422
    assert client.post("/api/jobs", json={"source": {"type": "upload", "upload_id": "abcabcabcabc"}}).status_code == 400


def test_create_job_without_key_needs_ranges(tmp_path):
    client, app = make_client(tmp_path, api_key=False)
    r = client.post("/api/jobs", json={"source": URL_SOURCE, "specific_moments": "the funny part"})
    assert r.status_code == 422 and "OPENAI_API_KEY" in r.json()["detail"]
    ok = client.post("/api/jobs", json={"source": URL_SOURCE, "specific_moments": "10:40-11:35"})
    assert ok.status_code == 200
    app.state.worker.wait_idle()


def test_job_lifecycle_and_clips(tmp_path):
    client, app = make_client(tmp_path)
    jid = run_job(client, app, {"source": URL_SOURCE, "caption_style": "mozi", "auto_zoom": True, "aspect_ratio": "9:16"})
    job = client.get(f"/api/jobs/{jid}").json()
    assert job["status"] == "done" and job["percent"] == 100
    assert job["options"]["caption_style"] == "mozi" and job["options"]["auto_zoom"] is True
    clips = client.get(f"/api/jobs/{jid}/clips").json()
    assert len(clips) == 1
    c = clips[0]
    assert (c["title"], c["score"], c["hook"], c["duration"]) == ("Hello", 91, "Because", 45.0)
    v = client.get(c["video_url"])
    assert v.status_code == 200 and v.headers["content-type"].startswith("video/mp4")
    assert client.get(c["thumbnail_url"]).status_code == 200
    d = client.get(c["download_url"])
    assert d.status_code == 200 and "attachment" in d.headers["content-disposition"]
    assert [j["id"] for j in client.get("/api/jobs").json()] == [jid]


def test_media_supports_range_requests(tmp_path):
    client, app = make_client(tmp_path)
    jid = run_job(client, app, {"source": URL_SOURCE})
    r = client.get(f"/api/jobs/{jid}/media/01_hello.mp4", headers={"Range": "bytes=0-9"})
    assert r.status_code == 206 and len(r.content) == 10


def test_failed_job_surfaces_message(tmp_path):
    client, app = make_client(tmp_path, runner=failing_runner)
    jid = run_job(client, app, {"source": URL_SOURCE})
    job = client.get(f"/api/jobs/{jid}").json()
    assert job["status"] == "failed" and "yt-dlp could not download" in job["error"]


def test_unknown_job_404(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/api/jobs/aaaaaaaaaaaa").status_code == 404
    assert client.get("/api/jobs/aaaaaaaaaaaa/clips").status_code == 404


@pytest.mark.parametrize(
    "name",
    ["../job.json", "..%2Fjob.json", "%2e%2e%2f%2e%2e%2fsecret.txt", "/etc/passwd", "job.json", "..%5Cjob.json", "01_hello.mp4%00.jpg"],
)
def test_media_blocks_traversal_and_non_media(tmp_path, name):
    client, app = make_client(tmp_path)
    jid = run_job(client, app, {"source": URL_SOURCE})
    r = client.get(f"/api/jobs/{jid}/media/{name}")
    assert r.status_code in (404, 400)
    assert b"top secret" not in r.content


def test_media_rejects_bad_job_id(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.get("/api/jobs/..%2F..%2Fout/media/x.mp4").status_code == 404
    assert client.get("/api/uploads/..%2F/thumbnail").status_code == 404


def test_finished_jobs_survive_restart(tmp_path):
    client, app = make_client(tmp_path)
    jid = run_job(client, app, {"source": URL_SOURCE})
    client2, _ = make_client(tmp_path)
    assert client2.get(f"/api/jobs/{jid}").json()["status"] == "done"
    assert len(client2.get(f"/api/jobs/{jid}/clips").json()) == 1


def test_spa_fallback_serves_index_when_built(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (dist / "assets" / "a.js").write_text("console.log(1)")
    settings = Settings(workdir=tmp_path / "w", output_dir=tmp_path / "o", web_dist=dist)
    client = TestClient(create_app(settings, Services(has_api_key=lambda: True)))
    assert "app" in client.get("/").text
    assert client.get("/assets/a.js").status_code == 200
    assert "app" in client.get("/some/route").text
    assert client.get("/api/nothing").status_code == 404


def test_retry_failed_job_requeues_same_job(tmp_path):
    calls = []

    def flaky(job, report, job_dir):
        calls.append(job["id"])
        if len(calls) == 1:
            raise RuntimeError("temporary")
        return fake_runner(job, report, job_dir)

    client, app = make_client(tmp_path, runner=flaky)
    jid = run_job(client, app, {"source": URL_SOURCE})
    assert client.get(f"/api/jobs/{jid}").json()["status"] == "failed"
    r = client.post(f"/api/jobs/{jid}/retry")
    assert r.status_code == 200 and r.json()["id"] == jid and r.json()["status"] == "queued"
    app.state.worker.wait_idle()
    job = client.get(f"/api/jobs/{jid}").json()
    assert job["status"] == "done" and job["error"] is None and len(job["clips"]) == 1
    assert calls == [jid, jid] and len(client.get("/api/jobs").json()) == 1


def test_retry_rejects_non_failed_and_unknown(tmp_path):
    client, app = make_client(tmp_path)
    jid = run_job(client, app, {"source": URL_SOURCE})
    assert client.post(f"/api/jobs/{jid}/retry").status_code == 409
    assert client.post("/api/jobs/aaaaaaaaaaaa/retry").status_code == 404
