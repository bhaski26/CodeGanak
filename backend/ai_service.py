"""AI service: repo-aware chat + semantic search.

Uses:
  - emergentintegrations.LlmChat with Anthropic Claude Sonnet 4.5 for chat.
  - Lightweight BM25-style scoring over indexed code symbols/files for
    retrieval (works fully in-memory, no external vector DB required).
"""
from __future__ import annotations

import os
import math
import re
from collections import Counter
from typing import List, Dict, Optional, AsyncIterator, Tuple

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
CHAT_MODEL_PROVIDER = "anthropic"
CHAT_MODEL_NAME = "claude-sonnet-4-5-20250929"

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]{1,}")


def tokenize(text: str) -> List[str]:
    """Split identifiers on camelCase, snake_case, and non-word chars."""
    if not text:
        return []
    toks = _WORD_RE.findall(text)
    out: List[str] = []
    for t in toks:
        # split camelCase
        parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+|[0-9]+", t)
        for p in parts:
            p = p.lower()
            if len(p) >= 2:
                out.append(p)
    return out


# ---------- BM25 lite ----------

class BM25Index:
    def __init__(self, docs: List[Dict], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1 = k1
        self.b = b
        self.doc_tokens: List[List[str]] = [tokenize(d.get("text", "")) for d in docs]
        self.doc_len = [len(t) for t in self.doc_tokens]
        self.avgdl = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0
        self.df: Counter = Counter()
        for toks in self.doc_tokens:
            for w in set(toks):
                self.df[w] += 1
        self.N = len(docs) or 1

    def _idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1 + (self.N - n + 0.5) / (n + 0.5))

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Dict, float]]:
        q_tokens = tokenize(query)
        if not q_tokens or not self.docs:
            return []
        scores = [0.0] * len(self.docs)
        for term in q_tokens:
            idf = self._idf(term)
            for i, tokens in enumerate(self.doc_tokens):
                if not tokens:
                    continue
                tf = tokens.count(term)
                if not tf:
                    continue
                dl = self.doc_len[i]
                denom = tf + self.k1 * (1 - self.b + self.b * (dl / (self.avgdl or 1)))
                scores[i] += idf * (tf * (self.k1 + 1)) / denom
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results: List[Tuple[Dict, float]] = []
        for i, s in ranked[:top_k]:
            if s <= 0:
                break
            results.append((self.docs[i], s))
        return results


# ---------- Retrieval helpers ----------

async def build_search_docs(repo_id: str, db) -> List[Dict]:
    """Load indexed symbols + files, materialize search docs."""
    docs: List[Dict] = []
    async for s in db.symbols.find({"repo_id": repo_id}, {"_id": 0}):
        text = " ".join(filter(None, [
            s.get("name", ""),
            s.get("signature", ""),
            s.get("kind", ""),
            s.get("file_path", ""),
            s.get("snippet", ""),
        ]))
        docs.append({
            "type": "symbol",
            "text": text,
            "path": s["file_path"],
            "start_line": s.get("start_line", 0),
            "end_line": s.get("end_line", 0),
            "name": s.get("name"),
            "kind": s.get("kind"),
            "snippet": s.get("snippet", "")[:800],
            "language": s.get("language"),
        })
    async for f in db.files.find({"repo_id": repo_id, "is_binary": False}, {"_id": 0}):
        docs.append({
            "type": "file",
            "text": f["path"],
            "path": f["path"],
            "start_line": 1,
            "end_line": f.get("line_count", 1),
            "snippet": "",
            "language": f.get("language"),
        })
    return docs


async def semantic_search(repo_id: str, query: str, db, top_k: int = 10) -> List[Dict]:
    docs = await build_search_docs(repo_id, db)
    index = BM25Index(docs)
    results = index.search(query, top_k=top_k)
    return [
        {
            "path": d["path"],
            "start_line": d["start_line"],
            "end_line": d["end_line"],
            "kind": d.get("kind") or d.get("type"),
            "name": d.get("name"),
            "language": d.get("language"),
            "snippet": d.get("snippet", ""),
            "score": round(score, 3),
        }
        for d, score in results
    ]


# ---------- Chat ----------

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


def build_context_block(chunks: List[Dict], budget_chars: int = 12000) -> str:
    parts = []
    total = 0
    for c in chunks:
        block = (
            f"### `{c['path']}` (lines {c['start_line']}-{c['end_line']}, "
            f"{c.get('kind') or 'file'}"
            + (f", {c['name']}" if c.get("name") else "")
            + ")\n"
            + "```" + (c.get("language") or "") + "\n"
            + (c.get("snippet") or "")
            + "\n```\n"
        )
        if total + len(block) > budget_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n".join(parts) if parts else "(No matching code was retrieved.)"


async def chat_stream(
    repo: Dict,
    message: str,
    history: List[Dict],
    db,
) -> AsyncIterator[Dict]:
    """Async generator that yields event dicts:
        {"type": "citations", "data": [...]}
        {"type": "delta", "data": "text"}
        {"type": "done"}
    """
    repo_id = repo["id"]

    # 1. Retrieve top-K chunks for the current question.
    hits = await semantic_search(repo_id, message, db, top_k=8)
    citations = [
        {"path": h["path"], "start_line": h["start_line"], "end_line": h["end_line"]}
        for h in hits
    ]
    yield {"type": "citations", "data": citations}

    context_block = build_context_block(hits)
    system_prompt = REPO_SYSTEM_TEMPLATE.format(
        repo_name=repo.get("name", "repo"),
        framework=repo.get("framework") or "unknown framework",
        language=repo.get("primary_language") or "mixed",
    )

    # Fold prior chat history into the user turn to keep session_id stable.
    hist_text = ""
    for m in history[-6:]:
        hist_text += f"\n\n[{m['role']}] {m['content']}"

    user_prompt = (
        f"Repository context:\n{context_block}\n\n"
        f"Conversation so far:{hist_text or ' (none)'}\n\n"
        f"User question: {message}"
    )

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"codeganak-{repo_id}",
        system_message=system_prompt,
    ).with_model(CHAT_MODEL_PROVIDER, CHAT_MODEL_NAME)

    async for event in chat.stream_message(UserMessage(text=user_prompt)):
        if isinstance(event, TextDelta):
            yield {"type": "delta", "data": event.content}
        elif isinstance(event, StreamDone):
            break
    yield {"type": "done"}


async def generate_documentation(repo: Dict, db) -> str:
    """Ask Claude to produce a README-style overview using indexed context."""
    hits = await semantic_search(
        repo["id"],
        "architecture overview main entry points routes models",
        db,
        top_k=12,
    )
    ctx = build_context_block(hits, budget_chars=14000)
    system = (
        "You are a senior technical writer. Produce a concise, well-structured "
        "Markdown documentation for the given repository. Include: Overview, "
        "Tech Stack, Architecture, Key Modules, How to Run. Use headings and "
        "code fences. Be concrete and reference real files."
    )
    prompt = (
        f"Repository: {repo.get('name')} ({repo.get('framework') or 'unknown'})\n"
        f"Primary language: {repo.get('primary_language') or 'mixed'}\n\n"
        f"Retrieved context:\n{ctx}\n\n"
        "Write the documentation now."
    )
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"codeganak-docs-{repo['id']}",
        system_message=system,
    ).with_model(CHAT_MODEL_PROVIDER, CHAT_MODEL_NAME)

    parts: List[str] = []
    async for event in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(event, TextDelta):
            parts.append(event.content)
        elif isinstance(event, StreamDone):
            break
    return "".join(parts).strip() or "# Documentation\n\nNo output produced."
