from fastapi import FastAPI, Depends, Header, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from models import SessionMetadata, Flashcard, GenerationRequest, SyncRequest
from database.db import get_db
from database.models_db import SessionMetadataDB, FlashcardDB
from storage import storage_manager
from ai.gemini_manager import GeminiManager, PrivacyManager

load_dotenv()

import sys

# Ensure Anki Wayland compatibility on Linux
if sys.platform.startswith('linux'):
    os.environ["ANKI_WAYLAND"] = "1"

app = FastAPI(
    title="Flashcards AI API",
    description="Backend para generación automática de flashcards con MLOps",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the Streamlit UI URL
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security: Zero Trust API Key Validation
API_KEY_SECRET = os.getenv("API_KEY_SECRET", "supersecretkey")

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
    return x_api_key

@app.get("/")
async def health_check():
    return {"status": "online", "version": "1.0.0", "cloud_simulation": "LocalStack S3"}

@app.get("/sessions", response_model=List[SessionMetadata])
async def list_sessions(api_key: str = Depends(verify_api_key)):
    # TODO: Implement database fetch
    return []

@app.post("/upload")
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Sube un archivo (Imagen/PDF/Video) a LocalStack S3 y registra la sesión."""
    # 1. Subir a LocalStack
    file_key = f"{session_id}/{file.filename}"
    success = await storage_manager.upload_file(file.file, file_key)
    
    if not success:
        raise HTTPException(status_code=500, detail="Error uploading to S3")
    
    # 2. Registrar en Postgres
    session = db.query(SessionMetadataDB).filter(SessionMetadataDB.session_id == session_id).first()
    if not session:
        session = SessionMetadataDB(session_id=session_id, title=f"Sesión {session_id}")
        db.add(session)
        db.commit()
    
    return {
        "filename": file.filename, 
        "session_id": session_id, 
        "s3_url": storage_manager.get_file_url(file_key),
        "status": "uploaded"
    }

@app.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_flashcards(
    request: GenerationRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Genera tarjetas usando LangChain + Gemini Pro (Async)."""
    # 1. Privacy Check (Presidio)
    privacy = PrivacyManager()
    safe_text = privacy.anonymize(request.text_content)
    
    # 2. IA Generation
    gemini_keys = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY_1", "")
    gemini_model = os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
    first_key = [k.strip() for k in gemini_keys.split(",") if k.strip()][0] if gemini_keys else ""
    gemini = GeminiManager(api_key=first_key, model_name=gemini_model.split(",")[0].strip())
    
    all_cards = []
    for card_type in request.card_types:
        try:
            cards = await gemini.generate_cards(safe_text, card_type, request.prompt_config.get(card_type) if request.prompt_config else None)
            all_cards.extend(cards)
            
            # 3. Guardar en Postgres
            for card in cards:
                db_card = FlashcardDB(
                    session_id=request.session_id,
                    card_type=card_type,
                    front=card.front,
                    back=card.back,
                    options=card.options,
                    tags=card.tags
                )
                db.add(db_card)
            db.commit()
            
        except Exception as e:
            print(f"⚠️ Error generando {card_type}: {e}")
            continue

    return {
        "message": f"Generadas {len(all_cards)} tarjetas", 
        "session_id": request.session_id,
        "count": len(all_cards)
    }

@app.post("/sync")
async def sync_to_anki(
    request: SyncRequest,
    api_key: str = Depends(verify_api_key)
):
    """Envía las tarjetas generadas a la instancia local de Anki."""
    # TODO: Implement AnkiSyncManager integration
    return {"status": "success", "synced_count": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
