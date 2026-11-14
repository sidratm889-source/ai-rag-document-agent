from datetime import datetime, timezone
from app.database.connection import Base
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, DateTime, Index



class Document(Base):
    __tablename__ = "document"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    user_id = Column(Integer, nullable=True, index=True)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key = True, index = True)
    document_id = Column(String, nullable = False)
    chunk_text = Column(String, nullable = False)
    embedding = Column(Vector(384), nullable = False)
    page_number = Column(Integer, nullable=True)
    section_heading = Column(String, nullable=True)

class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
      Index("conversations_conversation_id_key", "conversation_id", unique=True),
    )
    id = Column(Integer, primary_key=True)
    conversation_id = Column(String, nullable=False)
    user_id = Column(Integer, nullable=True, index=True)
    created_at = Column(
    DateTime,
    default=lambda: datetime.now(timezone.utc),
    nullable=False
)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        String,
        nullable=False,
        index=True
    )
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    action = Column(String, nullable=False)
    status = Column(String, nullable=False)
    details = Column(String, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

