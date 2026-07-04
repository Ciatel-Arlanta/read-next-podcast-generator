import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main


def test_health_check():
    client = TestClient(main.app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("https://example.com/story", "url"),
        ("http://example.com", "url"),
        ("Just some article text", "text"),
        ("ftp://example.com/file", "text"),
    ],
)
def test_detect_input_type(source, expected):
    assert main._detect_input_type(source) == expected


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "https://user:pass@example.com/article",
    ],
)
def test_validate_public_url_rejects_unsafe_targets(url):
    with pytest.raises(HTTPException):
        main._validate_public_url(url)


def test_validate_public_url_accepts_public_target(monkeypatch):
    monkeypatch.setattr(main.socket, "getaddrinfo", lambda *args: [(None, None, None, None, ("93.184.216.34", 0))])

    assert main._validate_public_url("https://example.com/article") == "https://example.com/article"


def test_fetch_public_url_rejects_redirect_to_private_host(monkeypatch):
    class RedirectResponse:
        is_redirect = True
        headers = {"Location": "http://127.0.0.1/admin"}
        text = ""

        def raise_for_status(self):
            return None

    monkeypatch.setattr(main.socket, "getaddrinfo", lambda *args: [(None, None, None, None, ("93.184.216.34", 0))])
    monkeypatch.setattr(main.requests, "get", lambda *args, **kwargs: RedirectResponse())

    with pytest.raises(HTTPException):
        main._fetch_public_url("https://example.com/article", headers={})


def test_serve_audio_rejects_invalid_session_id():
    client = TestClient(main.app)

    response = client.get("/api/audio/not-a-session/podcast.mp3")

    assert response.status_code == 404


def test_serve_audio_rejects_wrong_filename():
    client = TestClient(main.app)

    response = client.get("/api/audio/abcdef123456/other.mp3")

    assert response.status_code == 404


def test_serve_audio_rejects_traversal_filename():
    client = TestClient(main.app)

    response = client.get("/api/audio/abcdef123456/%2e%2e")

    assert response.status_code == 404


def test_serve_audio_rejects_missing_valid_file(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "AUDIO_CACHE_DIR", tmp_path)
    client = TestClient(main.app)

    response = client.get("/api/audio/abcdef123456/podcast.mp3")

    assert response.status_code == 404


def test_serve_audio_serves_valid_file(tmp_path, monkeypatch):
    session_dir = tmp_path / "abcdef123456"
    session_dir.mkdir()
    audio_file = session_dir / "podcast.mp3"
    audio_file.write_bytes(b"fake mp3")
    monkeypatch.setattr(main, "AUDIO_CACHE_DIR", tmp_path)
    client = TestClient(main.app)

    response = client.get("/api/audio/abcdef123456/podcast.mp3")

    assert response.status_code == 200
    assert response.content == b"fake mp3"
