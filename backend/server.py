"""CodeGanak backend API — auth, repo import, indexing, chat, search."""
from __future__ import annotations

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
)
from repo_service import (
    import_zip, import_github, build_file_tree, get_file_content,
)
from ai_service import chat_stream, semantic_search, generate_documentation

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("codeganak")

app = FastAPI(title="CodeGanak API", version="0.1.0")
api = APIRouter(prefix="/api")


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
    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=UserPublic(id=user.id, email=user.email, name=user.name, created_at=user.created_at),
    )


@api.get("/auth/me", response_model=UserPublic)
async def me(user: UserPublic = Depends(get_current_user)):
    return user


# ------------------ Repositories ------------------

async def _repo_or_404(repo_id: str, user_id: str) -> dict:
    doc = await db.repositories.find_one({"id": repo_id, "user_id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Repository not found")
    return doc


@api.get("/repositories", response_model=list[RepositoryPublic])
async def list_repositories(user: UserPublic = Depends(get_current_user)):
    docs = await db.repositories.find({"user_id": user.id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [RepositoryPublic(**d) for d in docs]


@api.post("/repositories/upload", response_model=RepositoryPublic)
async def upload_zip_repo(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    user: UserPublic = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip uploads are supported")
    content = await file.read()
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="ZIP too large (max 200 MB)")

    repo_name = name or Path(file.filename).stem
    repo = Repository(user_id=user.id, name=repo_name, source="zip", status="queued")
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

    slug = url.rstrip("/").split("github.com/")[-1].removesuffix(".git")
    repo_name = slug.split("/")[-1] or "repo"

    repo = Repository(
        user_id=user.id, name=repo_name, source="github",
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
    doc = await _repo_or_404(repo_id, user.id)
    await db.repositories.delete_one({"id": repo_id})
    await db.files.delete_many({"repo_id": repo_id})
    await db.symbols.delete_many({"repo_id": repo_id})
    await db.chat_messages.delete_many({"repo_id": repo_id})
    # Best effort: remove on-disk storage
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
    paths = [d["path"] for d in docs]
    return build_file_tree(paths)


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
    # Top-level module distribution — first path segment counts
    files = await db.files.find({"repo_id": repo_id}, {"_id": 0, "path": 1, "language": 1}).to_list(20000)
    module_counts: dict = {}
    for f in files:
        top = f["path"].split("/")[0] if "/" in f["path"] else f["path"]
        module_counts[top] = module_counts.get(top, 0) + 1
    top_modules = sorted(module_counts.items(), key=lambda kv: kv[1], reverse=True)[:8]

    # sample APIs
    apis = await db.symbols.find(
        {"repo_id": repo_id, "kind": "route"}, {"_id": 0}
    ).limit(50).to_list(50)

    return {
        "repo": RepositoryPublic(**repo).model_dump(),
        "top_modules": [{"name": k, "count": v} for k, v in top_modules],
        "apis": apis,
    }


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
    return {"results": results, "count": len(results)}


# ------------------ Chat ------------------

@api.get("/repositories/{repo_id}/chat/history")
async def get_chat_history(
    repo_id: str, user: UserPublic = Depends(get_current_user),
):
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
    await db.repositories.update_one(
        {"id": repo_id}, {"$set": {"generated_docs": md}},
    )
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
    # Helpful indexes; ignore duplicate errors on hot reload.
    try:
        await db.users.create_index("email", unique=True)
        await db.repositories.create_index([("user_id", 1), ("created_at", -1)])
        await db.files.create_index([("repo_id", 1), ("path", 1)])
        await db.symbols.create_index([("repo_id", 1), ("kind", 1)])
        await db.chat_messages.create_index([("repo_id", 1), ("created_at", 1)])
        log.info("mongo indexes ready")
    except Exception as e:
        log.warning("index creation failed: %s", e)


@app.on_event("shutdown")
async def _shutdown():
    client.close()
