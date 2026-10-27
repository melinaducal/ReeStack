from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import httpx
import os
import json
from app.database import get_db
from app.models import User, Item
from app.auth.utils import SECRET_KEY, ALGORITHM
from jose import jwt

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatMessage(BaseModel):
    message: str

class Recommendation(BaseModel):
    title: str
    type: str
    creator: Optional[str] = None
    reason: str
    in_library: bool = False

async def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

@router.post("/recommend")
async def recommend(message: ChatMessage, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Get user's library exclusively
    user_items = db.query(Item).filter(Item.user_id == user.id).all()
    library = [{"title": i.title, "type": i.type, "creator": i.creator} for i in user_items]
    
    # Build context
    context = f"""Eres un asistente de recomendaciones para ReeStack, una app para libros, películas, series, música y papers.
    
Biblioteca del usuario (ya tiene): {json.dumps(library, ensure_ascii=False)}
    
Usuario pregunta: {message.message}
    
Reglas:
- Recomienda solo libros, películas, series, música o papers.
- NO recomiendes nada que ya esté en la biblioteca del usuario.
- Explica brevemente por qué recomiendas cada uno.
- Respeta filtros: género, tipo, novedades, etc.
- Si pide algo relacionado a un álbum/item, busca similitudes.
- Responde en español, tono cálido y editorial.
- NO inventes información falsa presentada como real.
- Sugiere 2-4 recomendaciones máximo.
    
Formato de respuesta: JSON con este esquema:
{{"recommendations": [{{"title": "...", "type": "book|movie|series|music|paper", "creator": "...", "reason": "explicación breve"}}]}}"""
    
    api_key = os.getenv("LLM_API_KEY")
    api_url = os.getenv("LLM_API_URL", "https://openrouter.ai/api/v1/chat/completions")
    model = os.getenv("LLM_MODEL", "anthropic/claude-3.5-sonnet")
    
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM_API_KEY no configurada")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": os.getenv("LLM_APP_URL", "http://localhost:5173"),
                    "X-Title": os.getenv("LLM_APP_NAME", "ReeStack"),
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": context}
                    ],
                    "temperature": 0.7,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Try to parse JSON
            try:
                result = json.loads(content)
            except:
                # Try to extract JSON
                import re
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    result = json.loads(match.group())
                else:
                    raise HTTPException(status_code=500, detail="Error al parsear respuesta del modelo")
            
            return result
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail="Error de conexión con el modelo de IA")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al generar recomendaciones")

@router.post("/save")
async def save_recommendation(rec: Recommendation, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Check if already exists in user's library
    existing = db.query(Item).filter(Item.title == rec.title, Item.user_id == user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe en tu biblioteca")
    
    db_item = Item(
        title=rec.title,
        type=rec.type,
        creator=rec.creator,
        thoughts=f"Recomendado por chatbot: {rec.reason}",
        user_id=user.id
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return {"message": "Agregado a tu biblioteca", "id": db_item.id}
