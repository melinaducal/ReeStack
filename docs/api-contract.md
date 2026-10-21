# Reesatck API contract

All routes start with `/api`. JSON uses snake_case. Dates are ISO 8601 UTC. Errors use `{ "detail": "Human-readable message" }` (validation may use FastAPI's standard detail array). Lists are JSON arrays, bounded to 100 records by default. IDs are integers.

## Identity and privacy

The browser uses an opaque HttpOnly SameSite=Lax cookie (`reesatck_session`) and `credentials: 'include'`. Mutations send `X-Reesatck-Request: 1`; the API rejects unsafe requests without this header and rejects untrusted Origin values. `POST /auth/logout` revokes the presented session token and returns an empty body whose `Set-Cookie` clears `reesatck_session` (`Max-Age=0`); a client without that clear still holds a cookie whose token no longer resolves. Production must enable secure cookies and an explicit origin allowlist. Passwords use Argon2. Raw session tokens never enter JSON responses or localStorage. Collection rows are always scoped to the authenticated owner. Public posts/comments expose only public author fields, never email or password hashes.

## Shapes

```text
User = {id, username, display_name, bio, avatar_color}
Content = {id, title, creator, kind, year, description, cover_key, total_units, unit_label, tags: string[]}
kind = book | movie | series | music | paper
status = planned | in_progress | completed
Entry = {id, content: Content, status, progress, rating: null|1..5, review, updated_at}
Post = {id, author: User, body, content: Content|null, rating: null|1..5, created_at, like_count, comment_count, liked, is_demo}
Comment = {id, author: User, body, created_at}
```

`progress` is an integer from 0 through `content.total_units` (or >=0 when the total is unknown). `rating` is an integer from 1 through 5. `total_units` is positive or null. Empty review/bio are strings. No progress completion is required for posting or reviewing. `is_demo` marks seeded example posts. Cover keys map to local artwork, never arbitrary remote HTML.

## Routes

| Method and path | Input | Result |
| --- | --- | --- |
| GET /health | — | `{status: "ok"}` |
| POST /auth/register | `{username, display_name, password}` | User, 201 + session cookie |
| POST /auth/login | `{username, password}` | User + session cookie |
| POST /auth/logout | — | 204, revokes token and clears cookie |
| GET /auth/me | — | User or 401 |
| GET /contents | optional `q`, `kind`, `offset`, `limit` | Content[]; public |
| POST /contents | `{title, creator, kind, year?, description?, total_units?, unit_label?, tags?}` | Content, 201; authenticated |
| GET /collection | optional `status`, `kind`; `status_filter` accepted as a compatibility alias | Entry[]; private; filters apply before the 100-row bound |
| POST /collection | `{content_id, status?: "planned"}` | Entry, 201 for new, 200 for existing (never resets existing progress) |
| PATCH /collection/{entry_id} | `{status?, progress?, rating?, review?}` | Entry; null rating clears it |
| DELETE /collection/{entry_id} | — | 204; owner only |
| GET /posts | optional `kind`, `q`, `sort=latest|popular`, `offset`, `limit` | Post[]; public, personalized liked flag if authenticated |
| POST /posts | `{body, content_id?: null, rating?: null}` | Post, 201; body 1..5000 characters |
| GET /posts/{post_id}/comments | — | Comment[]; public |
| POST /posts/{post_id}/comments | `{body}` | Comment, 201; body 1..2000 characters |
| PUT /posts/{post_id}/like | — | `{liked: true, like_count}`; idempotent |
| DELETE /posts/{post_id}/like | — | `{liked: false, like_count}`; idempotent |
| GET /assistant/status | — | `{configured: boolean, model: string|null}` |
| POST /assistant/chat | `{message}` | `{reply}`; authenticated; 503 when unconfigured/unavailable |

Unknown IDs return 404. Accessing another owner's collection row also returns 404. Duplicate usernames return 409. Bad credentials use a generic 401. Authentication required uses 401. Bounds/invalid types use 422. Blank-only user content is rejected.

## Backend extension seam (internal, not browser APIs)

- `app.db.get_session()` yields SQLModel Session; `app.db.engine` uses `DATABASE_URL` (absolute SQLite file URI recommended). App creation uses `create_app()` and lifespan for tables/optional `SEED_DEMO`.
- `app.auth.current_user` is a FastAPI dependency; `app.auth.issue_token(session, user_id, kind="session", lifetime=604800) -> str`; `app.auth.resolve_token(session, raw, kind="session") -> User` rejects invalid/expired/wrong-kind credentials.
- `app.models.AuthToken` stores `token_hash` (primary key SHA256), `user_id`, `kind` and `expires_at` (Unix seconds); imports expose User, Content, Entry, Post, Comment, Like.
- `app.services.collection_for(session, user_id) -> list[dict]`; `app.services.posts_for(session, user_id) -> list[dict]` use the exact Entry and Post response shapes. They never include secrets. `posts_for` restricts to authored posts.
- `create_app()` includes `app.assistant.router` after the core router when its import succeeds; without `OPENAI_API_KEY` the assistant reports itself unconfigured and returns 503 before issuing any MCP token.
- MCP receives a short-lived `kind="mcp"` token either through `REESATCK_MCP_TOKEN` (standalone stdio) or an in-memory request-local binding (chat). Every tool call resolves it with `kind="mcp"`; its only tools are `get_collection` and `get_my_posts`, and neither accepts a user ID. Chat revokes its temporary token in `finally` before provider work, including failure paths.

## Local development

Vite proxies `/api` to `http://127.0.0.1:8000` without rewriting the Origin. API default allowed origins: `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:4173`, `http://127.0.0.1:4173`. Runtime tests may add `http://testserver`. Production serves built frontend from the same origin or uses an explicitly configured proxy; no wildcard credentialed CORS.
