"""AI service: embeddings-powered semantic search + repo-aware Claude chat.

- Embeddings via `fastembed` (BAAI/bge-small-en-v1.5) running locally through
  ONNX runtime — real semantic vectors, no network dependency.
- Chat via emergentintegrations.LlmChat with Claude Sonnet 4.5.
- Falls back to BM25 automatically if the embedder is unavailable.
"""
from __future__ import annotations

import asyncio
import math
import os
import re
import threading
from collections import Counter
from typing import AsyncIterator, Dict, List, Optional, Tuple

from emergentintegrations.llm.chat import LlmChat, UserMessage

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]

CHAT_MODEL_PROVIDER = "anthropic"
CHAT_MODEL_NAME = "claude-sonnet-4-5-20250929"

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
_EMBED_BATCH_SIZE = 128
_EMBED_MAX_CHARS = 2048

_embedder = None
_embedder_lock = threading.Lock()
_embed_enabled = True


def _get_embedder():
    """Lazy-initialize the ONNX embedder (heavy warmup happens only once)."""
    global _embedder, _embed_enabled
    if _embedder is not None or not _embed_enabled:
        return _embedder
    with _embedder_lock:
        if _embedder is None and _embed_enabled:
            try:
                from fastembed import TextEmbedding

                _embedder = TextEmbedding(model_name=EMBEDDING_MODEL)
                print(f"[embed] loaded {EMBEDDING_MODEL}")
            except Exception as e:
                print(f"[embed] failed to load embedder: {e}")
                _embed_enabled = False
    return _embedder


# ---------------- Embeddings ----------------

async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Return embeddings for `texts` using the local ONNX model."""
    global _embed_enabled
    if not _embed_enabled or not texts:
        return []

    cleaned = [(t or " ")[:_EMBED_MAX_CHARS] for t in texts]
    loop = asyncio.get_event_loop()

    def _do(batch):
        emb = _get_embedder()
        if emb is None:
            return []
        vectors = list(emb.embed(batch))
        return [v.tolist() for v in vectors]

    out: List[List[float]] = []

    for i in range(0, len(cleaned), _EMBED_BATCH_SIZE):
        batch = cleaned[i : i + _EMBED_BATCH_SIZE]

        try:
            vecs = await loop.run_in_executor(None, _do, batch)

            if not vecs:
                _embed_enabled = False
                return []

            out.extend(vecs)

        except Exception as e:
            print(f"[embed] batch failed, disabling embeddings: {e}")
            _embed_enabled = False
            return []

    return out


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = 0.0
    na = 0.0
    nb = 0.0

    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y

    if na == 0 or nb == 0:
        return 0.0

    return dot / (math.sqrt(na) * math.sqrt(nb))


# ---------------- BM25 (fallback) ----------------

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]{1,}")


def tokenize(text: str) -> List[str]:
    if not text:
        return []

    toks = _WORD_RE.findall(text)
    out: List[str] = []

    for t in toks:
        parts = re.findall(
            r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+|[0-9]+",
            t,
        )

        for p in parts:
            p = p.lower()

            if len(p) >= 2:
                out.append(p)

    return out


class BM25Index:
    def __init__(
        self,
        docs: List[Dict],
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.docs = docs
        self.k1 = k1
        self.b = b

        self.doc_tokens = [
            tokenize(d.get("text", ""))
            for d in docs
        ]

        self.doc_len = [
            len(t)
            for t in self.doc_tokens
        ]

        self.avgdl = (
            sum(self.doc_len) / len(self.doc_len)
            if self.doc_len
            else 0
        )

        self.df: Counter = Counter()

        for toks in self.doc_tokens:
            for w in set(toks):
                self.df[w] += 1

        self.N = len(docs) or 1

    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[Tuple[Dict, float]]:
        q = tokenize(query)

        if not q or not self.docs:
            return []

        scores = [0.0] * len(self.docs)

        for term in q:
            n = self.df.get(term, 0)

            idf = math.log(
                1 + (self.N - n + 0.5) / (n + 0.5)
            )

            for i, toks in enumerate(self.doc_tokens):
                if not toks:
                    continue

                tf = toks.count(term)

                if not tf:
                    continue

                dl = self.doc_len[i]

                denom = (
                    tf
                    + self.k1
                    * (
                        1
                        - self.b
                        + self.b
                        * (dl / (self.avgdl or 1))
                    )
                )

                scores[i] += (
                    idf
                    * (tf * (self.k1 + 1))
                    / denom
                )

        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True,
        )

        out: List[Tuple[Dict, float]] = []

        for i, s in ranked[:top_k]:
            if s <= 0:
                break

            out.append(
                (self.docs[i], s)
            )

        return out


# ---------------- Retrieval ----------------

def _symbol_text(s: Dict) -> str:
    return " ".join(
        filter(
            None,
            [
                s.get("name", ""),
                s.get("signature", ""),
                s.get("kind", ""),
                s.get("file_path", ""),
                s.get("snippet", ""),
            ],
        )
    )


async def build_search_docs(
    repo_id: str,
    db,
) -> Tuple[List[Dict], bool]:
    """Return (docs, has_embeddings). `docs` items include `embedding` when available."""
    docs: List[Dict] = []
    has_emb = True

    async for s in db.symbols.find(
        {"repo_id": repo_id},
        {"_id": 0},
    ):
        docs.append(
            {
                "type": "symbol",
                "text": _symbol_text(s),
                "path": s["file_path"],
                "start_line": s.get("start_line", 0),
                "end_line": s.get("end_line", 0),
                "name": s.get("name"),
                "kind": s.get("kind"),
                "snippet": s.get("snippet", "")[:800],
                "language": s.get("language"),
                "embedding": s.get("embedding"),
            }
        )

        if not s.get("embedding"):
            has_emb = False

    async for f in db.files.find(
        {
            "repo_id": repo_id,
            "is_binary": False,
        },
        {"_id": 0},
    ):
        docs.append(
            {
                "type": "file",
                "text": f["path"],
                "path": f["path"],
                "start_line": 1,
                "end_line": f.get("line_count", 1),
                "snippet": "",
                "language": f.get("language"),
                "embedding": None,
            }
        )

    return docs, has_emb and len(docs) > 0


async def semantic_search(
    repo_id: str,
    query: str,
    db,
    top_k: int = 10,
) -> List[Dict]:
    docs, has_emb = await build_search_docs(
        repo_id,
        db,
    )

    ranked: List[Tuple[Dict, float]] = []

    if has_emb and _embed_enabled:
        q_emb_list = await embed_texts([query])

        if q_emb_list:
            q_emb = q_emb_list[0]
            scored = []

            for d in docs:
                if d.get("embedding"):
                    scored.append(
                        (
                            d,
                            cosine(
                                q_emb,
                                d["embedding"],
                            ),
                        )
                    )
                else:
                    scored.append(
                        (d, 0.0)
                    )

            scored.sort(
                key=lambda x: x[1],
                reverse=True,
            )

            ranked = [
                (d, s)
                for d, s in scored
                if s > 0.15
            ][:top_k]

    if not ranked:
        # BM25 fallback
        idx = BM25Index(docs)
        ranked = idx.search(
            query,
            top_k=top_k,
        )

    return [
        {
            "path": d["path"],
            "start_line": d["start_line"],
            "end_line": d["end_line"],
            "kind": d.get("kind") or d.get("type"),
            "name": d.get("name"),
            "language": d.get("language"),
            "snippet": d.get("snippet", ""),
            "score": round(
                float(score),
                3,
            ),
        }
        for d, score in ranked
    ]


# ---------------- Chat ----------------

REPO_SYSTEM_TEMPLATE = """You are CodeGanak, a senior software engineer AI who has deeply
studied the repository "{repo_name}" ({framework}, primary language {language}).

You answer questions ONLY using the retrieved code excerpts provided in the
context below. If the answer isn't clearly supported, say so plainly.

Rules:
- Cite file paths in backticks, e.g. `backend/server.py`.
- When you reference code, quote a short excerpt in a fenced code block.
- Prefer concise, precise engineering-quality answers.
- Explain architecture in terms of components and their responsibilities.
- If asked about something that isn't in the context, say the file wasn't
  found in the retrieved chunks, and suggest what to search for.
"""


def build_context_block(
    chunks: List[Dict],
    budget_chars: int = 12000,
) -> str:
    parts = []
    total = 0

    for c in chunks:
        block = (
            f"### `{c['path']}` "
            f"(lines {c['start_line']}-{c['end_line']}, "
            f"{c.get('kind') or 'file'}"
            + (
                f", {c['name']}"
                if c.get("name")
                else ""
            )
            + ")\n"
            + "```"
            + (c.get("language") or "")
            + "\n"
            + (c.get("snippet") or "")
            + "\n```\n"
        )

        if total + len(block) > budget_chars:
            break

        parts.append(block)
        total += len(block)

    return (
        "\n".join(parts)
        if parts
        else "(No matching code was retrieved.)"
    )


async def chat_stream(
    repo: Dict,
    message: str,
    history: List[Dict],
    db,
) -> AsyncIterator[Dict]:
    repo_id = repo["id"]

    hits = await semantic_search(
        repo_id,
        message,
        db,
        top_k=8,
    )

    citations = [
        {
            "path": h["path"],
            "start_line": h["start_line"],
            "end_line": h["end_line"],
        }
        for h in hits
    ]

    yield {
        "type": "citations",
        "data": citations,
    }

    context_block = build_context_block(hits)

    system_prompt = REPO_SYSTEM_TEMPLATE.format(
        repo_name=repo.get("name", "repo"),
        framework=repo.get("framework")
        or "unknown framework",
        language=repo.get("primary_language")
        or "mixed",
    )

    hist_text = ""

    for m in history[-6:]:
        hist_text += (
            f"\n\n[{m['role']}] "
            f"{m['content']}"
        )

    user_prompt = (
        f"Repository context:\n"
        f"{context_block}\n\n"
        f"Conversation so far:"
        f"{hist_text or ' (none)'}\n\n"
        f"User question: {message}"
    )

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"codeganak-{repo_id}",
        system_message=system_prompt,
    ).with_model(
        CHAT_MODEL_PROVIDER,
        CHAT_MODEL_NAME,
    )

    # Current emergentintegrations SDK exposes send_message()
    # rather than the old TextDelta / StreamDone streaming classes.
    response = await chat.send_message(
        UserMessage(text=user_prompt)
    )

    # Preserve CodeGanak's existing SSE event contract.
    # The frontend still receives a "delta" followed by "done".
    yield {
        "type": "delta",
        "data": response,
    }

    yield {
        "type": "done",
    }


async def generate_documentation(
    repo: Dict,
    db,
) -> str:
    hits = await semantic_search(
        repo["id"],
        "architecture overview main entry points routes models",
        db,
        top_k=12,
    )

    ctx = build_context_block(
        hits,
        budget_chars=14000,
    )

    system = (
        "You are a senior technical writer. "
        "Produce a concise, well-structured "
        "Markdown documentation for the given repository. "
        "Include: Overview, Tech Stack, Architecture, "
        "Key Modules, How to Run. Use headings and "
        "code fences. Be concrete and reference real files."
    )

    prompt = (
        f"Repository: {repo.get('name')} "
        f"({repo.get('framework') or 'unknown'})\n"
        f"Primary language: "
        f"{repo.get('primary_language') or 'mixed'}\n\n"
        f"Retrieved context:\n"
        f"{ctx}\n\n"
        "Write the documentation now."
    )

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"codeganak-docs-{repo['id']}",
        system_message=system,
    ).with_model(
        CHAT_MODEL_PROVIDER,
        CHAT_MODEL_NAME,
    )

    response = await chat.send_message(
        UserMessage(text=prompt)
    )

    return (
        response.strip()
        or "# Documentation\n\n"
        "No output produced."
    )