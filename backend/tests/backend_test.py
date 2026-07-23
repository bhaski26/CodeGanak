"""End-to-end backend tests for CodeGanak API."""
import os
import time
import uuid
import json
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://repo-semantic-ai.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
GITHUB_URL = "https://github.com/tiangolo/uvicorn-gunicorn-fastapi-docker"
DEMO = {"email": "demo@codeganak.dev", "password": "password123"}


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def demo_token():
    r = requests.post(f"{API}/auth/login", json=DEMO, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def demo_headers(demo_token):
    return {"Authorization": f"Bearer {demo_token}"}


@pytest.fixture(scope="session")
def ready_repo(demo_headers):
    """Import the test repo and wait until ready. Reused across tests."""
    r = requests.post(
        f"{API}/repositories/import-github",
        json={"github_url": GITHUB_URL},
        headers=demo_headers,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    repo = r.json()
    assert repo["status"] == "queued"
    repo_id = repo["id"]

    # Poll until ready
    for _ in range(60):  # up to ~90s
        time.sleep(1.5)
        g = requests.get(f"{API}/repositories/{repo_id}", headers=demo_headers, timeout=15)
        assert g.status_code == 200
        st = g.json()["status"]
        if st == "ready":
            return g.json()
        if st == "failed":
            pytest.fail(f"Repo import failed: {g.json()}")
    pytest.fail("Repo not ready in time")


# ---------- Health ----------
def test_health():
    r = requests.get(f"{API}/health", timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------- Auth ----------
class TestAuth:
    def test_register_new_user(self):
        email = f"test_{uuid.uuid4().hex[:10]}@codeganak.dev"
        r = requests.post(f"{API}/auth/register", json={
            "name": "Test User", "email": email, "password": "password123",
        }, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "access_token" in data
        assert data["user"]["email"] == email
        assert data["user"]["name"] == "Test User"
        assert "id" in data["user"]

    def test_register_duplicate_email(self):
        r = requests.post(f"{API}/auth/register", json={
            "name": "Dup", "email": DEMO["email"], "password": "password123",
        }, timeout=15)
        assert r.status_code == 400

    def test_login_success(self):
        r = requests.post(f"{API}/auth/login", json=DEMO, timeout=15)
        assert r.status_code == 200
        assert r.json()["user"]["email"] == DEMO["email"]

    def test_login_invalid_password(self):
        r = requests.post(f"{API}/auth/login", json={
            "email": DEMO["email"], "password": "wrong-password"
        }, timeout=15)
        assert r.status_code == 401

    def test_me_with_token(self, demo_headers):
        r = requests.get(f"{API}/auth/me", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == DEMO["email"]

    def test_me_without_token(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code in (401, 403)


# ---------- Repositories ----------
class TestRepositories:
    def test_list_requires_auth(self):
        r = requests.get(f"{API}/repositories", timeout=15)
        assert r.status_code in (401, 403)

    def test_list_repos(self, demo_headers, ready_repo):
        r = requests.get(f"{API}/repositories", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        assert any(rp["id"] == ready_repo["id"] for rp in r.json())

    def test_repo_indexed(self, demo_headers, ready_repo):
        repo_id = ready_repo["id"]
        r = requests.get(f"{API}/repositories/{repo_id}", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ready"
        assert d["file_count"] > 0
        assert d["function_count"] >= 0
        assert isinstance(d.get("languages"), (list, dict))

    def test_tree(self, demo_headers, ready_repo):
        r = requests.get(f"{API}/repositories/{ready_repo['id']}/tree", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        tree = r.json()
        assert "children" in tree
        assert len(tree["children"]) > 0

    def test_file_content(self, demo_headers, ready_repo):
        # get a real file from tree
        tree = requests.get(f"{API}/repositories/{ready_repo['id']}/tree", headers=demo_headers, timeout=15).json()

        def find_file(node):
            if node.get("type") == "file":
                return node.get("path")
            for c in node.get("children", []) or []:
                p = find_file(c)
                if p:
                    return p
            return None

        path = find_file(tree)
        assert path, "no file found in tree"
        r = requests.get(
            f"{API}/repositories/{ready_repo['id']}/file",
            params={"path": path}, headers=demo_headers, timeout=15,
        )
        assert r.status_code == 200
        assert "content" in r.json()


# ---------- Search ----------
class TestSearch:
    def test_search_returns_results(self, demo_headers, ready_repo):
        r = requests.post(
            f"{API}/repositories/{ready_repo['id']}/search",
            json={"query": "gunicorn configuration", "limit": 10},
            headers=demo_headers, timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "results" in data
        assert len(data["results"]) > 0
        first = data["results"][0]
        assert "path" in first
        assert "snippet" in first
        assert "score" in first


# ---------- Chat (SSE) ----------
class TestChat:
    def test_chat_sse_stream(self, demo_headers, ready_repo):
        r = requests.post(
            f"{API}/repositories/{ready_repo['id']}/chat",
            json={"message": "In one sentence, what is this repo?"},
            headers=demo_headers, stream=True, timeout=90,
        )
        assert r.status_code == 200
        events = []
        deltas = []
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
            elif line.startswith("data:") and events and events[-1] == "delta":
                try:
                    deltas.append(json.loads(line[5:].strip()))
                except Exception:
                    pass
            if events and events[-1] == "done":
                break
        assert "done" in events, f"events seen: {events}"
        assert "delta" in events or "citations" in events

    def test_chat_history_persisted(self, demo_headers, ready_repo):
        r = requests.get(
            f"{API}/repositories/{ready_repo['id']}/chat/history",
            headers=demo_headers, timeout=15,
        )
        assert r.status_code == 200
        hist = r.json()
        assert len(hist) >= 2
        roles = [m["role"] for m in hist]
        assert "user" in roles and "assistant" in roles


# ---------- Docs & Delete (kept last; delete removes fixture repo) ----------
class TestZDocsAndDelete:
    def test_generate_docs(self, demo_headers, ready_repo):
        r = requests.post(
            f"{API}/repositories/{ready_repo['id']}/docs",
            headers=demo_headers, timeout=120,
        )
        assert r.status_code == 200, r.text
        md = r.json().get("markdown", "")
        assert isinstance(md, str) and len(md) > 20

    def test_delete_repo(self, demo_headers, ready_repo):
        rid = ready_repo["id"]
        r = requests.delete(f"{API}/repositories/{rid}", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        assert r.json().get("deleted") is True
        # verify gone
        g = requests.get(f"{API}/repositories/{rid}", headers=demo_headers, timeout=15)
        assert g.status_code == 404
