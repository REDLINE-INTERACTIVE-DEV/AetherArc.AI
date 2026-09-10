import os
os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("AETHER_MODEL_BASE_URL", None)
os.environ.pop("OLLAMA_URL", None)
os.environ.pop("POLLINATIONS_API_KEY", None)
os.environ.pop("COMPOSIO_API_KEY", None)
os.environ.pop("COMPOSIO_USER_ID", None)
from fastapi.testclient import TestClient
import app
from starlette.requests import Request

client = TestClient(app.app)

def test_api_contracts():
    assert client.get("/api/health").status_code == 200
    cfg = client.get("/api/config").json()
    assert cfg["agents"] == app.AGENTS
    assert cfg["model_connected"] is False
    assert cfg["image_generation"] is False
    assert cfg["composio_connected"] is False

def test_auth_history_contract():
    r = client.post("/api/auth/register", json={"email":"prelaunch@example.invalid","password":"safe-test-password"})
    assert r.status_code in (200, 400)
    token = client.post("/api/auth/guest", json={}).json()["token"]
    h = client.get("/api/history", headers={"Authorization":"Bearer "+token})
    assert h.status_code == 200 and h.json()["saved"] is False

def test_image_backend_contract(monkeypatch):
    monkeypatch.setenv("POLLINATIONS_API_KEY", "test-key")
    monkeypatch.setattr(app, "image_generate", lambda prompt, model=None: "data:image/png;base64,TEST")
    r = client.post("/api/image", json={"message":"generate a test image","agent":"manager"})
    assert r.status_code == 200 and r.json()["image_data"].startswith("data:image/")

def test_research_backend_contract(monkeypatch):
    monkeypatch.setattr(app, "research", lambda q, location=None: [{"title":"Test Source","url":"https://example.com","snippet":"evidence"}])
    monkeypatch.setattr(app, "model_available", lambda: True)
    monkeypatch.setattr(app, "call_model", lambda messages, temperature=0.2: "research synthesis")
    r = client.post("/api/chat", json={"message":"research current Aether news","agent":"research"})
    assert r.status_code == 200 and r.json()["answer"] == "research synthesis"
    assert r.json()["sources"][0]["url"] == "https://example.com"

def test_github_backend_contract(monkeypatch):
    monkeypatch.setenv("COMPOSIO_API_KEY", "test")
    monkeypatch.setenv("COMPOSIO_USER_ID", "test-user")
    calls=[]
    def fake(slug, arguments):
        calls.append((slug, arguments))
        if slug == "GITHUB_GET_REPOSITORY_CONTENT":
            import base64
            return {"content":{"content":base64.b64encode(b"print(1)\n").decode()}}
        return {"ok":True}
    monkeypatch.setattr(app, "composio_call", fake)
    monkeypatch.setattr(app, "call_model", lambda messages, temperature=0.1: "print(2)\n")
    answer, result = app.github_fix("fix https://github.com/REDLINE-INTERACTIVE-DEV/AetherArc.AI/blob/main/test.py")
    assert "updated" in answer
    assert calls[0][0] == "GITHUB_GET_REPOSITORY_CONTENT" and calls[1][0] == "GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS"

def test_manager_teamwork_contract(monkeypatch):
    monkeypatch.setattr(app, "model_available", lambda: True)
    def fake_report(agent, user_text, location=None):
        return (agent + " report", [])
    monkeypatch.setattr(app, "specialist_report", fake_report)
    monkeypatch.setattr(app, "call_model", lambda messages, temperature=0.2: "manager final")
    r, reports, sources = app.manager_team("fix my website and research the latest ideas")
    assert r == "manager final"
    assert set(reports) == {"reason", "code", "research"}


def test_github_url_parser(monkeypatch):
    monkeypatch.delenv('AETHER_GITHUB_PATH', raising=False)
    owner, repo, path, branch = app.github_target('edit https://github.com/REDLINE-INTERACTIVE-DEV/AetherArc.AI/blob/main/mobile/app/build.gradle')
    assert (owner, repo, path, branch) == ('REDLINE-INTERACTIVE-DEV', 'AetherArc.AI', 'mobile/app/build.gradle', 'main')


def test_persistent_guest_session(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'DB', tmp_path / 'aether.db')
    app.init_db()
    token = app.token_for(None, True)
    req = Request({'type':'http','headers':[(b'authorization',('Bearer '+token).encode())]})
    assert app.current_user(req)['guest'] is True
    app.SESSIONS.clear()
    assert app.current_user(req)['guest'] is True


def test_oauth_provider_contract(monkeypatch):
    monkeypatch.setenv('GOOGLE_CLIENT_ID','id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET','secret')
    monkeypatch.delenv('GITHUB_CLIENT_ID', raising=False)
    monkeypatch.delenv('GITHUB_CLIENT_SECRET', raising=False)
    assert app.providers() == {'google': True, 'github': False}
