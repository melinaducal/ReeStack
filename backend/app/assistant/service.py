"""Assistant use cases: obtain MCP-scoped context, then ask the model.

Design notes:
- Credentials come only from environment variables (`OPENAI_API_KEY`,
  `OPENAI_MODEL`). Nothing is hardcoded and a missing key produces a clear
  "not configured" state instead of a fake reply.
- Context comes only from authenticated MCP tools. A request-local token is
  revoked before model invocation, including on failed context reads.
"""
import os
from typing import Optional

from sqlmodel import Session

from .. import auth
from ..models import User
from .mcp_client import read_context

MCP_TOKEN_LIFETIME = 300

SYSTEM_PROMPT = (
    "You are the Reesatck assistant. Reesatck is a personal tracker for books, "
    "films, series, music and scientific papers, combined with a cultural social "
    "feed. You help the user reflect on their own library and posts. Only discuss "
    "the data provided in the context block. Be concise, warm and concrete. If the "
    "context is empty, say so plainly instead of inventing titles."
)


def model_name() -> Optional[str]:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def is_configured() -> bool:
    return model_name() is not None


def build_context(session: Session, user: User) -> str:
    """Delegate access through MCP, always revoking the temporary credential."""
    try:
        # Use the request's engine (including dependency overrides), not a global
        # default database. Separate sessions keep tool/cleanup transactions valid.
        database_engine = session.get_bind()
        with Session(database_engine) as token_session:
            token = auth.issue_token(token_session, user.id, kind="mcp", lifetime=MCP_TOKEN_LIFETIME)
            try:
                entries, posts = read_context(database_engine, token)
            finally:
                auth.revoke_token(token_session, token)
        return _format_context(user, entries, posts)
    except Exception:
        # No direct-data fallback, partial context, credential or database details.
        raise RuntimeError("The assistant context is unavailable.") from None


def _format_context(user: User, entries: list[dict], posts: list[dict]) -> str:
    """Format only successful MCP results; never query private data here."""
    lines = [f"User: {user.display_name} (@{user.username})"]

    if entries:
        lines.append("Personal library:")
        for entry in entries:
            content = entry["content"]
            rating = f", rated {entry['rating']}/5" if entry["rating"] else ""
            review = f", review: {entry['review']}" if entry["review"] else ""
            lines.append(
                f"- [{content['kind']}] {content['title']} by {content['creator']} "
                f"({entry['status']}, progress {entry['progress']}{rating}{review})"
            )
    else:
        lines.append("Personal library: empty")

    if posts:
        lines.append("Their own reflections:")
        for post in posts[:10]:
            target = f" on {post['content']['title']}" if post["content"] else ""
            lines.append(f"- {post['body']}{target}")
    else:
        lines.append("Their own reflections: none yet")

    return "\n".join(lines)


def _build_model():
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model_name(),
        temperature=0.3,
        timeout=60,
        max_retries=2,
    )


def answer(session: Session, user: User, message: str) -> str:
    """Produce a reply, or raise RuntimeError when unavailable."""
    if not is_configured():
        raise RuntimeError("The assistant is not configured. Set OPENAI_API_KEY to enable it.")

    from langchain_core.messages import HumanMessage, SystemMessage

    context = build_context(session, user)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=f"Context (only this user's data):\n{context}"),
        HumanMessage(content=message),
    ]
    try:
        model = _build_model()
        response = model.invoke(messages)
        content = getattr(response, "content", "")
        if isinstance(content, list):
            content = " ".join(str(part) for part in content)
        return str(content).strip()
    except Exception:  # Construction, invocation and malformed provider responses.
        raise RuntimeError("The assistant provider is unavailable.") from None
