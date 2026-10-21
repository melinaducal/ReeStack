# Reesatck core API

FastAPI and SQLModel power a private personal collection and a public cultural feed.
The browser contract lives in [`../docs/api-contract.md`](../docs/api-contract.md).
`create_app()` mounts the assistant router when `app.assistant` imports
successfully, including the authenticated MCP integration described in
[`../docs/assistant.md`](../docs/assistant.md). Without `OPENAI_API_KEY` the
assistant reports itself unconfigured and performs no provider or MCP work.

## Run locally

With the project's Python dependencies already available, run from `backend`:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`GET /api/health` returns `{"status":"ok"}`. Interactive endpoint documentation is
available at `/docs`. `create_app()` is the application factory; `app` is the default
export. Tables and optional demo data are created by the application lifespan,
not by importing a module.

## Runtime configuration

Set environment variables before starting Python. No environment file is loaded
automatically, and no credentials are needed for the core API.

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | Absolute SQLite URI for `backend/reesatck.db` | Independent of the launching working directory. Use an absolute SQLite file URI for subprocesses and other services. |
| `SEED_DEMO` | `true` | Local-demo setting. Creates ten catalog records and four explicitly fictional example posts, without network requests. Set `false` before first startup for an empty database. |
| `COOKIE_SECURE` | `false` | Local HTTP only by default. Set `true` when serving over HTTPS. |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173` | Comma-separated exact origins. Paths, wildcards, and embedded credentials are rejected. An empty setting permits no cross-origin browsers. |
| `REESATCK_MCP_TOKEN` | unset | Standalone stdio MCP process only. A short-lived `kind="mcp"` token issued by a trusted caller. The chat route never reads it. |
| `OPENAI_API_KEY` | unset | Enables the assistant provider. Unset keeps `/api/assistant/chat` at 503 and skips MCP entirely. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model id passed to the LangChain provider adapter. |

Boolean variables accept `true/false`, `1/0`, `yes/no`, or `on/off`. Invalid values
fail at app creation. Tests additionally allow `http://testserver`.

Demo startup is idempotent and preserves existing records. Disabling the seed
does not erase data already created. Demo authors cannot sign in; their password
hashes are unusable, their public names identify them as demos, and all sample
posts have `is_demo: true`. If a real account already occupies a demo username,
no sample activity is attached to it. Catalog totals are fixed demonstration
metadata, not edition-specific or live episode counts.

## Browser and privacy boundary

- Register and log in with JSON. The opaque `reesatck_session` cookie is
  HttpOnly, SameSite=Lax, path `/`, and expires after seven days. Logout revokes
  that session and clears its cookie. Raw tokens never enter JSON responses.
- Every POST, PUT, PATCH, and DELETE requires `X-Reesatck-Request: 1`, including
  login and registration. Unexpected Origin values are rejected; credentialed
  CORS uses only the explicit allowlist. Requests without Origin still need the
  mutation header.
- Passwords use Argon2id and must be 10–128 characters, not blank. They are not
  trimmed. Usernames are trimmed, lowercased, and restricted to 3–30 ASCII
  letters, digits, or underscores. Display names are 1–80 trimmed characters.
- Entries, progress, ratings, and reviews remain private. Only deliberate posts
  and comments are public. Responses whitelist fields; validation errors omit
  submitted input so even rejected passwords are not echoed.
- Ownership is checked in the entry query before changing or deleting anything.
  A missing or another owner's entry returns the same 404. Bad login responses
  use the same generic 401 for missing users, wrong passwords, and demo users.
- Invalid or expired cookies are anonymous on the public feed, but receive 401
  on private endpoints. Bearer headers are not browser authentication, and an
  MCP token cannot act as a browser session.

## Tracker and feed behavior

Saving an existing content item returns 200 with its original entry, including
progress and timestamp; a new save returns 201. Entry patches use only explicitly
supplied fields. `rating: null` clears a rating; other patch fields reject null.
An empty review clears it. Empty patches leave the entry unchanged.

Progress is an integer from 0 to a known total, capped at 1,000,000 when the total
is unknown. Positive totals are capped at 1,000,000. Marking a known-length item
completed fills its progress unless progress is explicitly supplied; all supplied
progress is validated before any change. Neither reviews, ratings, nor linked
posts require completion or even a saved collection entry. Ratings are integers
from 1 through 5; booleans, numeric strings, and fractions are rejected.

Post bodies are 1–5,000 trimmed characters; comments are 1–2,000. Reviews and
descriptions allow up to 5,000. Titles allow 1–240 and creators 1–160. Tags allow
at most 12 strings of 1–30 characters, normalized to lowercase with whitespace
collapsed and duplicates removed. Custom content uses a local kind-based cover
key; callers cannot submit remote cover URLs or impersonate demo posts.

Catalog and feed queries accept `q` up to 200 characters, `offset` 0–10,000, and
`limit` 1–100. Catalog search covers titles and creators; feed search additionally
covers post bodies. Search wildcard characters are literal. All kinds, statuses,
and sort modes are validated. Catalog order is descending ID. Entries, comments,
and latest posts use descending date then ID. Popular posts sort by like count,
then the same date/ID tie-breakers. Comments and collections return at most 100
rows; collection filters apply before the bound. Repeated likes and unlikes never
inflate counts. Counts include all matching rows, not only a displayed page.

## Internal extension seam

| Export | Contract |
| --- | --- |
| `app.db.engine`, `get_session()` | Configured engine and yielding SQLModel session dependency. SQLite foreign keys are enabled on every connection. |
| `app.auth.current_user` | Cookie-only FastAPI dependency, yielding `User` or raising 401. |
| `issue_token(session, user_id, kind="session", lifetime=604800) -> str` | Commits a random opaque token; only its SHA256 digest is stored. Internal callers may request `kind="mcp"` with a short lifetime. |
| `resolve_token(session, raw, kind="session") -> User` | Checks current database state, expected kind, and Unix-second expiry on every call; rejects with 401. |
| `collection_for(session, user_id) -> list[dict]` | Up to 100 owned entries, using the same whitelist and query logic as HTTP. |
| `posts_for(session, user_id) -> list[dict]` | Up to 100 authored posts, never the whole public feed. Dates are already ISO UTC strings. |
| `app.models` | Exports `User`, `Content`, `Entry`, `Post`, `Comment`, `Like`, and `AuthToken`. Token primary key is `token_hash`; other fields are `user_id`, `kind`, and `expires_at`. |

Parent integration can include `app.assistant.router` in `create_app()` after the
core router. Never accept a user ID from a tool caller: derive it from its verified
MCP token, and revoke the temporary token when the assistant operation ends.

## Verification and deployment limits

The core suite is `tests/test_core.py`; it exercises public HTTP behavior and the
documented internal reader/token seam. The assistant and MCP suites are
`tests/test_assistant.py` and `tests/test_mcp_context.py`. Fixtures replace the
engine and session dependency with isolated in-memory SQLite databases. No test
uses application data, credentials, network services, or an environment file.
Disable Python bytecode writes and use an external fresh pytest base directory:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHON_DOTENV_DISABLED = '1'
python -m pytest -q -p no:cacheprovider --basetemp='C:\Temp\reesatck-core-unique-run'
```

This is a local MVP, not a hardened public deployment. Authentication throttling
allows 20 attempts per client IP per 60 seconds and keeps at most 1,024 process-local
buckets. It resets on restart, is not shared across workers, and does not trust
forwarded IP headers itself. Configure a trusted reverse proxy with request-size
limits and durable rate limiting before exposure. Also require HTTPS, secure
cookies, an explicit production origin, disabled demos, backups, schema migrations,
and a retention policy for expired tokens. There is no account recovery, email
verification, moderation, or expired-token cleanup job. Seed initialization assumes
a single local startup worker. Public-feed serialization is bounded but performs
per-post count/author lookups; revisit batching before scaling beyond SQLite demo
traffic. Personal activity summaries can be derived by the client from its bounded
collection; there is no uncontracted summary endpoint.
