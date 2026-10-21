"""Assistant HTTP routes."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from ..auth import check_mutation_origin, get_current_user
from ..db import get_session
from ..models import User
from ..schemas import AssistantChat, AssistantStatus
from . import service

router = APIRouter(prefix="/api/assistant")


@router.get("/status", response_model=AssistantStatus)
def status_route():
    return AssistantStatus(configured=service.is_configured(), model=service.model_name())


@router.post("/chat")
def chat_route(
    payload: AssistantChat,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    check_mutation_origin(request)
    try:
        reply = service.answer(session, user, payload.message)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"reply": reply}
