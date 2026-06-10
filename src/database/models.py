"""Database models for PostgreSQL."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    JSON,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from src.config import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    api_key = Column(String(255), unique=True, index=True)
    role = Column(Enum("admin", "user", name="user_role"), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    queries = relationship("Query", back_populates="user")
    documents = relationship("Document", back_populates="uploaded_by")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    filing_type = Column(String(20), default="10-K")
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    chunk_count = Column(Integer, default=0)
    status = Column(Enum("pending", "processing", "indexed", "error", name="doc_status"), default="pending")
    metadata = Column(JSON)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    uploaded_by = relationship("User", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    section = Column(String(255))
    chunk_index = Column(Integer)
    embedding_id = Column(String(255))
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="chunks")


class Query(Base):
    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text)
    model_used = Column(String(50))
    complexity = Column(String(20))
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Integer)
    tools_used = Column(JSON)
    citations = Column(JSON)
    feedback_score = Column(Integer)  # 1-5 rating
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="queries")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    session_id = Column(String(255), unique=True, index=True)
    title = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    role = Column(Enum("user", "assistant", "system", name="message_role"), nullable=False)
    content = Column(Text, nullable=False)
    model_used = Column(String(50))
    tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class CostTracker(Base):
    __tablename__ = "cost_tracker"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    model = Column(String(50), nullable=False)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    query_type = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


# Database setup - lazy initialization
_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, echo=settings.debug)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=get_engine())


def get_db():
    """Dependency for FastAPI."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
