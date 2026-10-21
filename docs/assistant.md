# Assistant context through authenticated MCP

Reesatck chat reads the signed-in user's collection and authored posts through
the real MCP tool protocol before calling LangChain's `ChatOpenAI` adapter.
There is no direct-database fallback when MCP fails.

## Local configuration

Set `OPENAI_API_KEY` in the backend process environment to enable the provider.
`OPENAI_MODEL` defaults to `gpt-4o-mini`. No environment file is required or
loaded by this integration. Do not put credentials in chat messages, source
files, browser storage, or tool arguments.

- `GET /api/assistant/status` is public and reports configuration, not provider
  connectivity. Without a key it returns `{"configured": false, "model": null}`.
- `POST /api/assistant/chat` requires the normal authenticated browser session
  and mutation-origin checks. Send `{"message": "Summarize my library."}`.
  A successful response is `{"reply": "..."}`; anonymous requests remain 401.
- A configured chat can send the user's message, display name, username,
  collection context and authored reflections to the configured model provider.
  Set a key and invoke chat only when that external transfer and any provider
  charges are authorized. Local tests never call the provider.

## Request and credential lifecycle

1. Authenticate the HTTP request. If the provider is unconfigured, return 503
   before issuing any MCP token or constructing a provider.
2. Reuse `issue_token` to issue a random `kind="mcp"` token with a 300-second
   lifetime for the authenticated user. Only its hash is stored. No submitted
   user ID determines the account.
3. Bind a fresh FastMCP server to that token and the request session's database
   engine. The MCP SDK's in-memory transport initializes a real `ClientSession`
   and calls `get_collection` and then `get_my_posts`, each with `{}` arguments.
   There is no subprocess per chat, HTTP MCP endpoint, or process-environment
   mutation. Concurrent requests do not share a server's token binding.
4. Every tool invocation opens its own database session, resolves the token
   with `kind="mcp"`, and uses the existing owner-scoped reader and serializers
   in that same session. Both tools are read-only and accept no user ID.
5. On success or failure, close the MCP transport/server task and invoke
   `revoke_token` in `finally`, deleting the temporary record. Revocation happens
   **before** provider construction/invocation, so provider errors cannot leave
   a delegated credential behind. The browser session token is not revoked.
6. Format only successful structured tool results as context, then invoke the
   model. Tokens and provider credentials are not placed in model messages.

## Failure behavior

| Condition | HTTP result |
| --- | --- |
| Missing provider key | 503: `The assistant is not configured. Set OPENAI_API_KEY to enable it.` |
| MCP initialization, timeout, authorization, tool, result-shape or cleanup failure | 503: `The assistant context is unavailable.` |
| Provider construction, invocation or response processing fails | 503: `The assistant provider is unavailable.` |

A failed tool does not trigger a provider call, a partial-context answer, or a
direct read. The next tool is not called after a failed collection read. Raw
tool/provider exception messages are not returned to the browser; underlying
database exceptions are sanitized before the MCP SDK can log or serialize them.

## Standalone stdio remains available

From `backend`, `python -m app.assistant.mcp_server` runs the same two tools over
stdio for trusted local MCP clients. Set `DATABASE_URL` to the intended absolute
SQLite URI and supply a short-lived MCP-kind token through
`REESATCK_MCP_TOKEN` in the child process environment. Browser session tokens,
missing tokens, revoked tokens and expired tokens cannot authorize tool reads.
Do not print a token or place it on the command line. The trusted caller owns
issuance and revocation for standalone sessions; chat handles both automatically.

## Limits and verification

- This is fixed read-only context retrieval, not an autonomous tool-calling
  agent. The model cannot select users, mutate records or invoke extra tools.
- The existing reader shapes/order are preserved. The formatter includes the
  returned collection and the ten most recent authored posts. There is no chat
  history, token-budget truncation, or provider streaming in this MVP.
- MCP exchanges have a 15-second cooperative deadline. Synchronous database
  operations are not forcibly interrupted by that deadline. The existing model
  adapter uses a 60-second provider timeout and up to two retries.
- Normal exception paths revoke immediately. A process crash or unavailable
  database can prevent deletion; the five-minute expiry still bounds access.
  There is no expired-token pruning job in this integration.
- Focused tests: `python -m pytest tests/test_assistant.py tests/test_mcp_context.py -q`
  from `backend`, with `PYTHONDONTWRITEBYTECODE=1`,
  `PYTHON_DOTENV_DISABLED=1` and an external `TEMP`/`TMP` directory. They cover
  real stdio and in-memory protocol calls, two-owner isolation, unchanged data
  and browser authentication, revocation between calls, credential cleanup,
  malformed results and sanitized failure paths. Provider responses are stubbed.
