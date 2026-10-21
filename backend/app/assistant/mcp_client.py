"""Real MCP protocol over SDK memory streams; no per-chat subprocess or network."""
import asyncio
from datetime import timedelta

import anyio
from mcp.shared.memory import create_connected_server_and_client_session
from sqlalchemy.engine import Engine

from .mcp_server import create_server

MCP_TIMEOUT_SECONDS = 15


def _rows(result) -> list[dict]:
    """Accept only successful structured results from our typed read tools."""
    if result.isError:
        raise RuntimeError("MCP tool failed")
    structured = result.structuredContent
    rows = structured.get("result") if isinstance(structured, dict) else None
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise RuntimeError("Invalid MCP tool result")
    return rows


async def _read_context(database_engine: Engine, token: str) -> tuple[list[dict], list[dict]]:
    server = create_server(database_engine, lambda: token)
    # The SDK helper runs initialize + ClientSession over bidirectional memory
    # streams, and cancels/closes the server task on success and exception alike.
    with anyio.fail_after(MCP_TIMEOUT_SECONDS):
        async with create_connected_server_and_client_session(
            server, read_timeout_seconds=timedelta(seconds=MCP_TIMEOUT_SECONDS),
        ) as client:
            entries = _rows(await client.call_tool("get_collection", {}))
            posts = _rows(await client.call_tool("get_my_posts", {}))
            return entries, posts


def read_context(database_engine: Engine, token: str) -> tuple[list[dict], list[dict]]:
    """Called from the synchronous HTTP worker, not an already-running event loop."""
    return asyncio.run(_read_context(database_engine, token))
