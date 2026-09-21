"""CodeGanak backend API — auth, workspaces, repo import/index, chat, search, graphs."""
from __future__ import annotations
from fastapi.openapi.docs import get_redoc_html

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import (
    FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Form, status,
)
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware

from db import db, client
from auth import (
    hash_password, verify_password, create_access_token, get_current_user,
)
from models import (
    RegisterInput, LoginInput, TokenResponse, UserPublic, User,
    Repository, RepositoryPublic, GithubImportInput,
    ChatInput, ChatMessage, SearchInput,
    WorkspaceCreateInput, WorkspaceRenameInput, InviteCreateInput, RoleUpdateInput,
    WorkspacePublic,
)
from repo_service import (
    import_zip, import_github, build_file_tree, get_file_content,
)
from ai_service import chat_stream, semantic_search, generate_documentation
from graph_service import build_graph
from workspace_service import (
    ensure_personal_workspace, list_workspaces_for_user, get_membership,
    require_membership, create_workspace, rename_workspace, delete_workspace,
    list_members, update_member_role, remove_member,
    create_invite, list_invites, revoke_invite, accept_invite, preview_invite,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("codeganak")

app = FastAPI(
    title="CodeGanak API",
    version="0.2.0",
    redoc_url=None,
)
api = APIRouter(prefix="/api")

# ------------------ Redoc -----------------

@app.get("/redoc", include_in_schema=False)
async def custom_redoc():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js",
    )

# ------------------ Health ------------------

@api.get("/")
async def root():
    return {"service": "codeganak", "status": "ok"}


@api.get("/health")
async def health():
    try:
        await db.command("ping")
        return {"status": "ok", "mongo": "up"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"mongo down: {e}")


# ------------------ Auth ------------------

@api.post("/auth/register", response_model=TokenResponse)
async def register(payload: RegisterInput):
    existing = await db.users.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email.lower(),
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
    )
    await db.users.insert_one(user.model_dump())
    await ensure_personal_workspace(user.id)
    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserPublic(id=user.id, email=user.email, name=user.name, created_at=user.created_at),
    )


@api.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginInput):
    doc = await db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if not doc or not verify_password(payload.password, doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = User(**doc)
    await ensure_personal_workspace(user.id)
    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserPublic(id=user.id, email=user.email, name=user.name, created_at=user.created_at),
    )


@api.get("/auth/me", response_model=UserPublic)
async def me(user: UserPublic = Depends(get_current_user)):
    await ensure_personal_workspace(user.id)
    return user


# ------------------ Workspaces ------------------

@api.get("/workspaces", response_model=list[WorkspacePublic])
async def get_workspaces(user: UserPublic = Depends(get_current_user)):
    return await list_workspaces_for_user(user.id)


@api.post("/workspaces", response_model=WorkspacePublic)
async def new_workspace(payload: WorkspaceCreateInput, user: UserPublic = Depends(get_current_user)):
    return await create_workspace(user.id, payload.name.strip())


@api.patch("/workspaces/{workspace_id}")
async def patch_workspace(
    workspace_id: str, payload: WorkspaceRenameInput,
    user: UserPublic = Depends(get_current_user),
):
    await rename_workspace(workspace_id, user.id, payload.name.strip())
    return {"ok": True}


@api.delete("/workspaces/{workspace_id}")
async def del_workspace(workspace_id: str, user: UserPublic = Depends(get_current_user)):
    await delete_workspace(workspace_id, user.id)
    return {"deleted": True}


@api.get("/workspaces/{workspace_id}/members")
async def workspace_members(workspace_id: str, user: UserPublic = Depends(get_current_user)):
    return await list_members(workspace_id, user.id)


@api.patch("/workspaces/{workspace_id}/members/{target_user_id}")
async def change_role(
    workspace_id: str, target_user_id: str, payload: RoleUpdateInput,
    user: UserPublic = Depends(get_current_user),
):
    await update_member_role(workspace_id, user.id, target_user_id, payload.role)
    return {"ok": True}


@api.delete("/workspaces/{workspace_id}/members/{target_user_id}")
async def kick(workspace_id: str, target_user_id: str, user: UserPublic = Depends(get_current_user)):
    if target_user_id == user.id:
        # allow self-leave
        m = await get_membership(workspace_id, user.id)
        if not m:
            raise HTTPException(status_code=404, detail="Not a member")
        ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
        if ws and ws["owner_id"] == user.id:
            raise HTTPException(status_code=400, detail="Owner cannot leave — transfer ownership first")
        await db.memberships.delete_one({"workspace_id": workspace_id, "user_id": user.id})
        return {"left": True}
    await remove_member(workspace_id, user.id, target_user_id)
    return {"removed": True}


@api.get("/workspaces/{workspace_id}/invites")
async def get_invites(workspace_id: str, user: UserPublic = Depends(get_current_user)):
    invs = await list_invites(workspace_id, user.id)
    return [i.model_dump() for i in invs]


@api.post("/workspaces/{workspace_id}/invites")
async def new_invite(
    workspace_id: str, payload: InviteCreateInput,
    user: UserPublic = Depends(get_current_user),
):
    inv = await create_invite(workspace_id, user.id, payload.role)
    return inv.model_dump()


@api.delete("/workspaces/{workspace_id}/invites/{invite_id}")
async def del_invite(
    workspace_id: str, invite_id: str,
    user: UserPublic = Depends(get_current_user),
):
    await revoke_invite(workspace_id, user.id, invite_id)
    return {"revoked": True}


@api.get("/invites/{token}")
async def preview(token: str):
    return await preview_invite(token)


@api.post("/invites/{token}/accept")
async def accept(token: str, user: UserPublic = Depends(get_current_user)):
    ws, role = await accept_invite(token, user.id)
    return {"workspace_id": ws.id, "workspace_name": ws.name, "role": role}


# ------------------ Repositories ------------------

async def _repo_or_404(repo_id: str, user_id: str, min_role: str = "member") -> dict:
    doc = await db.repositories.find_one({"id": repo_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Repository not found")
    workspace_id = doc.get("workspace_id")
    if not workspace_id:
        # legacy repo without workspace: auto-migrate to personal
        ws = await ensure_personal_workspace(doc["user_id"])
        workspace_id = ws.id
        await db.repositories.update_one({"id": repo_id}, {"$set": {"workspace_id": workspace_id}})
        doc["workspace_id"] = workspace_id
    await require_membership(workspace_id, user_id, min_role=min_role)  # type: ignore
    return doc


@api.get("/repositories", response_model=list[RepositoryPublic])
async def list_repositories(
    workspace_id: Optional[str] = None,
    user: UserPublic = Depends(get_current_user),
):
    await ensure_personal_workspace(user.id)
    if workspace_id:
        await require_membership(workspace_id, user.id, min_role="member")
        cursor = db.repositories.find({"workspace_id": workspace_id}, {"_id": 0}).sort("created_at", -1)
    else:
        ws_ids = [m["workspace_id"] async for m in db.memberships.find({"user_id": user.id}, {"_id": 0})]
        cursor = db.repositories.find({"workspace_id": {"$in": ws_ids}}, {"_id": 0}).sort("created_at", -1)
    docs = await cursor.to_list(500)
    return [RepositoryPublic(**d) for d in docs]


async def _resolve_workspace_for_import(
    workspace_id: Optional[str], user_id: str, min_role: str = "admin",
) -> str:
    if workspace_id:
        await require_membership(workspace_id, user_id, min_role=min_role)  # type: ignore
        return workspace_id
    ws = await ensure_personal_workspace(user_id)
    return ws.id


@api.post("/repositories/upload", response_model=RepositoryPublic)
async def upload_zip_repo(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    workspace_id: Optional[str] = Form(None),
    user: UserPublic = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip uploads are supported")
    content = await file.read()
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="ZIP too large (max 200 MB)")

    ws_id = await _resolve_workspace_for_import(workspace_id, user.id)
    repo_name = name or Path(file.filename).stem
    repo = Repository(workspace_id=ws_id, user_id=user.id, name=repo_name, source="zip", status="queued")
    await db.repositories.insert_one(repo.model_dump())

    asyncio.create_task(import_zip(repo.id, content))
    return RepositoryPublic(**repo.model_dump())


@api.post("/repositories/import-github", response_model=RepositoryPublic)
async def import_github_repo(
    payload: GithubImportInput,
    user: UserPublic = Depends(get_current_user),
):
    url = payload.github_url.strip()
    if "github.com/" not in url:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")

    ws_id = await _resolve_workspace_for_import(payload.workspace_id, user.id)
    slug = url.rstrip("/").split("github.com/")[-1].removesuffix(".git")
    repo_name = slug.split("/")[-1] or "repo"

    repo = Repository(
        workspace_id=ws_id, user_id=user.id, name=repo_name, source="github",
        github_url=url, status="queued",
    )
    await db.repositories.insert_one(repo.model_dump())
    asyncio.create_task(import_github(repo.id, url))
    return RepositoryPublic(**repo.model_dump())


@api.get("/repositories/{repo_id}", response_model=RepositoryPublic)
async def get_repository(repo_id: str, user: UserPublic = Depends(get_current_user)):
    doc = await _repo_or_404(repo_id, user.id)
    return RepositoryPublic(**doc)


@api.delete("/repositories/{repo_id}")
async def delete_repository(repo_id: str, user: UserPublic = Depends(get_current_user)):
    doc = await _repo_or_404(repo_id, user.id, min_role="admin")
    await db.repositories.delete_one({"id": repo_id})
    await db.files.delete_many({"repo_id": repo_id})
    await db.symbols.delete_many({"repo_id": repo_id})
    await db.imports.delete_many({"repo_id": repo_id})
    await db.chat_messages.delete_many({"repo_id": repo_id})
    import shutil
    root = doc.get("root_path")
    if root and Path(root).exists():
        try:
            shutil.rmtree(root, ignore_errors=True)
        except Exception:
            pass
    return {"deleted": True}


@api.get("/repositories/{repo_id}/tree")
async def get_tree(repo_id: str, user: UserPublic = Depends(get_current_user)):
    await _repo_or_404(repo_id, user.id)
    docs = await db.files.find({"repo_id": repo_id}, {"_id": 0, "path": 1}).to_list(20000)
    return build_file_tree([d["path"] for d in docs])


@api.get("/repositories/{repo_id}/file")
async def get_file(repo_id: str, path: str, user: UserPublic = Depends(get_current_user)):
    repo = await _repo_or_404(repo_id, user.id)
    content = await get_file_content(repo, path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    meta = await db.files.find_one({"repo_id": repo_id, "path": path}, {"_id": 0})
    return {
        "path": path,
        "language": (meta or {}).get("language"),
        "line_count": (meta or {}).get("line_count", 0),
        "content": content,
    }


@api.get("/repositories/{repo_id}/stats")
async def get_stats(repo_id: str, user: UserPublic = Depends(get_current_user)):
    repo = await _repo_or_404(repo_id, user.id)
    files = await db.files.find({"repo_id": repo_id}, {"_id": 0, "path": 1, "language": 1}).to_list(20000)
    module_counts: dict = {}
    for f in files:
        top = f["path"].split("/")[0] if "/" in f["path"] else f["path"]
        module_counts[top] = module_counts.get(top, 0) + 1
    top_modules = sorted(module_counts.items(), key=lambda kv: kv[1], reverse=True)[:8]
    apis = await db.symbols.find({"repo_id": repo_id, "kind": "route"}, {"_id": 0}).limit(50).to_list(50)
    return {
        "repo": RepositoryPublic(**repo).model_dump(),
        "top_modules": [{"name": k, "count": v} for k, v in top_modules],
        "apis": apis,
    }


@api.get("/repositories/{repo_id}/graph")
async def get_graph(
    repo_id: str, granularity: str = "module",
    user: UserPublic = Depends(get_current_user),
):
    repo = await _repo_or_404(repo_id, user.id)
    if repo["status"] != "ready":
        raise HTTPException(status_code=400, detail=f"Repository not ready (status: {repo['status']})")
    if granularity not in ("module", "file"):
        raise HTTPException(status_code=400, detail="granularity must be 'module' or 'file'")
    return await build_graph(repo_id, db, granularity=granularity)


# ------------------ Search ------------------

@api.post("/repositories/{repo_id}/search")
async def search(
    repo_id: str, payload: SearchInput,
    user: UserPublic = Depends(get_current_user),
):
    repo = await _repo_or_404(repo_id, user.id)
    if repo["status"] != "ready":
        raise HTTPException(status_code=400, detail=f"Repository not ready (status: {repo['status']})")
    results = await semantic_search(repo_id, payload.query, db, top_k=payload.limit)
    return {
        "results": results, "count": len(results),
        "mode": "embeddings" if repo.get("embedding_ready") else "bm25",
    }


# ------------------ Chat ------------------

@api.get("/repositories/{repo_id}/chat/history")
async def get_chat_history(repo_id: str, user: UserPublic = Depends(get_current_user)):
    await _repo_or_404(repo_id, user.id)
    docs = await db.chat_messages.find(
        {"repo_id": repo_id, "user_id": user.id}, {"_id": 0},
    ).sort("created_at", 1).to_list(500)
    return docs


@api.post("/repositories/{repo_id}/chat")
async def repo_chat(
    repo_id: str, payload: ChatInput,
    user: UserPublic = Depends(get_current_user),
):
    repo = await _repo_or_404(repo_id, user.id)
    if repo["status"] != "ready":
        raise HTTPException(status_code=400, detail=f"Repository not ready (status: {repo['status']})")

    user_msg = ChatMessage(repo_id=repo_id, user_id=user.id, role="user", content=payload.message)
    await db.chat_messages.insert_one(user_msg.model_dump())

    history_docs = await db.chat_messages.find(
        {"repo_id": repo_id, "user_id": user.id}, {"_id": 0},
    ).sort("created_at", 1).to_list(50)
    history = [{"role": h["role"], "content": h["content"]} for h in history_docs[:-1]]

    async def event_gen():
        buf: list[str] = []
        citations: list = []
        try:
            async for ev in chat_stream(repo, payload.message, history, db):
                if ev["type"] == "citations":
                    citations = ev["data"]
                    yield f"event: citations\ndata: {json.dumps(citations)}\n\n"
                elif ev["type"] == "delta":
                    buf.append(ev["data"])
                    yield f"event: delta\ndata: {json.dumps(ev['data'])}\n\n"
                elif ev["type"] == "done":
                    break
        except Exception as e:
            log.exception("chat stream failed")
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"
        finally:
            answer = "".join(buf).strip()
            if answer:
                assistant_msg = ChatMessage(
                    repo_id=repo_id, user_id=user.id, role="assistant",
                    content=answer, citations=citations,
                )
                await db.chat_messages.insert_one(assistant_msg.model_dump())
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ------------------ Documentation ------------------

@api.post("/repositories/{repo_id}/docs")
async def gen_docs(repo_id: str, user: UserPublic = Depends(get_current_user)):
    repo = await _repo_or_404(repo_id, user.id)
    if repo["status"] != "ready":
        raise HTTPException(status_code=400, detail=f"Repository not ready (status: {repo['status']})")
    md = await generate_documentation(repo, db)
    await db.repositories.update_one({"id": repo_id}, {"$set": {"generated_docs": md}})
    return {"markdown": md}


# ------------------ App wiring ------------------

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.workspaces.create_index([("owner_id", 1)])
        await db.memberships.create_index([("workspace_id", 1), ("user_id", 1)], unique=True)
        await db.memberships.create_index([("user_id", 1)])
        await db.invites.create_index("token", unique=True)
        await db.repositories.create_index([("workspace_id", 1), ("created_at", -1)])
        await db.files.create_index([("repo_id", 1), ("path", 1)])
        await db.symbols.create_index([("repo_id", 1), ("kind", 1)])
        await db.imports.create_index([("repo_id", 1), ("source_path", 1)])
        await db.chat_messages.create_index([("repo_id", 1), ("created_at", 1)])
        log.info("mongo indexes ready")
    except Exception as e:
        log.warning("index creation failed: %s", e)


@app.on_event("shutdown")
async def _shutdown():
    client.close()
