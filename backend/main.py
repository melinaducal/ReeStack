from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import items, auth, comments, chat, likes, books
from app.database import engine, Base
from dotenv import load_dotenv

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ReeStack API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(items.router)
app.include_router(auth.router)
app.include_router(comments.router)
app.include_router(chat.router)
app.include_router(likes.router)
app.include_router(books.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to ReeStack API"}
