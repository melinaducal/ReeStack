# Reesatck

Track what you read, watch, listen to and study — and publish only what you choose.

Reesatck keeps a private personal record of books, films, series, music and papers,
with progress, ratings and reviews. Collection entries and reviews stay visible to
their owner alone; only deliberate posts and comments reach the public community feed.

This repository holds a locally verified MVP: a FastAPI + SQLModel backend, a
React + Vite client, and an assistant that reads your own library through an
internal MCP server.

## Quick path

Requirements: Node.js >= 22.12 and Python 3.12+.

**Backend** — from `backend/`:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`GET /api/health` returns `{"status":"ok"}`. Interactive docs live at `/docs`.

**Frontend** — from the repository root:

```powershell
npm install
npm run dev
```

The dev server runs on `http://127.0.0.1:5173` and proxies `/api` to the backend.

## Verify

| Suite | Command | Expected |
| --- | --- | --- |
| Backend | `python -m pytest` (from `backend/`) | 83 passed |
| Frontend | `npm test` | 61 passed |
| Build | `npm run build` | exit 0 |

The backend suite needs an environment where `pytest` is installed; see
[`backend/README.md`](backend/README.md) for the isolated-base-directory command.

## Layout

| Path | Contents |
| --- | --- |
| `backend/app/` | FastAPI application: models, schemas, auth, routes, services, seed |
| `backend/app/assistant/` | Assistant service and the internal MCP server and client |
| `backend/tests/` | Core, assistant and MCP boundary suites |
| `src/` | React client: views, components, state and interaction tests |
| `docs/` | API contract, assistant contract, frontend notes |
| `odd/tasks/` | Feature registry: specs, tasks and the delivery logbook |

## Contracts

- [`docs/api-contract.md`](docs/api-contract.md) — the browser-facing HTTP contract.
- [`docs/assistant.md`](docs/assistant.md) — the assistant and MCP credential lifecycle.
- [`backend/README.md`](backend/README.md) — runtime configuration, privacy boundary
  and verification limits.

## Status and limits

This is a **local MVP, not a hardened public deployment.** Authentication uses
Argon2id with opaque session cookies and a mutation header, but there is no HTTPS
termination, no durable rate limiting across workers, no schema migrations and no
account recovery. The assistant stays unconfigured without `OPENAI_API_KEY`, and
performs no provider or MCP work in that state.

Read [`backend/README.md`](backend/README.md) before exposing anything publicly.
