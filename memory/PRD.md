# CodeGanak — PRD (v0.3)

## Original problem statement
Build **CodeGanak — an AI-powered software engineering platform** that lets
users upload a repository (ZIP or GitHub URL), semantically indexes it, and
enables architecture exploration, semantic search, repo-aware chat, docs
generation and team collaboration. Inspired by Linear/Vercel/Cursor. Dark
mode first.

## Adapted stack
- **Frontend**: React 19 + Tailwind + shadcn/ui + framer-motion + `@xyflow/react` (React Flow) + `dagre`
- **Backend**: FastAPI + Motor (MongoDB) + JWT + bcrypt
- **AI**: Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`) via `emergentintegrations`
- **Embeddings**: `fastembed` (BAAI/bge-small-en-v1.5, 384-dim, local ONNX runtime)
- **Parser**: Python `ast` + multi-language regex, with import extraction
- **GitHub cloning**: `git clone --depth 1` (public repos, `GIT_TERMINAL_PROMPT=0`)

## User personas
- Senior/staff engineers onboarding to unfamiliar codebases
- Founders auditing inherited repos
- Teams sharing indexed repositories via workspaces

## Implemented — v0.1 (2026-07-23 initial)
- **Auth**: register / login / me — JWT + bcrypt (`/api/auth/*`)
- **Repo import**: ZIP upload + GitHub URL
- **Indexing pipeline**: clone → parse → extract symbols → stats
- **File tree** API + file content viewer
- **Semantic search** (BM25 in-memory)
- **Streaming chat (SSE)** with Claude Sonnet 4.5 + citations
- **Documentation generator** (Claude)
- **Dashboard / Repository detail** with tabs (Overview, Files, Chat, Search, Docs)
- **Command palette** (⌘K)

## Implemented — v0.3 (2026-07-23 same day, this iteration)
- **Real vector embeddings** via `fastembed` (BGE-small); parses+ready flow now marks repo `ready` first and embeds in a background task. Search falls back to BM25 while embeddings are cooking, then upgrades to cosine-similarity ranking automatically. Search response includes `mode: 'embeddings' | 'bm25'` and the UI shows a `VECTORS` badge when ready.
- **Architecture / Dependency Graph** (`/api/repositories/{id}/graph`): parser now extracts imports for Python, JS/TS, Java, Go, Ruby; a `graph_service` builds module or file-granularity graphs and detects cycles via Tarjan SCC. Frontend `GraphView` renders the graph with React Flow + dagre layout, cycle highlighting (destructive color), minimap and external-package summary.
- **Team Workspaces** with RBAC (`owner`/`admin`/`member`):
  - Personal workspace ("My workspace") is created + backfilled with legacy repos on first login/register/me call (idempotent).
  - New collections: `workspaces`, `memberships`, `invites`.
  - Repos now live inside a workspace; `POST /repositories/upload` and `import-github` accept `workspace_id`.
  - `GET /workspaces`, `POST /workspaces`, `PATCH /workspaces/{id}`, `DELETE` (owner + non-personal), members CRUD, role update, self-leave.
  - **Invite links**: `POST /workspaces/{id}/invites` → shareable URL `/invite/{token}`; anyone signed-in who opens it joins; unauthenticated users are redirected to login and the pending token is preserved.
  - Frontend: `WorkspaceSwitcher` in header (with popover + create dialog), `WorkspaceSettings` page (rename, invites, members table with role selector, danger-zone delete), `AcceptInvite` page.

## Backlog
- P1 — Monaco Editor integration for file preview
- P1 — GitHub OAuth for private repos
- P1 — Chat persistence per user in shared workspaces (currently scoped per user)
- P2 — File-granularity graph tuning for large monorepos (edge weight thresholding)
- P2 — Repository health scoring, unused-symbol detection
- P2 — Doc categories (API docs, folder guide, onboarding)

## Key file map
### Backend
- `server.py` — FastAPI routes (auth, workspaces, invites, repos, graph, search, chat, docs)
- `auth.py` — JWT + bcrypt
- `models.py` — Pydantic models (User, Workspace, Membership, Invite, Repository, CodeSymbol, ImportEdge…)
- `workspace_service.py` — Workspace / membership / invite logic + personal-workspace migration
- `parser.py` — multi-language symbol & import parsing
- `repo_service.py` — clone/extract, two-pass index, background embedding pass
- `ai_service.py` — fastembed vectors + BM25 fallback, Claude Sonnet 4.5 chat streaming
- `graph_service.py` — module/file dependency graph + Tarjan SCC

### Frontend
- `App.js` — routes incl. `/invite/:token`, `/workspaces/:id/settings`
- `pages/*` — Landing, Login, Register, Dashboard, RepositoryDetail, WorkspaceSettings, AcceptInvite
- `components/*` — AppHeader, ChatPanel, FileTree, GraphView, CommandPalette, WorkspaceSwitcher
- `lib/workspaces.js` — Zustand store for current workspace
- `lib/api.js` — axios + streamChat SSE reader
