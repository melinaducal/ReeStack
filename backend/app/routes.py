"""HTTP routes for the Reesatck API."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session, func, select

from .auth import (
    check_mutation_origin,
    clear_session_cookie,
    get_current_user,
    get_optional_user,
    hash_password,
    issue_token,
    revoke_token,
    set_session_cookie,
    verify_password,
)
from .db import get_session
from .models import Comment, Content, Entry, Like, Post, User
from .schemas import (
    AssistantChat,
    AssistantStatus,
    CollectionAdd,
    CommentCreate,
    ContentCreate,
    EntryPatch,
    HealthOut,
    LikeOut,
    PostCreate,
    UserLogin,
    UserOut,
    UserRegister,
)
from .services import (
    collection_for,
    comment_to_dict,
    content_to_dict,
    entry_to_dict,
    post_to_dict,
    serialize_posts,
    user_public_dict,
)
from .seed import seed_demo

router = APIRouter(prefix="/api")


def _guard(request: Request) -> None:
    check_mutation_origin(request)


def _user_out(user: User) -> UserOut:
    return UserOut(**user_public_dict(user))


def _entry_for_user(session: Session, user: User, entry_id: int) -> Entry:
    entry = session.get(Entry, entry_id)
    if entry is None or entry.user_id != user.id:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


def _content_or_404(session: Session, content_id: int) -> Content:
    content = session.get(Content, content_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Content not found")
    return content


def _entry_payload(session: Session, entry: Entry) -> dict:
    content = _content_or_404(session, entry.content_id)
    return entry_to_dict(entry, content)


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok")


@router.post("/auth/register", response_model=UserOut, status_code=201)
def register(payload: UserRegister, request: Request, response: Response, session: Session = Depends(get_session)):
    _guard(request)
    existing = session.exec(select(User).where(User.username == payload.username)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already taken")
    colors = ["#5b7f68", "#7a6a9b", "#b06b4a", "#4a6d8c", "#8a7a4a", "#6a8a7a"]
    user = User(
        username=payload.username,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        avatar_color=colors[int(payload.username[:2].encode().hex(), 16) % len(colors)],
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    raw = issue_token(session, user.id, kind="session")
    set_session_cookie(response, raw)
    return _user_out(user)


@router.post("/auth/login", response_model=UserOut)
def login(payload: UserLogin, request: Request, response: Response, session: Session = Depends(get_session)):
    _guard(request)
    user = session.exec(select(User).where(User.username == payload.username.strip().lower())).first()
    if user is None or not verify_password(user.password_hash, payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    raw = issue_token(session, user.id, kind="session")
    set_session_cookie(response, raw)
    return _user_out(user)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, session: Session = Depends(get_session)):
    _guard(request)
    raw = request.cookies.get("reesatck_session")
    if raw:
        revoke_token(session, raw)
    clear_session_cookie(response)
    response.status_code = 204
    return response


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)


# ---------------------------------------------------------------------------
# Contents
# ---------------------------------------------------------------------------


@router.get("/contents", response_model=List[dict])
def list_contents(
    q: Optional[str] = None,
    kind: Optional[str] = None,
    offset: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    stmt = select(Content)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where((Content.title.ilike(like)) | (Content.creator.ilike(like)))
    if kind:
        stmt = stmt.where(Content.kind == kind)
    rows = session.exec(stmt.order_by(Content.id).offset(offset).limit(limit)).all()
    return [content_to_dict(c) for c in rows]


@router.post("/contents", response_model=dict, status_code=201)
def create_content(payload: ContentCreate, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _guard(request)
    content = Content(
        title=payload.title,
        creator=payload.creator.strip(),
        kind=payload.kind,
        year=payload.year,
        description=payload.description.strip(),
        cover_key=payload.cover_key,
        total_units=payload.total_units,
        unit_label=payload.unit_label,
        tags=str(payload.tags).replace("'", '"'),
    )
    session.add(content)
    session.commit()
    session.refresh(content)
    return content_to_dict(content)


# ---------------------------------------------------------------------------
# Personal collection
# ---------------------------------------------------------------------------


@router.get("/collection", response_model=List[dict])
def list_collection(
    status_filter: Optional[str] = None,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    stmt = select(Entry, Content).join(Content, Entry.content_id == Content.id).where(Entry.user_id == user.id)
    selected_status = status if status is not None else status_filter
    if selected_status:
        stmt = stmt.where(Entry.status == selected_status)
    if kind:
        stmt = stmt.where(Content.kind == kind)
    rows = session.exec(stmt.order_by(Entry.updated_at.desc(), Entry.id.desc())).all()
    return [entry_to_dict(entry, content) for entry, content in rows]


@router.post("/collection", response_model=dict)
def add_to_collection(
    payload: CollectionAdd,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _guard(request)
    _content_or_404(session, payload.content_id)
    existing = session.exec(
        select(Entry).where(Entry.user_id == user.id, Entry.content_id == payload.content_id)
    ).first()
    if existing is not None:
        response.status_code = 200
        return _entry_payload(session, existing)
    entry = Entry(user_id=user.id, content_id=payload.content_id, status=payload.status, progress=0)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    response.status_code = 201
    return _entry_payload(session, entry)


@router.patch("/collection/{entry_id}", response_model=dict)
def patch_entry(
    entry_id: int,
    payload: EntryPatch,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _guard(request)
    entry = _entry_for_user(session, user, entry_id)
    content = _content_or_404(session, entry.content_id)
    data = payload.model_dump(exclude_unset=True)
    if "progress" in data and content.total_units is not None and data["progress"] > content.total_units:
        raise HTTPException(status_code=422, detail="Progress exceeds total units")
    for key, value in data.items():
        setattr(entry, key, value)
    from .models import utcnow

    entry.updated_at = utcnow()
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return _entry_payload(session, entry)


@router.delete("/collection/{entry_id}", status_code=204)
def delete_entry(entry_id: int, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _guard(request)
    entry = _entry_for_user(session, user, entry_id)
    session.delete(entry)
    session.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Feed / posts
# ---------------------------------------------------------------------------


def _feed_query(
    session: Session,
    viewer: Optional[User],
    kind: Optional[str],
    q: Optional[str],
    sort: str,
    offset: int,
    limit: int,
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    stmt = select(Post)
    if kind:
        stmt = stmt.where(Post.content_id.in_(select(Content.id).where(Content.kind == kind)))
    if q:
        like = f"%{q.strip()}%"
        matching_content = select(Content.id).where((Content.title.ilike(like)) | (Content.creator.ilike(like)))
        stmt = stmt.where(Post.body.ilike(like) | Post.content_id.in_(matching_content))

    if sort == "popular":
        stmt = (
            stmt.outerjoin(Like, Like.post_id == Post.id)
            .group_by(Post.id)
            .order_by(func.count(Like.id).desc(), Post.id.desc())
        )
    else:
        stmt = stmt.order_by(Post.created_at.desc(), Post.id.desc())
    return session.exec(stmt.offset(offset).limit(limit)).all()


@router.get("/posts", response_model=List[dict])
def list_posts(
    kind: Optional[str] = None,
    q: Optional[str] = None,
    sort: str = "latest",
    offset: int = 0,
    limit: int = 100,
    viewer: Optional[User] = Depends(get_optional_user),
    session: Session = Depends(get_session),
):
    if sort not in ("latest", "popular"):
        sort = "latest"
    posts = _feed_query(session, viewer, kind, q, sort, offset, limit)
    return serialize_posts(session, posts, viewer)


@router.post("/posts", response_model=dict, status_code=201)
def create_post(payload: PostCreate, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _guard(request)
    content = None
    if payload.content_id is not None:
        content = _content_or_404(session, payload.content_id)
    post = Post(user_id=user.id, body=payload.body, content_id=payload.content_id if content else None, rating=payload.rating)
    session.add(post)
    session.commit()
    session.refresh(post)
    return post_to_dict(post, user, content, 0, 0, False)


@router.get("/posts/{post_id}/comments", response_model=List[dict])
def list_comments(post_id: int, session: Session = Depends(get_session)):
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    comments = session.exec(
        select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at.asc(), Comment.id.asc())
    ).all()
    out = []
    for c in comments:
        author = session.get(User, c.user_id)
        if author is not None:
            out.append(comment_to_dict(c, author))
    return out


@router.post("/posts/{post_id}/comments", response_model=dict, status_code=201)
def create_comment(
    post_id: int,
    payload: CommentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _guard(request)
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    comment = Comment(post_id=post_id, user_id=user.id, body=payload.body)
    session.add(comment)
    session.commit()
    session.refresh(comment)
    return comment_to_dict(comment, user)


@router.put("/posts/{post_id}/like", response_model=LikeOut)
def like_post(post_id: int, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _guard(request)
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    existing = session.exec(select(Like).where(Like.user_id == user.id, Like.post_id == post_id)).first()
    if existing is None:
        session.add(Like(user_id=user.id, post_id=post_id))
        session.commit()
    count = session.exec(select(func.count(Like.id)).where(Like.post_id == post_id)).one()
    return LikeOut(liked=True, like_count=count)


@router.delete("/posts/{post_id}/like", response_model=LikeOut)
def unlike_post(post_id: int, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _guard(request)
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    existing = session.exec(select(Like).where(Like.user_id == user.id, Like.post_id == post_id)).first()
    if existing is not None:
        session.delete(existing)
        session.commit()
    count = session.exec(select(func.count(Like.id)).where(Like.post_id == post_id)).one()
    return LikeOut(liked=False, like_count=count)


def maybe_seed(session: Session) -> None:
    import os

    if os.getenv("SEED_DEMO", "true").lower() != "false":
        seed_demo(session)
