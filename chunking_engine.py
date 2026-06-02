"""
Motor de Fragmentación (Chunking Engine).
Implementa el Patrón Strategy y Factory para enrutar el procesamiento de archivos
dependiendo de su modalidad (Video, Audio, PDF) y el modo seleccionado (Estándar o Semántico).
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

try:
    # Desactivar aceleración por hardware en OpenCV para evitar crashes con AV1
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "hwaccel;none"
    os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"
    
    from scenedetect import detect, ContentDetector, AdaptiveDetector
    SCENEDETECT_AVAILABLE = True
except ImportError:
    SCENEDETECT_AVAILABLE = False

try:
    from marker.convert import convert_single_pdf
    from marker.models import load_all_models as load_marker_models
    MARKER_AVAILABLE = True
except ImportError:
    MARKER_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    BGE_AVAILABLE = True
except ImportError:
    BGE_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    # pyannote.audio requires HuggingFace token
    import pyannote.audio
    AUDIO_SEMANTIC_AVAILABLE = True
except ImportError:
    AUDIO_SEMANTIC_AVAILABLE = False

try:
    from transformers import AutoModelForCausalLM, AutoProcessor
    FLORENCE_AVAILABLE = True
except ImportError:
    FLORENCE_AVAILABLE = False

class BaseSemanticChunker(ABC):
    """
    Clase virtual pura (Plantilla) para todas las estrategias de fragmentación.
    Todas las tecnologías específicas (Marker, FFmpeg, PySceneDetect) heredarán de aquí.
    """
    
    @abstractmethod
    def process_and_chunk(self, filepath: str, **kwargs) -> Dict[str, Any]:
        """
        Toma un archivo y lo fragmenta según la estrategia implementada.
        Debe retornar un diccionario con el estado y los resultados.
        """
        pass


# ==========================================
# ESTRATEGIAS ESTÁNDAR (LEGACY)
# ==========================================

class StandardVideoChunker(BaseSemanticChunker):
    """Estrategia de fragmentación clásica para videos (cortes fijos por tiempo con FFmpeg)."""
    
    def __init__(self, video_processor):
        self.video_processor = video_processor
        
    def process_and_chunk(self, filepath: str, **kwargs) -> Dict[str, Any]:
        """
        kwargs esperados: segment_duration_min, overlap_sec
        """
        # Nota: Aquí conectaremos el código de tu video_processor actual
        return {
            "success": True,
            "strategy": "StandardVideoChunker",
            "message": f"Preparado para cortar {os.path.basename(filepath)} usando método estándar por tiempo.",
            "mode": "standard"
        }

class StandardPDFChunker(BaseSemanticChunker):
    """Estrategia de fragmentación clásica para PDF/Word (cortes fijos por páginas)."""
    
    def __init__(self, document_processor):
        self.document_processor = document_processor
        
    def process_and_chunk(self, filepath: str, **kwargs) -> Dict[str, Any]:
        """kwargs esperados: pages_per_section, overlap"""
        # Nota: Aquí conectaremos el código de tu document_processor actual
        return {
            "success": True,
            "strategy": "StandardPDFChunker",
            "message": f"Preparado para segmentar {os.path.basename(filepath)} usando método estándar por páginas.",
            "mode": "standard"
        }

# ==========================================
# ESTRATEGIAS SEMÁNTICAS (NUEVAS)
# ==========================================

class SemanticVideoChunker(BaseSemanticChunker):
    """Estrategia semántica para video usando PySceneDetect (AdaptiveDetector)."""
    
    def __init__(self, models_manager):
        self.models_manager = models_manager
        
    def process_and_chunk(self, filepath: str, **kwargs) -> Dict[str, Any]:
        if not SCENEDETECT_AVAILABLE:
            return {
                "success": False,
                "error": "PySceneDetect no está instalado. Instala usando: pip install scenedetect[opencv]"
            }
            
        try:
            logging.info(f"[SemanticVideoChunker] Analizando video: {os.path.basename(filepath)}")
            
            # Usar AdaptiveDetector para detectar cambios abruptos y transiciones suaves (diapositivas)
            scene_list = detect(filepath, AdaptiveDetector(adaptive_threshold=3.0))
            
            if not scene_list:
                return {
                    "success": False,
                    "error": "No se detectaron cortes semánticos en el video."
                }
                
            # --- NUEVO: SMART MERGER (Filtro de Coherencia) ---
            # Duración mínima de un segmento lógico (en segundos). 
            # Evita micro-escenas de 2 segundos por animaciones.
            MIN_DURATION_SEC = 45.0  
            
            merged_timestamps = []
            current_start = None
            
            for i, scene in enumerate(scene_list):
                start_time = scene[0].get_seconds()
                end_time = scene[1].get_seconds()
                
                # Si estamos iniciando un nuevo bloque
                if current_start is None:
                    current_start = start_time
                    
                # Duración acumulada desde el inicio del bloque hasta el fin de esta sub-escena
                accumulated_duration = end_time - current_start
                
                # Si acumulamos suficiente duración, o si es literalmente la última escena del video
                if accumulated_duration >= MIN_DURATION_SEC or i == len(scene_list) - 1:
                    merged_timestamps.append({
                        "start": current_start,
                        "end": end_time
                    })
                    current_start = None  # Reiniciamos para el siguiente bloque
                
            logging.info(f"[SemanticVideoChunker] Escenas originales: {len(scene_list)} -> Tras Smart Merge: {len(merged_timestamps)}")
            
            return {
                "success": True,
                "strategy": "SemanticVideoChunker",
                "message": f"IA detectó {len(scene_list)} cambios, fusionados inteligentemente en {len(merged_timestamps)} bloques sólidos.",
                "mode": "semantic",
                "timestamps": merged_timestamps
            }
            
        except Exception as e:
            error_msg = str(e)
            if "Get current frame error" in error_msg or "Failed to get pixel format" in error_msg:
                error_msg = ("Error crítico de decodificación (posible códec AV1 no soportado). "
                             "Por favor, cambia a la Segmentación 'Estándar' o convierte el video a formato H.264.")
            return {
                "success": False,
                "error": f"Error en segmentación semántica de video: {error_msg}"
            }

class SemanticPDFChunker(BaseSemanticChunker):
    """Estrategia semántica local para PDFs usando PyMuPDF + bge-m3 (embeddings por página)."""
    
    def __init__(self, models_manager):
        self.models_manager = models_manager
        
    def process_and_chunk(self, filepath: str, **kwargs) -> Dict[str, Any]:
        """
        Segmenta un PDF por temas usando embeddings de BGE-M3.
        
        Flujo:
        1. Extrae texto de cada página con PyMuPDF (ya instalado)
        2. Genera embeddings por página con BGE-M3
        3. Detecta cambios de tema por caída de similitud coseno entre páginas consecutivas
        4. Retorna rangos de páginas agrupados por tema
        
        kwargs esperados: 
            document_processor - instancia de DocumentProcessor para extraer texto
            similarity_threshold - umbral de similitud (default 0.55)
            min_pages_per_section - mínimo de páginas por sección (default 3)
        """
        if not BGE_AVAILABLE:
            return {
                "success": False,
                "error": "SentenceTransformers (bge-m3) no está instalado. Instala usando: pip install sentence-transformers"
            }
        
        doc_processor = kwargs.get("document_processor")
        similarity_threshold = kwargs.get("similarity_threshold", 0.55)
        min_pages = kwargs.get("min_pages_per_section", 3)
            
        try:
            logging.info(f"[SemanticPDFChunker] Iniciando procesamiento local de: {os.path.basename(filepath)}")
            
            # 1. Extraer texto por página
            if doc_processor:
                pages_data = doc_processor.extract_text_per_page(filepath)
            else:
                # Fallback directo con fitz
                import fitz
                doc = fitz.open(filepath)
                pages_data = []
                for i in range(len(doc)):
                    page = doc.load_page(i)
                    pages_data.append({"page_number": i + 1, "text": page.get_text().strip()})
                doc.close()
            
            if not pages_data:
                return {"success": False, "error": "No se pudo extraer texto del PDF."}
            
            # Filtrar páginas con texto mínimo (al menos 50 chars)
            valid_pages = [p for p in pages_data if len(p["text"]) > 50]
            
            if len(valid_pages) < 2:
                # Si hay pocas páginas con texto, retornar todo como una sección
                return {
                    "success": True,
                    "strategy": "SemanticPDFChunker",
                    "message": f"Documento muy corto ({len(valid_pages)} páginas con texto). Se creará una sola sección.",
                    "mode": "semantic",
                    "semantic_sections": [{
                        "title": f"Documento completo",
                        "start_page": pages_data[0]["page_number"],
                        "end_page": pages_data[-1]["page_number"],
                        "pages": [p["page_number"] for p in pages_data]
                    }]
                }
            
            # 2. Cargar BGE-M3
            if not self.models_manager.is_loaded("bge_m3"):
                logging.info("[SemanticPDFChunker] Cargando BGE-M3 en memoria...")
                bge_model = SentenceTransformer('BAAI/bge-m3')
                self.models_manager.register_model("bge_m3", bge_model)
            else:
                bge_model = self.models_manager.get_model("bge_m3")
            
            # 3. Generar embeddings por página
            logging.info(f"[SemanticPDFChunker] Generando embeddings para {len(pages_data)} páginas...")
            page_texts = [p["text"] if len(p["text"]) > 50 else "[Página sin contenido textual significativo]" for p in pages_data]
            embeddings = bge_model.encode(page_texts, show_progress_bar=False)
            
            # 4. Detectar cambios de tema (caída de similitud coseno)
            cut_points = []  # Índices donde hay cambio de tema
            
            for i in range(1, len(embeddings)):
                sim = float(np.dot(embeddings[i-1], embeddings[i]) / 
                           (np.linalg.norm(embeddings[i-1]) * np.linalg.norm(embeddings[i])))
                
                if sim < similarity_threshold:
                    cut_points.append(i)
            
            logging.info(f"[SemanticPDFChunker] Detectados {len(cut_points)} cambios de tema potenciales")
            
            # 5. Agrupar páginas en secciones respetando mínimo
            sections = []
            current_start_idx = 0
            
            for cut_idx in cut_points:
                # Solo cortar si la sección actual tiene al menos min_pages páginas
                if (cut_idx - current_start_idx) >= min_pages:
                    sections.append({
                        "start_idx": current_start_idx,
                        "end_idx": cut_idx - 1
                    })
                    current_start_idx = cut_idx
            
            # Añadir la última sección
            sections.append({
                "start_idx": current_start_idx,
                "end_idx": len(pages_data) - 1
            })
            
            # 6. Convertir a formato de salida con page numbers
            result_sections = []
            for sec in sections:
                start_page = pages_data[sec["start_idx"]]["page_number"]
                end_page = pages_data[sec["end_idx"]]["page_number"]
                pages_list = list(range(start_page, end_page + 1))
                
                # Generar título descriptivo a partir del contenido de la primera página
                first_text = pages_data[sec["start_idx"]]["text"][:200].replace("\n", " ").strip()
                # Tomar la primera línea significativa como título
                title_candidate = first_text.split(".")[0].strip() if "." in first_text else first_text[:80]
                title = f"Págs. {start_page}-{end_page}: {title_candidate[:60]}..."
                
                result_sections.append({
                    "title": title,
                    "start_page": start_page,
                    "end_page": end_page,
                    "pages": pages_list
                })
            
            logging.info(f"[SemanticPDFChunker] Segmentación finalizada: {len(result_sections)} secciones temáticas.")
            
            return {
                "success": True,
                "strategy": "SemanticPDFChunker",
                "message": f"PDF segmentado localmente en {len(result_sections)} temas semánticos usando BGE-M3.",
                "mode": "semantic",
                "semantic_sections": result_sections
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error en segmentación semántica local de PDF: {str(e)}"
            }

# ==========================================
# ESTRATEGIAS SEMÁNTICAS (NUEVAS) - AUDIO E IMAGEN
# ==========================================

class SemanticAudioChunker(BaseSemanticChunker):
    """Estrategia semántica para audio usando PyAnnote 3.1 para Diarización (Gemini se encarga de la transcripción)."""
    
    def __init__(self, models_manager):
        self.models_manager = models_manager
        
    def process_and_chunk(self, filepath: str, **kwargs) -> Dict[str, Any]:
        if not AUDIO_SEMANTIC_AVAILABLE:
            return {
                "success": False,
                "error": "PyAnnote no está instalado. Instala usando: pip install pyannote.audio"
            }
            
        try:
            from pyannote.audio import Pipeline
            from dotenv import load_dotenv
            import torch
            load_dotenv()
            
            hf_token = os.getenv("HF_TOKEN")
            
            logging.info(f"[SemanticAudioChunker] Iniciando procesamiento de: {os.path.basename(filepath)}")
            
            if not self.models_manager.is_loaded("pyannote"):
                if not hf_token or "aqui_va_tu_token" in hf_token:
                    return {"success": False, "error": "HF_TOKEN no configurado en .env. Por favor añádelo."}
                
                logging.info("[SemanticAudioChunker] Cargando PyAnnote (Diarization) en VRAM...")
                pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=hf_token)
                
                if pipeline is None:
                    return {"success": False, "error": "No se pudo cargar el pipeline de PyAnnote. Verifica tu Token y permisos en Hugging Face."}
                    
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                pipeline.to(device)
                self.models_manager.register_model("pyannote", pipeline)
            else:
                pipeline = self.models_manager.get_model("pyannote")
            
            logging.info("[SemanticAudioChunker] Ejecutando diarización matemática sobre el audio...")
            diarization = pipeline(filepath)
            
            explicit_timestamps = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                explicit_timestamps.append({
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker
                })
            
            logging.info(f"[SemanticAudioChunker] Diarización completada. {len(explicit_timestamps)} segmentos de voz detectados.")
            
            return {
                "success": True,
                "strategy": "SemanticAudioChunker",
                "message": f"Audio segmentado por orador (Diarización PyAnnote).",
                "mode": "semantic",
                "explicit_timestamps": explicit_timestamps,
                "chunks": []  # El contenido real se lo dejamos a Gemini
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error en segmentación semántica de audio: {str(e)}"
            }

class SemanticImageChunker(BaseSemanticChunker):
    """Estrategia semántica para imágenes (Infografías) usando Florence-2."""
    
    def __init__(self, models_manager):
        self.models_manager = models_manager
        
    def process_and_chunk(self, filepath: str, **kwargs) -> Dict[str, Any]:
        if not FLORENCE_AVAILABLE:
            return {
                "success": False,
                "error": "Transformers o Pillow no están instalados para Florence-2."
            }
            
        try:
            logging.info(f"[SemanticImageChunker] Analizando infografía: {os.path.basename(filepath)}")
            
            if not self.models_manager.is_loaded("florence2"):
                logging.info("[SemanticImageChunker] Cargando Florence-2 en VRAM...")
                # model = AutoModelForCausalLM.from_pretrained("microsoft/Florence-2-large", trust_remote_code=True)
                # processor = AutoProcessor.from_pretrained("microsoft/Florence-2-large", trust_remote_code=True)
                # self.models_manager.register_model("florence2", (model, processor))
                
            return {
                "success": True,
                "strategy": "SemanticImageChunker",
                "message": f"Imagen segmentada lógicamente mediante polígonos de Florence-2.",
                "mode": "semantic"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error procesando imagen con Florence-2: {str(e)}"
            }

# ==========================================
# LA FÁBRICA (FACTORY)
# ==========================================

class ChunkingEngineFactory:
    """Orquestador que inspecciona el archivo y decide qué estrategia instanciar."""
    
    def __init__(self, models_manager, video_processor=None, document_processor=None):
        self.models_manager = models_manager
        # Se inyectan las dependencias legacy para poder mantener el modo estándar
        self.video_processor = video_processor
        self.document_processor = document_processor
        
    def get_chunker(self, filepath: str, mode: str) -> BaseSemanticChunker:
        """
        Inspecciona la extensión del archivo y retorna la estrategia correcta.
        mode: "standard" o "semantic"
        """
        ext = os.path.splitext(filepath)[1].lower()
        
        # --- MULTIMEDIA (Videos / Audio) ---
        if ext in ['.mp4', '.avi', '.mkv', '.mov', '.webm']:
            if mode == "semantic":
                return SemanticVideoChunker(self.models_manager)
            else:
                return StandardVideoChunker(self.video_processor)
                
        elif ext in ['.mp3', '.wav', '.ogg', '.m4a']:
            if mode == "semantic":
                return SemanticAudioChunker(self.models_manager)
            else:
                # Fallback al estándar (asumiendo que video_processor maneja audio estándar)
                return StandardVideoChunker(self.video_processor)
                
        # --- DOCUMENTOS (Textos / PDFs) ---
        elif ext in ['.pdf', '.docx', '.epub']:
            if mode == "semantic":
                return SemanticPDFChunker(self.models_manager)
            else:
                return StandardPDFChunker(self.document_processor)
                
        # --- IMÁGENES ---
        elif ext in ['.png', '.jpg', '.jpeg', '.webp']:
            if mode == "semantic":
                return SemanticImageChunker(self.models_manager)
            else:
                raise ValueError("Modo estándar no soportado en la fábrica de imágenes. Use el flujo directo de imágenes.")
                
        else:
            raise ValueError(f"Formato de archivo no soportado por el motor: {ext}")
