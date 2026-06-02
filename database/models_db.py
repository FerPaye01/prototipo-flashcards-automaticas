from sqlalchemy import Column, Integer, String, Boolean, JSON, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from .db import Base

class SessionMetadataDB(Base):
    __tablename__ = "session_metadata"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(255))
    mode = Column(String(50), default="normal")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

class FlashcardDB(Base):
    __tablename__ = "generated_flashcards"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), ForeignKey("session_metadata.session_id"))
    card_type = Column(String(50))
    front = Column(TEXT := String) # String allows text in PG
    back = Column(String)
    options = Column(JSONB)
    tags = Column(ARRAY(String))
    sync_status = Column(Boolean, default=False)
    embedding = Column(Vector(1536))
    created_at = Column(TIMESTAMP, server_default=func.now())
