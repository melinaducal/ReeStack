"""Internal MCP server: read-only, token-scoped access for the assistant.

The assistant never receives a user id from the model. Instead a
short-lived MCP-kind token is issued server-side and bound to one server
instance (or read from the environment for stdio). Every tool call resolves that
token to exactly one user, so the model can only ever read the
collection and posts of the account that started the request.

Errors returned to the model stay generic on purpose: no SQL text,
table names, or token material is echoed back.
"""
import os
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP
from sqlalchemy.engine import Engine
from sqlmodel import Session

from ..auth import resolve_token
from ..db import engine
from ..services import collection_for, posts_for

TOKEN_ENV_VAR = "REESATCK_MCP_TOKEN"

_ACCESS_ERROR = "Access denied: this session is not authorized for the Reesatck library."
_TOOL_ERROR = "The Reesatck library is unavailable."


class AccessDenied(Exception):
    """Raised for any credential problem, with no internal detail attached."""


def create_server(database_engine: Engine, token_provider: Callable[[], str]) -> FastMCP:
    """Bind credentials and storage per connection, never through global mutation."""
    server = FastMCP("reesatck-internal")

    def read_owned(reader: Callable) -> list[dict]:
        try:
            with Session(database_engine) as session:
                # Resolve on every invocation, including after earlier successful calls.
                user = resolve_token(session, token_provider(), kind="mcp")
                if user is None:
                    raise AccessDenied(_ACCESS_ERROR)
                return reader(session, user.id)
        except AccessDenied:
            raise
        except Exception:
            # Sanitize before FastMCP can serialize or log the underlying exception.
            raise RuntimeError(_TOOL_ERROR) from None

    @server.tool()
    def get_collection() -> list[dict]:
        """Return the signed-in user's personal library entries."""
        return read_owned(collection_for)

    @server.tool()
    def get_my_posts() -> list[dict]:
        """Return the public reflections authored by the signed-in user."""
        return read_owned(posts_for)

    return server


mcp = create_server(engine, lambda: os.getenv(TOKEN_ENV_VAR, ""))


if __name__ == "__main__":
    mcp.run(transport="stdio")
