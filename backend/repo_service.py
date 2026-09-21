"""Repository import + indexing pipeline (ZIP or GitHub)."""
from __future__ import annotations

import asyncio
import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from db import db
from models import Repository, RepoFile, CodeSymbol, now_iso
from parser import (
    walk_repository, read_text, detect_language, detect_framework,
    extract_symbols, extract_imports, resolve_import,
)
from ai_service import embed_texts, EMBEDDING_DIM

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_GITHUB_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/#?\s]+)")


async def _update_repo(repo_id: str, **fields) -> None:
    fields["updated_at"] = now_iso()
    await db.repositories.update_one({"id": repo_id}, {"$set": fields})


def _repo_dir(repo_id: str) -> Path:
    return UPLOAD_DIR / repo_id


async def extract_zip_upload(repo_id: str, upload_bytes: bytes) -> Path:
    """Extract a ZIP archive into the repo's storage directory.

    If the archive contains exactly one top-level folder, we use that folder
    directly as the repo root so users don't see a redundant nesting.
    """
    dest = _repo_dir(repo_id)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    with zipfile.ZipFile(io.BytesIO(upload_bytes)) as zf:
        zf.extractall(dest)

    # collapse single-root wrapper
    entries = [p for p in dest.iterdir() if not p.name.startswith("__MACOSX")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return dest


async def clone_github_repo(repo_id: str, github_url: str) -> Path:
    """Clone a public GitHub repo using shallow depth."""
    m = _GITHUB_RE.match(github_url.strip())
    if not m:
        raise ValueError("Invalid GitHub URL. Expected https://github.com/<owner>/<repo>")

    owner, name = m.group(1), m.group(2)
    if name.endswith(".git"):
        name = name[:-4]
    clean_url = f"https://github.com/{owner}/{name}.git"

    dest = _repo_dir(repo_id)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    def _clone():
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        return subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", clean_url, str(dest)],
            capture_output=True, text=True, timeout=180, env=env,
        )

    result = await asyncio.get_event_loop().run_in_executor(None, _clone)
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed: {result.stderr.strip()[:400]}")
    return dest


async def index_repository(repo_id: str, root: Path) -> None:
    """Walk repo, extract files, symbols and imports, then embed symbols."""
    await _update_repo(repo_id, status="parsing")

    # clean any previous index
    await db.files.delete_many({"repo_id": repo_id})
    await db.symbols.delete_many({"repo_id": repo_id})
    await db.imports.delete_many({"repo_id": repo_id})

    files_batch: list = []
    symbols_batch: list = []
    lang_counts: dict = {}
    total_bytes = 0
    file_count = 0
    function_count = 0
    class_count = 0
    api_count = 0

    # Two-pass to allow resolve_import to see the full path set.
    parsed_files: list = []  # (rel, language, source)

    for path in walk_repository(root):
        rel = str(path.relative_to(root))
        language = detect_language(path.name)
        try:
            size = path.stat().st_size
        except OSError:
            continue
        total_bytes += size
        file_count += 1

        source = read_text(path) if language else None
        is_binary = source is None

        file_doc = RepoFile(
            repo_id=repo_id,
            path=rel,
            language=language,
            size_bytes=size,
            line_count=(source.count("\n") + 1) if source else 0,
            is_binary=is_binary,
        ).model_dump()
        files_batch.append(file_doc)

        if language and source:
            lang_counts[language] = lang_counts.get(language, 0) + 1
            parsed_files.append((rel, language, source))

    if files_batch:
        await db.files.insert_many(files_batch)

    all_paths = {f["path"] for f in files_batch}

    imports_batch: list = []
    for rel, language, source in parsed_files:
        syms = extract_symbols(source, language, rel)
        for s in syms:
            if s["kind"] == "function":
                function_count += 1
            elif s["kind"] == "class":
                class_count += 1
            elif s["kind"] == "route":
                api_count += 1
            sym_doc = CodeSymbol(
                repo_id=repo_id,
                file_path=rel,
                language=language,
                **s,
            ).model_dump()
            symbols_batch.append(sym_doc)

        for mod in extract_imports(source, language):
            target = resolve_import(rel, mod, language, all_paths)
            imports_batch.append({
                "id": __import__("uuid").uuid4().hex,
                "repo_id": repo_id,
                "source_path": rel,
                "raw": mod,
                "target_path": target,
                "target_module": mod,
                "is_external": target is None,
            })
        # flush occasionally
        if len(symbols_batch) >= 500:
            await db.symbols.insert_many(symbols_batch)
            symbols_batch = []
        if len(imports_batch) >= 1000:
            await db.imports.insert_many(imports_batch)
            imports_batch = []

    if symbols_batch:
        await db.symbols.insert_many(symbols_batch)
    if imports_batch:
        await db.imports.insert_many(imports_batch)

    framework, pm = detect_framework(root, lang_counts)
    primary = max(lang_counts.items(), key=lambda kv: kv[1])[0] if lang_counts else None

    await _update_repo(
        repo_id,
        status="ready",                    # BM25 search/chat immediately available
        languages=lang_counts,
        primary_language=primary,
        framework=framework,
        package_manager=pm,
        file_count=file_count,
        function_count=function_count,
        class_count=class_count,
        api_count=api_count,
        total_bytes=total_bytes,
        root_path=str(root),
        embedding_ready=False,
        error=None,
    )

    # Kick off embeddings in the background so the UI is usable immediately.
    asyncio.create_task(_embed_symbols(repo_id))


async def _embed_symbols(repo_id: str) -> None:
    """Background pass: batch-embed indexed symbols and persist vectors."""
    try:
        symbol_docs = await db.symbols.find({"repo_id": repo_id}, {"_id": 0}).to_list(15000)
        if not symbol_docs:
            return
        # cap to keep large monorepos feasible on CPU
        cap = 2500
        symbol_docs = symbol_docs[:cap]
        texts = [
            " ".join(filter(None, [
                s.get("kind", ""), s.get("name", ""), s.get("signature", ""),
                s.get("file_path", ""), s.get("snippet", ""),
            ]))
            for s in symbol_docs
        ]
        embeddings = await embed_texts(texts)
        if not embeddings or len(embeddings) != len(symbol_docs):
            return
        from pymongo import UpdateOne
        ops = [
            UpdateOne(
                {"id": s["id"]},
                {"$set": {"embedding": emb, "embedding_dim": len(emb)}},
            )
            for s, emb in zip(symbol_docs, embeddings)
        ]
        for i in range(0, len(ops), 500):
            await db.symbols.bulk_write(ops[i : i + 500], ordered=False)
        await _update_repo(repo_id, embedding_ready=True)
        print(f"[embed] repo {repo_id}: {len(embeddings)} vectors written")
    except Exception as e:
        print(f"[embed] repo {repo_id} failed: {e}")


async def import_zip(repo_id: str, upload_bytes: bytes) -> None:
    try:
        await _update_repo(repo_id, status="cloning")
        root = await extract_zip_upload(repo_id, upload_bytes)
        await index_repository(repo_id, root)
    except Exception as e:
        await _update_repo(repo_id, status="failed", error=str(e)[:500])


async def import_github(repo_id: str, github_url: str) -> None:
    try:
        await _update_repo(repo_id, status="cloning")
        root = await clone_github_repo(repo_id, github_url)
        await index_repository(repo_id, root)
    except Exception as e:
        await _update_repo(repo_id, status="failed", error=str(e)[:500])


# ---------- File tree helpers ----------

def build_file_tree(paths: list) -> dict:
    """Given a list of relative paths, return a nested tree dict."""
    root = {"name": "", "type": "dir", "children": {}}
    for p in paths:
        parts = p.split("/")
        node = root
        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            children = node["children"]
            if part not in children:
                children[part] = {
                    "name": part,
                    "type": "file" if is_last else "dir",
                    "children": {},
                    "path": "/".join(parts[: i + 1]),
                }
            node = children[part]

    def _finalize(n):
        return {
            "name": n["name"],
            "type": n["type"],
            "path": n.get("path", ""),
            "children": sorted(
                [_finalize(c) for c in n["children"].values()],
                key=lambda x: (x["type"] == "file", x["name"].lower()),
            ),
        }

    return _finalize(root)


async def get_file_content(repo: dict, file_path: str) -> Optional[str]:
    root = repo.get("root_path")
    if not root:
        return None
    # sandbox: resolve and ensure inside root
    root_p = Path(root).resolve()
    target = (root_p / file_path).resolve()
    if not str(target).startswith(str(root_p)):
        return None
    if not target.is_file():
        return None
    try:
        if target.stat().st_size > 800_000:
            return "// File too large to display in preview."
        return target.read_text(errors="ignore")
    except OSError:
        return None
