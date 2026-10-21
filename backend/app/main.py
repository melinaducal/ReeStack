"""FastAPI application factory for Reesatck."""
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from .db import engine, init_db
from .routes import maybe_seed, router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        maybe_seed(session)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Reesatck API", version="0.1.0", lifespan=lifespan)

    origins = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    }
    for item in os.getenv("ALLOWED_ORIGINS", "").split(","):
        item = item.strip()
        if item:
            origins.add(item)
    origins.add("http://testserver")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(router)

    try:
        from .assistant.router import router as assistant_router

        app.include_router(assistant_router)
    except ImportError:
        pass

    return app


app = create_app()
