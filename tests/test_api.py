import pytest
from fastapi.testclient import TestClient

from audio_studying import config, main, podcast

client = TestClient(main.app)

SAMPLE = "# Notes\n\n## Part A\n\n" + "alpha " * 60 + "\n\n## Part B\n\n" + "beta " * 60


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["features"]["chapters_simple"] is True


def test_index_served():
    assert client.get("/").status_code == 200


def test_chapters_from_text_simple():
    resp = client.post("/api/chapters", data={"text": SAMPLE, "mode": "simple"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Notes"
    assert [c["title"] for c in body["chapters"]] == ["Part A", "Part B"]


def test_chapters_from_file_uses_filename_as_title():
    files = {"file": ("biology.txt", b"alpha " * 300, "text/plain")}
    resp = client.post("/api/chapters", files=files, data={"mode": "simple"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "biology"


def test_chapters_requires_input():
    resp = client.post("/api/chapters", data={"mode": "simple"})
    assert resp.status_code == 400


def test_chapters_rejects_unknown_file_type():
    files = {"file": ("image.png", b"\x89PNG", "image/png")}
    resp = client.post("/api/chapters", files=files, data={"mode": "simple"})
    assert resp.status_code == 400


def test_chapters_ai_without_key(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    resp = client.post("/api/chapters", data={"text": SAMPLE, "mode": "ai"})
    assert resp.status_code == 503


def test_chapters_markdown_export():
    result = client.post("/api/chapters", data={"text": SAMPLE, "mode": "simple"}).json()
    resp = client.post("/api/chapters/markdown", json=result)
    assert resp.status_code == 200
    assert "## 1. Part A" in resp.text


def test_audio_without_keys(monkeypatch):
    monkeypatch.setattr(config, "ELEVEN_API_KEY", "")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    resp = client.post("/api/audio", data={"text": "hello"})
    assert resp.status_code == 503


@pytest.fixture
def fake_audio_stack(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "require_audio_stack", lambda: None)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(
        podcast,
        "generate_script",
        lambda text: [{"narrator": "Host", "text": "Hi"}, {"narrator": "Expert", "text": "Hello"}],
    )
    monkeypatch.setattr(podcast, "synthesize_line", lambda text, voice: b"mp3:" + text.encode())
    monkeypatch.setattr(podcast, "merge_audio", lambda segments: b"".join(segments))


def test_audio_from_text(fake_audio_stack, tmp_path):
    resp = client.post("/api/audio", data={"text": "Some chapter text"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["audio_url"].startswith("/output/podcast_")
    assert len(body["script"]) == 2
    saved = tmp_path / body["audio_url"].split("/")[-1]
    assert saved.read_bytes() == b"mp3:Himp3:Hello"


def test_legacy_upload_endpoint(fake_audio_stack):
    files = {"file": ("notes.txt", b"Some text", "text/plain")}
    assert client.post("/upload", files=files).status_code == 200
