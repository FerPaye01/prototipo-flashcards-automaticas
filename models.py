from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime

# Pydantic v2 Models

class FlashcardBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    front: str
    back: str
    card_type: str
    options: Optional[List[str]] = None
    tags: Optional[List[str]] = Field(default_factory=list)

class FlashcardCreate(FlashcardBase):
    session_id: str

class Flashcard(FlashcardBase):
    id: int
    session_id: str
    created_at: datetime
    sync_status: bool = False

class SessionMetadataBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    session_id: str
    title: Optional[str] = "Nueva Sesión"
    mode: str = "normal"
    meta_data: Optional[Dict[str, Any]] = Field(default_factory=dict)

class SessionMetadata(SessionMetadataBase):
    id: int
    created_at: datetime
    updated_at: datetime

class GenerationRequest(BaseModel):
    session_id: str
    text_content: str
    card_types: List[str]
    prompt_config: Optional[Dict[str, str]] = None

class SyncRequest(BaseModel):
    session_id: str
    deck_name: str
    card_ids: Optional[List[int]] = None # If None, sync all from session
