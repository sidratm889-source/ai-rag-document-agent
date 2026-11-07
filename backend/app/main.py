from fastapi import FastAPI
from app.api.auth import router as auth_router
import os
from app.database import models  # registers SQLAlchemy models before create_all()
from app.database.connection import (
    Base,
    engine,
    ensure_pgvector_extension,
    ensure_conversation_messages_schema,
)
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router
from fastapi.middleware.cors import CORSMiddleware
from app.database.models import User

app = FastAPI(title="AI RAG Document Agent")
app.include_router(auth_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    os.getenv("FRONTEND_URL", "http://localhost:3000")
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    ensure_pgvector_extension()
    Base.metadata.create_all(bind=engine)
    ensure_conversation_messages_schema()
    app.state.db_ready = True
except Exception as exc:
    app.state.db_ready = False
    app.state.db_error = str(exc)

app.include_router(documents_router)
app.include_router(chat_router)


@app.get("/health")
def health_check():
    if getattr(app.state, "db_ready", False):
        return {"status": "ok"}

    return {
        "status": "degraded",
        "database": "unavailable"
    }

@app.get("/db-test")
def database_test():
    try:
        with engine.connect():
            return {"database": "connected"}
    except Exception:
        return {"database": "error"}