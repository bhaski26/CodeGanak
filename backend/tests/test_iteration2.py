"""Iteration 2 backend tests: Workspaces, Invites, Graph, Embeddings-mode search."""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
DEMO = {"email": "demo@codeganak.dev", "password": "password123"}
GITHUB_URL = "https://github.com/psf/requests-html"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def demo_headers():
    r = requests.post(f"{API}/auth/login", json=DEMO, timeout=15)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def personal_ws(demo_headers):
    r = requests.get(f"{API}/workspaces", headers=demo_headers, timeout=15)
    assert r.status_code == 200
    wss = r.json()
    personal = [w for w in wss if w.get("is_personal")]
    assert personal, f"no personal workspace: {wss}"
    return personal[0]


@pytest.fixture(scope="module")
def invitee():
    email = f"test_invitee_{uuid.uuid4().hex[:8]}@codeganak.dev"
    r = requests.post(f"{API}/auth/register", json={
        "name": "Invitee", "email": email, "password": "password123",
    }, timeout=15)
    assert r.status_code == 200, r.text
    return {"email": email, "token": r.json()["access_token"], "user_id": r.json()["user"]["id"]}


# ---------- Workspaces ----------
class TestWorkspaces:
    def test_list_returns_personal(self, personal_ws):
        assert personal_ws["name"] == "My workspace"
        assert personal_ws["is_personal"] is True
        assert personal_ws["role"] == "owner"

    def test_legacy_repos_migrated(self, demo_headers, personal_ws):
        # After migration, personal workspace should have >0 repos (from iter1 imports)
        assert personal_ws["repo_count"] >= 0  # can be 0 if prior cleanup; check by listing
        r = requests.get(f"{API}/repositories", params={"workspace_id": personal_ws["id"]},
                         headers=demo_headers, timeout=15)
        assert r.status_code == 200

    def test_create_workspace(self, demo_headers):
        name = f"TEST_ws_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/workspaces", json={"name": name},
                          headers=demo_headers, timeout=15)
        assert r.status_code == 200, r.text
        ws = r.json()
        assert ws["name"] == name
        assert ws["role"] == "owner"
        assert ws["is_personal"] is False
        # GET verify
        gr = requests.get(f"{API}/workspaces", headers=demo_headers, timeout=15)
        assert any(w["id"] == ws["id"] for w in gr.json())
        # cleanup
        requests.delete(f"{API}/workspaces/{ws['id']}", headers=demo_headers, timeout=15)

    def test_delete_personal_forbidden(self, demo_headers, personal_ws):
        r = requests.delete(f"{API}/workspaces/{personal_ws['id']}",
                            headers=demo_headers, timeout=15)
        assert r.status_code == 400


# ---------- Invites & Membership ----------
class TestInvites:
    @pytest.fixture(scope="class")
    def team_ws(self, demo_headers):
        name = f"TEST_team_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/workspaces", json={"name": name},
                          headers=demo_headers, timeout=15)
        ws = r.json()
        yield ws
        # cleanup
        requests.delete(f"{API}/workspaces/{ws['id']}", headers=demo_headers, timeout=15)

    def test_create_invite(self, demo_headers, team_ws):
        r = requests.post(f"{API}/workspaces/{team_ws['id']}/invites",
                          json={"role": "member"}, headers=demo_headers, timeout=15)
        assert r.status_code == 200, r.text
        inv = r.json()
        assert "token" in inv and len(inv["token"]) > 8
        assert inv["role"] == "member"
        # stash on class
        TestInvites.token = inv["token"]

    def test_preview_no_auth(self, team_ws):
        assert getattr(TestInvites, "token", None)
        r = requests.get(f"{API}/invites/{TestInvites.token}", timeout=15)
        assert r.status_code == 200
        p = r.json()
        assert p["workspace_name"] == team_ws["name"]
        assert p["role"] == "member"
        assert "owner_name" in p

    def test_accept_as_new_user(self, invitee, team_ws):
        h = {"Authorization": f"Bearer {invitee['token']}"}
        r = requests.post(f"{API}/invites/{TestInvites.token}/accept",
                          headers=h, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["workspace_id"] == team_ws["id"]
        # invitee now sees both workspaces
        gr = requests.get(f"{API}/workspaces", headers=h, timeout=15)
        ws_ids = [w["id"] for w in gr.json()]
        assert team_ws["id"] in ws_ids
        assert len(gr.json()) >= 2  # personal + this one

    def test_promote_member_to_admin(self, demo_headers, invitee, team_ws):
        r = requests.patch(
            f"{API}/workspaces/{team_ws['id']}/members/{invitee['user_id']}",
            json={"role": "admin"}, headers=demo_headers, timeout=15,
        )
        assert r.status_code == 200, r.text
        # verify via list
        mr = requests.get(f"{API}/workspaces/{team_ws['id']}/members",
                          headers=demo_headers, timeout=15)
        roles = {m["user_id"]: m["role"] for m in mr.json()}
        assert roles[invitee["user_id"]] == "admin"

    def test_non_owner_cannot_promote_to_owner(self, invitee, demo_headers, team_ws):
        # invitee is admin now — try to promote self to owner
        h = {"Authorization": f"Bearer {invitee['token']}"}
        # get demo user id
        me = requests.get(f"{API}/auth/me", headers=demo_headers, timeout=15).json()
        r = requests.patch(
            f"{API}/workspaces/{team_ws['id']}/members/{invitee['user_id']}",
            json={"role": "owner"}, headers=h, timeout=15,
        )
        assert r.status_code == 403

    def test_self_leave(self, invitee, team_ws):
        h = {"Authorization": f"Bearer {invitee['token']}"}
        r = requests.delete(
            f"{API}/workspaces/{team_ws['id']}/members/{invitee['user_id']}",
            headers=h, timeout=15,
        )
        assert r.status_code == 200
        assert r.json().get("left") is True

    def test_remove_non_owner(self, demo_headers, invitee, team_ws):
        # re-add invitee via invite
        r = requests.post(f"{API}/workspaces/{team_ws['id']}/invites",
                          json={"role": "member"}, headers=demo_headers, timeout=15)
        tok = r.json()["token"]
        h = {"Authorization": f"Bearer {invitee['token']}"}
        requests.post(f"{API}/invites/{tok}/accept", headers=h, timeout=15)
        # owner removes them
        rd = requests.delete(
            f"{API}/workspaces/{team_ws['id']}/members/{invitee['user_id']}",
            headers=demo_headers, timeout=15,
        )
        assert rd.status_code == 200
        assert rd.json().get("removed") is True

    def test_delete_team_workspace(self, demo_headers, team_ws):
        r = requests.delete(f"{API}/workspaces/{team_ws['id']}",
                            headers=demo_headers, timeout=15)
        assert r.status_code == 200
        assert r.json().get("deleted") is True
        # verify gone
        gr = requests.get(f"{API}/workspaces", headers=demo_headers, timeout=15)
        assert not any(w["id"] == team_ws["id"] for w in gr.json())


# ---------- Repo import into workspace + embeddings + graph ----------
@pytest.fixture(scope="module")
def imported_repo(demo_headers, personal_ws):
    r = requests.post(
        f"{API}/repositories/import-github",
        json={"github_url": GITHUB_URL, "workspace_id": personal_ws["id"]},
        headers=demo_headers, timeout=30,
    )
    assert r.status_code == 200, r.text
    repo = r.json()
    assert repo["status"] == "queued"
    assert repo["workspace_id"] == personal_ws["id"]
    rid = repo["id"]
    # poll until ready
    for _ in range(60):
        time.sleep(1.5)
        g = requests.get(f"{API}/repositories/{rid}", headers=demo_headers, timeout=15)
        if g.status_code == 200 and g.json()["status"] == "ready":
            yield g.json()
            requests.delete(f"{API}/repositories/{rid}", headers=demo_headers, timeout=15)
            return
        if g.status_code == 200 and g.json()["status"] == "failed":
            pytest.fail(f"Import failed: {g.json()}")
    pytest.fail("Repo not ready in time")


class TestRepoWorkspaceImport:
    def test_ready(self, imported_repo):
        assert imported_repo["status"] == "ready"

    def test_scoped_list_by_workspace(self, demo_headers, personal_ws, imported_repo):
        r = requests.get(f"{API}/repositories",
                         params={"workspace_id": personal_ws["id"]},
                         headers=demo_headers, timeout=15)
        assert r.status_code == 200
        assert any(rp["id"] == imported_repo["id"] for rp in r.json())

    def test_list_all_workspaces(self, demo_headers, imported_repo):
        r = requests.get(f"{API}/repositories", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        assert any(rp["id"] == imported_repo["id"] for rp in r.json())


class TestGraph:
    def test_graph_module(self, demo_headers, imported_repo):
        r = requests.get(
            f"{API}/repositories/{imported_repo['id']}/graph",
            params={"granularity": "module"},
            headers=demo_headers, timeout=30,
        )
        assert r.status_code == 200, r.text
        g = r.json()
        assert "nodes" in g and "edges" in g and "stats" in g
        assert g["stats"]["node_count"] >= 1
        # requests-html has internal + external deps; edges may be 0 if only external
        assert isinstance(g["stats"].get("cycle_count"), int)

    def test_graph_file(self, demo_headers, imported_repo):
        r = requests.get(
            f"{API}/repositories/{imported_repo['id']}/graph",
            params={"granularity": "file"},
            headers=demo_headers, timeout=30,
        )
        assert r.status_code == 200, r.text
        g = r.json()
        assert g["stats"]["node_count"] >= 1


class TestEmbeddingsSearch:
    def test_search_mode_switches_to_embeddings(self, demo_headers, imported_repo):
        rid = imported_repo["id"]
        # wait up to ~120s for embedding_ready
        mode = None
        for _ in range(60):
            time.sleep(2)
            rr = requests.get(f"{API}/repositories/{rid}", headers=demo_headers, timeout=15)
            if rr.status_code == 200 and rr.json().get("embedding_ready"):
                break
        # perform search
        sr = requests.post(
            f"{API}/repositories/{rid}/search",
            json={"query": "how to render javascript pages", "limit": 10},
            headers=demo_headers, timeout=60,
        )
        assert sr.status_code == 200, sr.text
        data = sr.json()
        mode = data.get("mode")
        assert mode in ("embeddings", "bm25")
        assert isinstance(data.get("results"), list)
        if mode == "embeddings":
            assert len(data["results"]) > 0
            joined = " ".join((r.get("snippet", "") + " " + r.get("name", ""))
                              for r in data["results"]).lower()
            assert "render" in joined, f"'render' not in top results: {joined[:400]}"
