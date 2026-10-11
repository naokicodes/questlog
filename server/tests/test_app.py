import io


def test_pages_need_login(cfg, conn):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(cfg)) as client:
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login"
        assert client.get("/api/gate").status_code == 401
        assert client.get("/login").status_code == 200
        assert client.get("/static/app.css").status_code == 200


def test_today_and_gate_api(make_client):
    client = make_client("laptop")
    r = client.get("/")
    assert r.status_code == 200
    assert "Quests" in r.text
    g = client.get("/api/gate").json()
    assert g["state"] in ("LOCKED", "OPEN")
    assert "emergencies_left" in g


def test_phone_manual_quest_needs_proof(make_client):
    client = make_client("phone")
    today = client.get("/api/today").json()
    manual = next(q for q in today["quests"] if q["verify"] == "manual")
    r = client.post(f"/quests/{manual['id']}/done", follow_redirects=False)
    assert "error=" in r.headers["location"]
    files = {"proof": ("take.m4a", io.BytesIO(b"fake audio"), "audio/mp4")}
    r = client.post(f"/quests/{manual['id']}/done", files=files, follow_redirects=False)
    assert "notice=" in r.headers["location"]
    done = {q["id"]: q["status"] for q in client.get("/api/today").json()["quests"]}
    assert done[manual["id"]] == "done"


def test_journal_create_search_and_photo(make_client):
    client = make_client("laptop")
    files = [("files", ("page.jpg", io.BytesIO(b"\xff\xd8fakejpeg"), "image/jpeg"))]
    data = {
        "day": "2026-10-12",
        "title": "Evening review",
        "body_md": "Grateful for coffee",
        "tags": "review",
    }
    r = client.post("/journal", data=data, files=files, follow_redirects=False)
    assert r.status_code == 303
    entry_url = r.headers["location"].split("?")[0]
    page = client.get(entry_url)
    assert "Grateful for coffee" in page.text and "/media/" in page.text
    img = page.text.split('src="/media/')[1].split('"')[0]
    assert client.get(f"/media/{img}").status_code == 200
    assert "Evening review" in client.get("/journal", params={"q": "coffee"}).text


def test_sessions_and_templates(make_client):
    client = make_client("laptop")
    skills_page = client.get("/")
    assert "Start session" in skills_page.text
    r = client.post(
        "/sessions/start",
        data={"skill_id": "1", "begin_action": "open notes"},
        follow_redirects=False,
    )
    assert "notice=" in r.headers["location"]
    assert "End session" in client.get("/").text
    r = client.post(
        "/quests/templates",
        data={
            "title": "AutoCAD plates",
            "verify": "auto",
            "apps": "acad.exe",
            "min_minutes": "60",
            "required": "on",
            "weekdays": ["1", "2", "3"],
        },
        follow_redirects=False,
    )
    assert "notice=" in r.headers["location"]
    assert "acad.exe" in client.get("/quests").text


def test_phone_usage_upload(make_client):
    client = make_client("phone")
    r = client.post(
        "/api/phone/usage",
        json={
            "items": [{"package": "com.zhiliaoapp.musically", "label": "TikTok", "seconds": 1800}]
        },
    )
    assert r.json()["saved"] == 1
