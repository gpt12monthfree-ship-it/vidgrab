"""
VidGrab Pro — automated test suite.

Run with:  python -m pytest tests/ -v
Focused on core behavior: pages, auth, API contracts, error handling.
Live-network tests (real YouTube) are included but tagged so they can be
skipped with:  python -m pytest tests/ -v -m "not live"
"""

import json
import time
import uuid

import pytest

import app as app_module

LIVE_URL = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"


@pytest.fixture
def client():
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture
def unique_user():
    """Return a fresh unique (username, email, password) for each test run."""
    tag = uuid.uuid4().hex[:8]
    return f"usr_{tag}", f"usr_{tag}@example.com", "secret123"


# ──────────────────────────── Pages ────────────────────────────

def test_homepage_redirects_anon(client):
    r = client.get("/")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_login_page(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert b"VidGrab" in r.data


def test_register_page(client):
    r = client.get("/register")
    assert r.status_code == 200


# ──────────────────────────── Auth API ────────────────────────────

def test_register_validation(client):
    r = client.post("/register", json={"username": "ab", "email": "x@y.com", "password": "secret123"})
    assert r.status_code == 400
    assert r.get_json()["ok"] is False

    r = client.post("/register", json={"username": "valuser", "email": "notanemail", "password": "secret123"})
    assert r.status_code == 400

    r = client.post("/register", json={"username": "valuser2", "email": "v2@example.com", "password": "abc"})
    assert r.status_code == 400


def test_register_login_flow(client, unique_user):
    u, e, p = unique_user
    r = client.post("/register", json={"username": u, "email": e, "password": p})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    r = client.post("/login", json={"username": u, "password": "wrong"})
    assert r.status_code == 401

    r = client.post("/login", json={"username": u, "password": p})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_history_requires_login(client):
    r = client.get("/history")
    assert r.status_code == 302


# ──────────────────────────── Inspect API contract ────────────────────────────

def test_inspect_rejects_bad_url(client):
    r = client.post("/api/inspect", json={"url": "not-a-url"})
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_inspect_rejects_missing_url(client):
    r = client.post("/api/inspect", json={})
    assert r.status_code == 400


def test_inspect_error_is_json_not_html(client):
    """Frontend expects JSON; a backend failure must not leak an HTML page."""
    r = client.post("/api/inspect", json={"url": "https://example.com/definitely-not-a-video"})
    assert r.status_code in (400, 502)
    assert r.is_json
    assert "error" in r.get_json()


def test_status_unknown_job(client):
    r = client.get("/api/status/doesnotexist")
    assert r.status_code == 200
    assert r.get_json()["state"] == "unknown"


def test_file_unknown_job_404_json(client):
    r = client.get("/api/file/doesnotexist")
    assert r.status_code == 404
    assert r.is_json


# ──────────────────────────── Live YouTube tests ────────────────────────────

@pytest.mark.live
def test_inspect_real_youtube(client):
    r = client.post("/api/inspect", json={"url": LIVE_URL})
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["title"]
    assert d["platform"] == "Youtube"
    assert len(d["formats"]) >= 1
    f = d["formats"][0]
    assert "id" in f and "label" in f and "ext" in f
    assert not any("\x1b" in str(k) for k in d.values()), "ANSI leak into JSON"


@pytest.mark.live
@pytest.mark.slow
def test_download_real_youtube_video(client):
    r = client.post("/api/download", json={
        "url": LIVE_URL, "type": "video", "format_id": "242",
        "title": "pytest", "platform": "Youtube", "quality": "240p",
    })
    assert r.status_code == 200
    job = r.get_json()["job"]

    for _ in range(120):
        s = client.get(f"/api/status/{job}").get_json()
        if s["state"] in ("done", "error"):
            break
        time.sleep(2)
    assert s["state"] == "done", s

    # Fetch the file
    fr = client.get(f"/api/file/{job}")
    assert fr.status_code == 200
    data = fr.data
    assert len(data) > 100_000
    assert data[:4] == b"\x00\x00\x00\x18" or b"ftyp" in data[:64], "not a valid mp4 header"