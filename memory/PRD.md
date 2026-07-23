# CodeGanak — PRD (v0.1)

## Original problem statement
Build **CodeGanak — an AI-powered software engineering platform** that lets
users upload a repository (ZIP or GitHub URL), semantically indexes it, and
enables architecture exploration, semantic search, repository-aware chat,
and documentation generation. Inspired by Linear/Vercel/Cursor. Dark-mode
first. See original brief in system prompt.

## Adapted stack (v0.1)
- **Frontend**: React 19 + CRA/craco + Tailwind + shadcn/ui + framer-motion
- **Backend**: FastAPI + Motor (MongoDB) + JWT + bcrypt
- **AI**: Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`) via `emergentintegrations` (Emergent LLM key)
- **Retrieval**: In-memory BM25 over indexed symbols + files (no external vector DB)
- **Parser**: Python `ast` + multi-language regex (JS/TS/Java/Go/Ruby/Python/etc.)
- **GitHub cloning**: `git clone --depth 1` (public repos only)

## User personas
- Senior/staff engineers onboarding to unfamiliar codebases
- Founders auditing inherited repos
- Consultants doing rapid code reviews

## Implemented (v0.1) — 2026-07-23
- **Auth**: register / login / me — JWT + bcrypt (`/api/auth/*`)
- **Repository import**: ZIP upload + GitHub URL (`/api/repositories/upload`, `/api/repositories/import-github`)
- **Repository indexing pipeline**: clone → parse → extract symbols → stats
- **File tree API** + on-demand file content (`/api/repositories/{id}/tree`, `/file`)
- **Semantic search**: BM25 over `{symbols, files}` per-repo (`/api/repositories/{id}/search`)
- **Streaming chat (SSE)**: retrieves top-K → Claude Sonnet 4.5 → tokens streamed + citations (`/api/repositories/{id}/chat`)
- **Chat history** (`/chat/history`)
- **Doc generation** (`/api/repositories/{id}/docs`) — Claude synthesizes README
- **Repository stats**: languages, framework, package manager, routes, top modules
- **Frontend**: Landing, Login, Register, Dashboard, Repository detail (Overview / Files / Chat / Search / Docs), Command palette (⌘K)
- **Data-testids** across every interactive element

## Backlog / next up (P0/P1)
- P0 — Architecture Explorer (React Flow graph of modules/services)
- P0 — Dependency Graph visualization
- P1 — True vector embeddings (Qdrant or in-mem sentence-transformers)
- P1 — GitHub OAuth for private repos
- P1 — Workspace sharing / RBAC
- P2 — Monaco Editor integration for file preview
- P2 — Repository health scoring
- P2 — Deep documentation categories (API docs, folder guide, onboarding)

## Key file map
- `/app/backend/server.py` — FastAPI routes
- `/app/backend/auth.py` — JWT + bcrypt
- `/app/backend/models.py` — Pydantic models
- `/app/backend/parser.py` — Multi-language symbol parser
- `/app/backend/repo_service.py` — Import + index pipeline
- `/app/backend/ai_service.py` — BM25 + Claude Sonnet chat streaming
- `/app/frontend/src/App.js` — Routes + command palette host
- `/app/frontend/src/pages/*` — Landing / Login / Register / Dashboard / RepositoryDetail
- `/app/frontend/src/components/*` — AppHeader / ChatPanel / FileTree / CommandPalette
