"""Shared serializers and query helpers.

Every JSON representation of a row is produced here, so the API, the
assistant MCP layer, and future consumers all see the same shapes and
never leak password hashes or tokens.
"""
import json
from typing import List, Optional

from sqlmodel import Session, func, select

from .models import Comment, Content, Entry, Like, Post, User


def user_public_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "bio": user.bio,
        "avatar_color": user.avatar_color,
    }


def content_to_dict(content: Content) -> dict:
    try:
        tags = json.loads(content.tags) if content.tags else []
    except (TypeError, ValueError):
        tags = []
    return {
        "id": content.id,
        "title": content.title,
        "creator": content.creator,
        "kind": content.kind,
        "year": content.year,
        "description": content.description,
        "cover_key": content.cover_key,
        "total_units": content.total_units,
        "unit_label": content.unit_label,
        "tags": tags,
    }


def entry_to_dict(entry: Entry, content: Content) -> dict:
    return {
        "id": entry.id,
        "content": content_to_dict(content),
        "status": entry.status,
        "progress": entry.progress,
        "rating": entry.rating,
        "review": entry.review,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


def post_to_dict(
    post: Post,
    author: User,
    content: Optional[Content],
    like_count: int,
    comment_count: int,
    liked: bool,
) -> dict:
    return {
        "id": post.id,
        "author": user_public_dict(author),
        "body": post.body,
        "content": content_to_dict(content) if content else None,
        "rating": post.rating,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "like_count": like_count,
        "comment_count": comment_count,
        "liked": liked,
        "is_demo": post.is_demo,
    }


def comment_to_dict(comment: Comment, author: User) -> dict:
    return {
        "id": comment.id,
        "author": user_public_dict(author),
        "body": comment.body,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


def _content_map(session: Session, content_ids: set) -> dict:
    if not content_ids:
        return {}
    rows = session.exec(select(Content).where(Content.id.in_(content_ids))).all()
    return {c.id: c for c in rows}


def _user_map(session: Session, user_ids: set) -> dict:
    if not user_ids:
        return {}
    rows = session.exec(select(User).where(User.id.in_(user_ids))).all()
    return {u.id: u for u in rows}


def serialize_posts(
    session: Session,
    posts: List[Post],
    viewer: Optional[User] = None,
) -> List[dict]:
    post_ids = [p.id for p in posts]
    content_ids = {p.content_id for p in posts if p.content_id}
    user_ids = {p.user_id for p in posts}
    contents = _content_map(session, content_ids)
    users = _user_map(session, user_ids)

    like_counts: dict = {}
    comment_counts: dict = {}
    liked: set = set()
    if post_ids:
        like_rows = session.exec(
            select(Like.post_id, func.count(Like.id)).where(Like.post_id.in_(post_ids)).group_by(Like.post_id)
        ).all()
        like_counts = {row[0]: row[1] for row in like_rows}
        comment_rows = session.exec(
            select(Comment.post_id, func.count(Comment.id)).where(Comment.post_id.in_(post_ids)).group_by(Comment.post_id)
        ).all()
        comment_counts = {row[0]: row[1] for row in comment_rows}
        if viewer is not None:
            mine = session.exec(
                select(Like.post_id).where(Like.post_id.in_(post_ids), Like.user_id == viewer.id)
            ).all()
            liked = set(mine)

    return [
        post_to_dict(
            p,
            users.get(p.user_id),
            contents.get(p.content_id) if p.content_id else None,
            like_counts.get(p.id, 0),
            comment_counts.get(p.id, 0),
            p.id in liked,
        )
        for p in posts
        if users.get(p.user_id) is not None
    ]


def collection_for(session: Session, user_id: int) -> List[dict]:
    """Private personal collection for one owner, newest activity first."""
    rows = session.exec(
        select(Entry, Content)
        .join(Content, Entry.content_id == Content.id)
        .where(Entry.user_id == user_id)
        .order_by(Entry.updated_at.desc(), Entry.id.desc())
    ).all()
    return [entry_to_dict(entry, content) for entry, content in rows]


def posts_for(session: Session, user_id: int) -> List[dict]:
    """Posts authored by one user (used by the MCP assistant tools)."""
    posts = session.exec(
        select(Post).where(Post.user_id == user_id).order_by(Post.created_at.desc(), Post.id.desc())
    ).all()
    viewer = session.get(User, user_id)
    return serialize_posts(session, posts, viewer)
