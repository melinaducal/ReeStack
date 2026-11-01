from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    message: str = Field(min_length=1, max_length=1500)
    # Optional: continue an existing conversation. Omitted keeps the old
    # stateless behaviour, so the current frontend keeps working.
    conversation_id: Optional[int] = None
    type: Optional[str] = None
    limit: int = Field(default=4, ge=1, le=6)
    exclude_consumed: bool = True


class Recommendation(BaseModel):
    title: str
    type: str
    creator: Optional[str] = None
    reason: str
    in_library: bool = False
    year: Optional[int] = None
    cover_url: Optional[str] = None
    external_id: Optional[str] = None
    source: Optional[str] = None
    matched_genres: List[str] = Field(default_factory=list)


class ChatRecommendResponse(BaseModel):
    message: str = ""
    recommendations: List[Recommendation] = Field(default_factory=list)
    engine: str = "heuristic"
    degraded: bool = False
    warnings: List[str] = Field(default_factory=list)
    conversation_id: Optional[int] = None
    intent: Dict[str, Any] = Field(default_factory=dict)


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)


class ConversationSummary(BaseModel):
    id: int
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    turns: int = 0


class ConversationTurn(BaseModel):
    id: int
    role: str
    content: str
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
