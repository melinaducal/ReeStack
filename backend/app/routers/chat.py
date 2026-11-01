import json
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import ChatConversation, ChatTurn, Item, User
from app.schemas import (
    ChatMessage,
    ChatRecommendResponse,
    ConversationCreate,
    ConversationSummary,
    ConversationTurn,
    Recommendation,
)
from app.services import recommender

router = APIRouter(prefix="/chat", tags=["chat"])

# How many previous turns are sent to the model as context.
MAX_HISTORY_TURNS = 6


def _owned_conversation(db: Session, user: User, conversation_id: int) -> ChatConversation:
    conversation = (
        db.query(ChatConversation)
        .filter(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user.id,
        )
        .first()
    )
    if conversation is None:
        # Same answer for "does not exist" and "belongs to someone else", so
        # one user cannot probe another user's history.
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return conversation


def _history(conversation: ChatConversation) -> List[Dict[str, str]]:
    turns = conversation.turns[-MAX_HISTORY_TURNS:]
    return [{"role": turn.role, "content": turn.content} for turn in turns]


def _recommended_titles(conversation: ChatConversation) -> set:
    titles = set()
    for turn in conversation.turns:
        if not turn.recommendations:
            continue
        try:
            payload = json.loads(turn.recommendations)
        except (TypeError, ValueError):
            continue
        for item in payload or []:
            if isinstance(item, dict) and item.get("title"):
                titles.add(recommender.normalize(item["title"]))
    return titles


def _summary(conversation: ChatConversation) -> ConversationSummary:
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        turns=len(conversation.turns),
    )


@router.post("/recommend", response_model=ChatRecommendResponse)
async def recommend(
    payload: ChatMessage,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = None
    if payload.conversation_id is not None:
        conversation = _owned_conversation(db, user, payload.conversation_id)

    history = _history(conversation) if conversation else []
    already_suggested = _recommended_titles(conversation) if conversation else set()

    result = await recommender.recommend(
        db,
        user,
        payload.message,
        forced_type=payload.type,
        limit=payload.limit,
        exclude_consumed=payload.exclude_consumed,
        exclude_titles=already_suggested,
        history=history,
    )

    result["recommendations"] = result["recommendations"][: payload.limit]

    if conversation is not None:
        if not conversation.title:
            conversation.title = payload.message.strip()[:80]
        db.add(
            ChatTurn(
                conversation_id=conversation.id,
                role="user",
                content=payload.message,
            )
        )
        db.add(
            ChatTurn(
                conversation_id=conversation.id,
                role="assistant",
                content=result["message"],
                recommendations=json.dumps(result["recommendations"], ensure_ascii=False),
            )
        )
        db.commit()
        result["conversation_id"] = conversation.id

    return result


@router.post("/conversations", response_model=ConversationSummary, status_code=201)
def create_conversation(
    payload: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = ChatConversation(user_id=user.id, title=payload.title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return _summary(conversation)


@router.get("/conversations", response_model=List[ConversationSummary])
def list_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversations = (
        db.query(ChatConversation)
        .filter(ChatConversation.user_id == user.id)
        .order_by(ChatConversation.id.desc())
        .all()
    )
    return [_summary(conversation) for conversation in conversations]


@router.get("/conversations/{conversation_id}", response_model=List[ConversationTurn])
def get_conversation(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = _owned_conversation(db, user, conversation_id)
    turns = []
    for turn in conversation.turns:
        try:
            payload = json.loads(turn.recommendations) if turn.recommendations else []
        except (TypeError, ValueError):
            payload = []
        turns.append(
            ConversationTurn(
                id=turn.id,
                role=turn.role,
                content=turn.content,
                recommendations=payload,
                created_at=turn.created_at,
            )
        )
    return turns


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = _owned_conversation(db, user, conversation_id)
    db.delete(conversation)
    db.commit()
    return Response(status_code=204)


@router.post("/save")
def save_recommendation(
    rec: Recommendation,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Check if already exists in user's library
    existing = (
        db.query(Item)
        .filter(Item.title == rec.title, Item.user_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe en tu biblioteca")

    db_item = Item(
        title=rec.title,
        type=rec.type,
        creator=rec.creator,
        year=rec.year,
        cover_url=rec.cover_url,
        thoughts=f"Recomendado por chatbot: {rec.reason}",
        user_id=user.id,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return {"message": "Agregado a tu biblioteca", "id": db_item.id}
