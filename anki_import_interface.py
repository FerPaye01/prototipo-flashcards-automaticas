"""
Interfaz simplificada para importar flashcards a Anki.
4 cajitas de texto, una para cada estilo de flashcard.
+ Modo Automático con secciones dinámicas para imágenes.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import queue
import os
import sys

# Ensure Anki Wayland compatibility on Linux
if sys.platform.startswith('linux'):
    os.environ["ANKI_WAYLAND"] = "1"

import json
from datetime import datetime
import time
from PIL import Image, ImageTk
import io
import math
from flashcards_converter import FlashcardsConverter
from document_processor import DocumentProcessor
from anki_sync_manager import AnkiSyncManager
from config_sets_manager import ConfigSetsManager
from video_processor import VideoProcessor, VideoSection, VideoSegment
import tempfile
from gemini_flashcard_generator import GeminiFlashcardGenerator
from models_manager import ModelResourceManager
from chunking_engine import ChunkingEngineFactory
from deduplication_window import DeduplicationUI
from evaluation_window import EvaluationUI


# Carpeta maestra para archivos generados
MASTER_FOLDER = "Flashcards Programa"

# Asegurar que la carpeta maestra exista
if not os.path.exists(MASTER_FOLDER):
    os.makedirs(MASTER_FOLDER, exist_ok=True)

# Archivo para guardar sesiones
SESSIONS_FILE = os.path.join(MASTER_FOLDER, "flashcard_sessions.json")
TEXT_SESSIONS_FILE = os.path.join(MASTER_FOLDER, "flashcard_text_sessions.json")
BOOK_SESSIONS_FILE = os.path.join(MASTER_FOLDER, "flashcard_book_sessions.json")


class ImageSection:
    """Representa una sección con imágenes."""
    
    def __init__(self, section_id: int):
        self.section_id = section_id
        self.title = f"Sección {section_id}"
        self.images = []  # Lista de dicts: {path, name, size, format, date, thumbnail}
    
    def add_image(self, path: str) -> dict:
        """Añade una imagen a la sección."""
        try:
            file_size = os.path.getsize(path)
            if file_size > 25 * 1024 * 1024:  # 25 MB limit
                return {"error": f"Imagen excede 25 MB: {os.path.basename(path)}"}
            
            img = Image.open(path)
            img_format = img.format or path.split('.')[-1].upper()
            
            # Crear thumbnail
            thumbnail = img.copy()
            thumbnail.thumbnail((100, 100))
            
            image_data = {
                "path": path,
                "name": os.path.basename(path),
                "size": file_size,
                "format": img_format,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "thumbnail": thumbnail,
                "width": img.width,
                "height": img.height
            }
            self.images.append(image_data)
            return image_data
        except Exception as e:
            return {"error": str(e)}
    
    def remove_image(self, index: int):
        """Elimina una imagen por índice."""
        if 0 <= index < len(self.images):
            self.images.pop(index)
    
    def clear_images(self):
        """Limpia todas las imágenes."""
        self.images.clear()
    
    def get_status(self) -> dict:
        """Retorna el estado de la sección."""
        return {
            "section_id": self.section_id,
            "title": self.title,
            "image_count": len(self.images),
            "total_size": sum(img["size"] for img in self.images),
            "ready": len(self.images) > 0
        }


class TextSection:
    """Representa una sección con texto."""
    
    def __init__(self, section_id: int):
        self.section_id = section_id
        self.title = f"Sección {section_id}"
        self.text = ""  # Contenido de texto
    
    def set_text(self, text: str):
        """Establece el texto de la sección."""
        self.text = text
    
    def get_text(self) -> str:
        """Retorna el texto de la sección."""
        return self.text
    
    def clear_text(self):
        """Limpia el texto."""
        self.text = ""
    
    def get_char_count(self) -> int:
        """Retorna el número de caracteres."""
        return len(self.text)
    
    def get_status(self) -> dict:
        """Retorna el estado de la sección."""
        return {
            "section_id": self.section_id,
            "title": self.title,
            "char_count": len(self.text),
            "ready": len(self.text.strip()) > 0
        }


class AnkiImportInterface:
    """Interfaz para convertir y importar flashcards a Anki."""
    
    CARD_TYPES = {
        "basic": "Basic (Anverso/Reverso)",
        "multiple_choice": "Multiple Choice (Opción Múltiple)",
        "cloze": "Cloze (Respuesta Anidada)",
        "vocabulary": "Vocabulary (Vocabulario)"
    }
    
    SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tiff', '.ico')
    
    def __init__(self, root):
        """Inicializa la interfaz."""
        self.root = root
        self.root.title("Flashcards to Anki Converter")
        self.root.geometry("1200x700")
        
        # --- INFRAESTRUCTURA BASE (Debe ir primero) ---
        import queue
        self.ui_queue = queue.Queue()
        self.root.after(100, self._process_ui_queue)
        
        self.converter = FlashcardsConverter()
        self.anki_manager = AnkiSyncManager()
        self.flashcard_generator = None  # Se inicializa bajo demanda
        self.config_manager = ConfigSetsManager()  # Gestor de configuraciones
        self.video_processor = VideoProcessor(log_callback=self.video_log)  # Procesador de videos
        self.document_processor = DocumentProcessor(log_callback=self.text_log)  # Para PDF/Word
        
        # --- Fase 1 & 2: Infrastructure ---
        self.models_manager = ModelResourceManager()
        self.chunking_factory = ChunkingEngineFactory(
            self.models_manager, 
            self.video_processor, 
            self.document_processor
        )
        
        # Modo actual: "normal", "automatic_images", "automatic_videos", "automatic_text", "automatic_books"
        self.current_mode = "normal"
        
        # Secciones para modo automático (imágenes)

        self.sections = []
        self.section_counter = 0
        self.section_widgets = {}  # section_id -> widgets dict
        self.thumbnail_refs = {}  # Mantener referencias a thumbnails
        
        # Jerarquía compartida para modos automáticos
        self.great_grandparent_deck = tk.StringVar(value="")
        self.grandparent_deck = tk.StringVar(value="")
        self.parent_prefix = tk.StringVar(value="Sección")
        self.hierarchy_counter = 0  # Contador global para el sufijo

        
        # Secciones para modo automático (texto)
        self.text_sections = []
        self.text_section_counter = 0
        self.text_section_widgets = {}  # section_id -> widgets dict
        self.use_ai_structuring_text = tk.BooleanVar(value=False)
        
        # Secciones para modo automático (libros)
        self.book_sections = []
        self.book_section_counter = 0
        self.book_section_widgets = {}
        self.extraction_mode_book = tk.StringVar(value="Apuntes de Estudiante Experto")
        
        # Videos para modo automático (videos)
        self.video_sessions = []  # Lista de sesiones de video procesadas
        self.current_video_path = None  # Video actualmente cargado
        self.current_video_segments = []  # Lista de VideoSegment del video actual
        self.video_sections = []  # Lista de VideoSection para agrupar segmentos
        self.video_section_counter = 0
        self.video_segment_widgets = {}  # segment_id -> widgets dict
        self.video_section_widgets = {}  # section_id -> widgets dict
        self.current_playing_audio = None  # Referencia al audio en reproducción
        self.extraction_mode_video = tk.StringVar(value="Transcripción Estándar")
        self.use_source_context_var = tk.BooleanVar(value=False)  # Switch "Usar Fuente Completa"
        self.source_segment_duration_var = tk.DoubleVar(value=5.0)  # Minutos por segmento de fuente (video/audio)
        self.current_source_context = ""  # Almacena la fuente de consulta generada
        
        # Audio para modo automático (audio)
        self.audio_sessions = []
        self.current_audio_path = None
        self.current_audio_segments = []
        self.audio_sections = []
        self.audio_section_counter = 0
        self.audio_segment_widgets = {}
        self.audio_section_widgets = {}
        self.extraction_mode_audio = tk.StringVar(value="Transcripción Estándar")
        
        # --- Sala de espera para Deduplicación Semántica ---
        self.pending_flashcard_imports = []
        
        # Motor de deduplicación persistente (caché de embeddings sobrevive entre aperturas)
        try:
            from deduplication_engine import DeduplicationEngine
            self.dedup_engine = DeduplicationEngine(log_callback=self.auto_log)
        except Exception as e:
            self.dedup_engine = None
            print(f"⚠️ No se pudo inicializar DeduplicationEngine: {e}")
        
        # Estado de procesamiento
        self.is_processing = False
        
        # Frames principales
        self.normal_frame = None
        self.automatic_images_frame = None
        self.automatic_text_frame = None
        self.automatic_videos_frame = None
        self.automatic_books_frame = None
        self.automatic_audio_frame = None
        
        self.setup_ui()
        self.check_anki_status()
        self._load_pending_queue()

    def _process_ui_queue(self):
        """Heartbeat de la interfaz gráfica: procesa mensajes de hilos en segundo plano."""
        try:
            # Procesar todos los mensajes disponibles en este tick
            while True:
                msg = self.ui_queue.get_nowait()
                msg_type = msg.get("type")
                
                if msg_type == "log":
                    target = msg.get("target")
                    message = msg.get("message")
                    
                    if target == "normal" and hasattr(self, 'logs_text'):
                        self.logs_text.insert("end", f"{message}\n")
                        self.logs_text.see("end")
                    else:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        formatted_msg = f"[{timestamp}] {message}\n"
                        
                        if target == "video" and hasattr(self, 'video_logs_text'):
                            self.video_logs_text.insert("end", formatted_msg)
                            self.video_logs_text.see("end")
                        elif target == "text" and hasattr(self, 'text_logs_text'):
                            self.text_logs_text.insert("end", formatted_msg)
                            self.text_logs_text.see("end")
                        elif target == "audio" and hasattr(self, 'audio_logs_text'):
                            self.audio_logs_text.insert("end", formatted_msg)
                            self.audio_logs_text.see("end")
                        elif target == "auto" and hasattr(self, 'auto_logs_text'):
                            self.auto_logs_text.insert("end", formatted_msg)
                            self.auto_logs_text.see("end")
                        elif target == "book" and hasattr(self, 'book_logs_text'):
                            self.book_logs_text.insert(tk.END, formatted_msg)
                            self.book_logs_text.see(tk.END)
                
                self.ui_queue.task_done()
        except queue.Empty:
            pass
        finally:
            # Reprogramar el siguiente latido
            self.root.after(100, self._process_ui_queue)

    def setup_ui(self):
        """Configura la interfaz gráfica."""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Crear los cuatro frames
        self.setup_normal_mode()
        self.setup_automatic_images_mode()
        self.setup_automatic_text_mode()
        self.setup_automatic_videos_mode()
        self.setup_automatic_books_mode()
        self.setup_automatic_audio_mode()
        
        # Mostrar modo normal por defecto
        self.show_normal_mode()
        
    def apply_hierarchy_names(self):
        """Aplica dinámicamente el prefijo padre a todas las secciones del modo actual y bloquea la edición."""
        prefix = self.parent_prefix.get().strip()
        if not prefix:
            messagebox.showwarning("Falta prefijo", "Escribe un 'Prefijo Padre' para poder aplicar los nombres.")
            return
            
        counter = 1
        
        # Modo Imágenes
        if self.current_mode == "automatic_images":
            for section in self.sections:
                new_title = f"{prefix} {counter}"
                section.title = new_title
                widgets = self.section_widgets.get(section.section_id)
                if widgets:
                    widgets["title_var"].set(new_title)
                    widgets["title_label"].config(text=new_title)
                    # Quitar botón de edición si existe en el header (índice 1)
                    header_frame = widgets["frame"].winfo_children()[0]
                    children = header_frame.winfo_children()
                    if len(children) > 1 and isinstance(children[1], ttk.Button) and children[1].cget("text") == "✏":
                        children[1].grid_forget()
                counter += 1
            self.hierarchy_counter = len(self.sections)
            self.auto_log(f"🔄 Secciones renombradas dinámicamente a '{prefix}'")
            
        # Modo Libros
        elif self.current_mode == "automatic_books":
            for section in self.book_sections:
                new_title = f"{prefix} {counter}"
                section.title = new_title
                widgets = self.book_section_widgets.get(section.section_id)
                if widgets:
                    widgets["title_var"].set(new_title)
                    widgets["title_label"].config(text=new_title)
                    # Quitar botón de edición
                    header_frame = widgets["frame"].winfo_children()[0]
                    children = header_frame.winfo_children()
                    if len(children) > 1 and isinstance(children[1], ttk.Button) and children[1].cget("text") == "✏":
                        children[1].grid_forget()
                counter += 1
            self.hierarchy_counter = len(self.book_sections)
            self.book_log(f"🔄 Secciones de libro renombradas dinámicamente a '{prefix}'")
            
        # Modo Texto
        elif self.current_mode == "automatic_text":
            for section in self.text_sections:
                new_title = f"{prefix} {counter}"
                section.title = new_title
                widgets = self.text_section_widgets.get(section.section_id)
                if widgets:
                    widgets["title_var"].set(new_title)
                    widgets["title_label"].config(text=new_title)
                    header_frame = widgets["frame"].winfo_children()[0]
                    children = header_frame.winfo_children()
                    if len(children) > 1 and isinstance(children[1], ttk.Button) and children[1].cget("text") == "✏":
                        children[1].grid_forget()
                counter += 1
            self.hierarchy_counter = len(self.text_sections)
            self.text_log(f"🔄 Secciones de texto renombradas dinámicamente a '{prefix}'")
            
        # Modo Videos
        elif self.current_mode == "automatic_videos":
            for section in self.video_sections:
                new_title = f"{prefix} {counter}"
                section.title = new_title
                widgets = self.video_section_widgets.get(section.section_id)
                if widgets:
                    # En video, el label es directo
                    if "title_label" in widgets:
                        widgets["title_label"].config(text=new_title)
                counter += 1
            self.hierarchy_counter = len(self.video_sections)
            self.video_log(f"🔄 Secciones de video renombradas dinámicamente a '{prefix}'")
        
        # Modo Audio
        elif self.current_mode == "automatic_audio":
            for section in self.audio_sections:
                new_title = f"{prefix} {counter}"
                section.title = new_title
                widgets = self.audio_section_widgets.get(section.section_id)
                if widgets:
                    if "title_label" in widgets:
                        widgets["title_label"].config(text=new_title)
                counter += 1
            self.hierarchy_counter = len(self.audio_sections)
            self.audio_log(f"🔄 Secciones de audio renombradas dinámicamente a '{prefix}'")
    
    def _create_hierarchy_config_frame(self, parent_frame):
        """Crea el frame de configuración de jerarquía (Mazo Bisabuelo, Mazo Abuelo y Prefijo Padre)."""
        hierarchy_frame = ttk.LabelFrame(parent_frame, text="Jerarquía de Mazos (Anki)", padding="5")
        hierarchy_frame.columnconfigure(1, weight=1)
        hierarchy_frame.columnconfigure(3, weight=1)
        hierarchy_frame.columnconfigure(5, weight=1)
        
        # Mazo Bisabuelo
        ttk.Label(hierarchy_frame, text="Mazo Bisabuelo:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        great_grandparent_entry = ttk.Entry(hierarchy_frame, textvariable=self.great_grandparent_deck, width=20)
        great_grandparent_entry.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        # Mazo Abuelo
        ttk.Label(hierarchy_frame, text="Mazo Abuelo:").grid(row=0, column=2, sticky="e", padx=5, pady=2)
        grandparent_entry = ttk.Entry(hierarchy_frame, textvariable=self.grandparent_deck, width=20)
        grandparent_entry.grid(row=0, column=3, sticky="w", padx=5, pady=2)
        
        # Prefijo Padre
        ttk.Label(hierarchy_frame, text="Prefijo Padre:").grid(row=0, column=4, sticky="e", padx=5, pady=2)
        parent_entry = ttk.Entry(hierarchy_frame, textvariable=self.parent_prefix, width=20)
        parent_entry.grid(row=0, column=5, sticky="w", padx=5, pady=2)
        
        # Controles
        control_frame = ttk.Frame(hierarchy_frame)
        control_frame.grid(row=0, column=6, sticky="e", padx=10, pady=2)
        
        apply_btn = ttk.Button(control_frame, text="✅ Aplicar", command=self.apply_hierarchy_names)
        apply_btn.pack(side="left", padx=2)
        
        def reset_counter():
            self.hierarchy_counter = 0
            messagebox.showinfo("Contador Reiniciado", "El sufijo numérico volverá a empezar desde 1.")
            
        reset_btn = ttk.Button(control_frame, text="🔄 Reset", command=reset_counter, width=8)
        reset_btn.pack(side="left", padx=2)

        return hierarchy_frame

    def setup_normal_mode(self):
        """Configura la vista del modo normal (4 cajitas)."""
        self.normal_frame = ttk.Frame(self.root, padding="10")
        
        self.normal_frame.columnconfigure(0, weight=1)
        self.normal_frame.rowconfigure(2, weight=1)
        
        # Título y botón modo automático
        header_frame = ttk.Frame(self.normal_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=10)
        header_frame.columnconfigure(0, weight=1)
        
        title_label = ttk.Label(header_frame, text="Flashcards to Anki Converter", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, sticky="w")
        
        self.auto_images_btn = ttk.Button(header_frame, text="🖼️ Modo Imágenes",
                                          command=self.show_automatic_images_mode)
        self.auto_images_btn.grid(row=0, column=1, sticky="e", padx=5)
        
        self.auto_text_btn = ttk.Button(header_frame, text="🖊️ Modo Texto",
                                        command=self.show_automatic_text_mode)
        self.auto_text_btn.grid(row=0, column=2, sticky="e", padx=5)
        
        self.auto_videos_btn = ttk.Button(header_frame, text="🎥 Modo Videos",
                                          command=self.show_automatic_videos_mode)
        self.auto_videos_btn.grid(row=0, column=3, sticky="e", padx=5)
        
        self.auto_books_btn = ttk.Button(header_frame, text="📚 Modo Libros",
                                         command=self.show_automatic_books_mode)
        self.auto_books_btn.grid(row=0, column=4, sticky="e", padx=5)
        
        self.auto_audio_btn = ttk.Button(header_frame, text="🎧 Modo Audio",
                                          command=self.show_automatic_audio_mode)
        self.auto_audio_btn.grid(row=0, column=5, sticky="e", padx=5)
        
        # Frame para el prefijo del deck
        prefix_frame = ttk.Frame(self.normal_frame)
        prefix_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        
        ttk.Label(prefix_frame, text="Deck Prefix:").pack(side="left", padx=5)
        self.prefix_var = tk.StringVar(value="Flashcards")
        prefix_entry = ttk.Entry(prefix_frame, textvariable=self.prefix_var, width=30)
        prefix_entry.pack(side="left", padx=5)

        # Estado de Anki
        status_frame = ttk.LabelFrame(self.normal_frame, text="Anki Status", padding="5")
        status_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        
        self.status_label = ttk.Label(status_frame, text="Checking...", foreground="orange")
        self.status_label.pack(side="left")
        
        self.check_button = ttk.Button(status_frame, text="Check Anki", 
                                       command=self.check_anki_status)
        self.check_button.pack(side="left", padx=5)
        
        # Frame para las 4 cajitas
        cards_frame = ttk.LabelFrame(self.normal_frame, text="Flashcards Input", padding="5")
        cards_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=5)
        cards_frame.columnconfigure(0, weight=1)
        cards_frame.columnconfigure(1, weight=1)
        cards_frame.rowconfigure(0, weight=1)
        cards_frame.rowconfigure(1, weight=1)
        
        self.text_widgets = {}
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        
        for (row, col), (card_type, card_label) in zip(positions, self.CARD_TYPES.items()):
            frame = ttk.LabelFrame(cards_frame, text=card_label, padding="5")
            frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            
            text_widget = tk.Text(frame, height=12, width=40, wrap="word")
            text_widget.grid(row=0, column=0, sticky="nsew")
            
            scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text_widget.yview)
            scrollbar.grid(row=0, column=1, sticky="ns")
            text_widget.config(yscrollcommand=scrollbar.set)
            
            count_button = ttk.Button(frame, text="Count Cards", 
                                     command=lambda ct=card_type, cl=card_label: self.count_flashcards(ct, cl))
            count_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
            
            self.text_widgets[card_type] = text_widget

        # Frame de botones
        button_frame = ttk.Frame(self.normal_frame)
        button_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)
        
        self.convert_button = ttk.Button(button_frame, text="Convert & Import to Anki",
                                        command=self.convert_and_import)
        self.convert_button.pack(side="left", padx=5)
        
        self.export_button = ttk.Button(button_frame, text="Export as TSV",
                                       command=self.export_tsv)
        self.export_button.pack(side="left", padx=5)
        
        self.clear_button = ttk.Button(button_frame, text="Clear All",
                                      command=self.clear_all)
        self.clear_button.pack(side="left", padx=5)
        
        # Frame de logs
        logs_frame = ttk.LabelFrame(self.normal_frame, text="Logs", padding="5")
        logs_frame.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=5)
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)
        
        self.logs_text = tk.Text(logs_frame, height=8, width=100, wrap="word")
        self.logs_text.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(logs_frame, orient="vertical", command=self.logs_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.logs_text.config(yscrollcommand=scrollbar.set)

    def setup_automatic_images_mode(self):
        """Configura la vista del modo automático para imágenes."""
        self.automatic_images_frame = ttk.Frame(self.root, padding="10")
        self.automatic_images_frame.columnconfigure(0, weight=3)
        self.automatic_images_frame.columnconfigure(1, weight=1)
        self.automatic_images_frame.rowconfigure(2, weight=1)
        
        # Header con botón de retroceso
        header_frame = ttk.Frame(self.automatic_images_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)
        
        back_btn = ttk.Button(header_frame, text="← Volver", command=self.show_normal_mode)
        back_btn.grid(row=0, column=0, sticky="w")
        
        title_label = ttk.Label(header_frame, text="🤖 Modo Automático - Secciones de Imágenes",
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=1, sticky="w", padx=20)
        
        # Frame de Jerarquía
        hierarchy_frame = self._create_hierarchy_config_frame(self.automatic_images_frame)
        hierarchy_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        # Ajustamos el layout principal (Canvas y Logs) para que empiecen en la fila 2
        # Panel izquierdo: Secciones (scrollable)
        left_container = ttk.Frame(self.automatic_images_frame)
        left_container.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        left_container.columnconfigure(0, weight=1)
        left_container.rowconfigure(0, weight=1)
        
        # Canvas con scrollbar para secciones
        self.sections_canvas = tk.Canvas(left_container, highlightthickness=0)
        sections_scrollbar = ttk.Scrollbar(left_container, orient="vertical", 
                                           command=self.sections_canvas.yview)
        
        self.sections_inner_frame = ttk.Frame(self.sections_canvas)
        self.sections_inner_frame.columnconfigure(0, weight=1)
        
        self.sections_canvas.create_window((0, 0), window=self.sections_inner_frame, 
                                           anchor="nw", tags="inner")
        self.sections_canvas.configure(yscrollcommand=sections_scrollbar.set)
        
        self.sections_canvas.grid(row=0, column=0, sticky="nsew")
        sections_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Bind para actualizar scroll region
        self.sections_inner_frame.bind("<Configure>", self._on_sections_configure)
        self.sections_canvas.bind("<Configure>", self._on_canvas_configure)

        # Panel derecho: Logs
        right_frame = ttk.LabelFrame(self.automatic_images_frame, text="Logs de Imágenes", padding="5")
        right_frame.grid(row=2, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        
        self.auto_logs_text = tk.Text(right_frame, width=40, wrap="word")
        self.auto_logs_text.grid(row=0, column=0, sticky="nsew")
        
        auto_logs_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", 
                                            command=self.auto_logs_text.yview)
        auto_logs_scrollbar.grid(row=0, column=1, sticky="ns")
        self.auto_logs_text.config(yscrollcommand=auto_logs_scrollbar.set)
        
        # Panel inferior: Botones
        bottom_frame = ttk.Frame(self.automatic_images_frame)
        bottom_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        # Fila 1: Gestión de Secciones
        row1 = ttk.Frame(bottom_frame)
        row1.pack(fill="x", side="top", pady=2)
        
        add_section_btn = ttk.Button(row1, text="+ Añadir Sección", 
                                     command=self.add_section)
        add_section_btn.pack(side="left", padx=5)
        
        load_batch_btn = ttk.Button(row1, text="📂 Cargar Lote", 
                                    command=self.load_image_batch)
        load_batch_btn.pack(side="left", padx=5)
        
        check_status_btn = ttk.Button(row1, text="✓ Chequear Estado",
                                      command=self.check_sections_status)
        check_status_btn.pack(side="left", padx=5)
        
        clear_all_sections_btn = ttk.Button(row1, text="🗑 Limpiar Todo",
                                            command=self.clear_all_sections)
        clear_all_sections_btn.pack(side="left", padx=5)
        
        check_api_btn = ttk.Button(row1, text="🔌 Chequear API",
                                   command=self.check_gemini_api)
        check_api_btn.pack(side="left", padx=5)
        
        # Fila 2: Acciones y Configuración
        row2 = ttk.Frame(bottom_frame)
        row2.pack(fill="x", side="top", pady=2)
        
        self.process_sections_btn = ttk.Button(row2, text="🚀 Procesar Secciones",
                                               command=self.process_all_sections_auto)
        self.process_sections_btn.pack(side="left", padx=5)
        ttk.Button(row2, text="🧠 Filtrar Interferencia (IA)", command=self.open_deduplication_window).pack(side="left", padx=5)
        ttk.Button(row2, text="🎓 Rúbrica Pedagógica (IA)", command=self.open_evaluation_window).pack(side="left", padx=5)
        ttk.Button(row2, text="✅ Ejecutar Sincronización", command=self.execute_deduplicated_import).pack(side="left", padx=5)
        
        recover_btn = ttk.Button(row2, text="📂 Recuperar Sesión",
                                 command=self.show_recover_session_dialog)
        recover_btn.pack(side="left", padx=5)
        
        self.pending_btn = ttk.Button(row2, text="📋 Importar Pendientes",
                                      command=self.import_pending_flashcards)
        self.pending_btn.pack(side="left", padx=5)
        self._update_pending_button()
        
        config_btn = ttk.Button(row2, text="⚙️ Configuración",
                               command=self.show_config_dialog)
        config_btn.pack(side="left", padx=5)
        
        # Label del set activo
        self.active_set_label = ttk.Label(row2, text=f"Set: {self.config_manager.active_set_name}",
                                          font=("Segoe UI", 9, "bold"), foreground="blue")
        self.active_set_label.pack(side="right", padx=10)
    
    def setup_automatic_text_mode(self):
        """Configura la vista del modo automático para texto."""
        self.automatic_text_frame = ttk.Frame(self.root, padding="10")
        self.automatic_text_frame.columnconfigure(0, weight=3)
        self.automatic_text_frame.columnconfigure(1, weight=1)
        self.automatic_text_frame.rowconfigure(2, weight=1)
        
        # Header con botón de retroceso
        header_frame = ttk.Frame(self.automatic_text_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)
        
        back_btn = ttk.Button(header_frame, text="← Volver", command=self.show_normal_mode)
        back_btn.grid(row=0, column=0, sticky="w")
        
        title_label = ttk.Label(header_frame, text="🖊️ Modo Automático - Secciones de Texto",
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=1, sticky="w", padx=20)
        
        # Frame de Jerarquía
        hierarchy_frame = self._create_hierarchy_config_frame(self.automatic_text_frame)
        hierarchy_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Ajustar fila para layout izquierdo
        # Panel izquierdo: Secciones (scrollable)
        left_container = ttk.Frame(self.automatic_text_frame)
        left_container.grid(row=2, column=0, sticky="nsew", padx=(0, 10))
        left_container.columnconfigure(0, weight=1)
        left_container.rowconfigure(0, weight=1)
        
        # Canvas con scrollbar para secciones
        self.text_sections_canvas = tk.Canvas(left_container, highlightthickness=0)
        text_sections_scrollbar = ttk.Scrollbar(left_container, orient="vertical", 
                                               command=self.text_sections_canvas.yview)
        
        self.text_sections_inner_frame = ttk.Frame(self.text_sections_canvas)
        self.text_sections_inner_frame.columnconfigure(0, weight=1)
        
        self.text_sections_canvas.create_window((0, 0), window=self.text_sections_inner_frame, 
                                               anchor="nw", tags="inner")
        self.text_sections_canvas.configure(yscrollcommand=text_sections_scrollbar.set)
        
        self.text_sections_canvas.grid(row=0, column=0, sticky="nsew")
        text_sections_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Bind para actualizar scroll region
        self.text_sections_inner_frame.bind("<Configure>", 
            lambda e: self.text_sections_canvas.configure(scrollregion=self.text_sections_canvas.bbox("all")))
        self.text_sections_canvas.bind("<Configure>", 
            lambda e: self.text_sections_canvas.itemconfig("inner", width=e.width))

        # Panel derecho: Logs
        right_frame = ttk.LabelFrame(self.automatic_text_frame, text="Logs de Texto", padding="5")
        right_frame.grid(row=2, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        
        self.text_logs_text = tk.Text(right_frame, width=40, wrap="word")
        self.text_logs_text.grid(row=0, column=0, sticky="nsew")
        
        text_logs_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", 
                                           command=self.text_logs_text.yview)
        text_logs_scrollbar.grid(row=0, column=1, sticky="ns")
        self.text_logs_text.config(yscrollcommand=text_logs_scrollbar.set)
        
        # Panel inferior: Botones
        bottom_frame = ttk.Frame(self.automatic_text_frame)
        bottom_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        # Fila 1: Gestión de Secciones
        trow1 = ttk.Frame(bottom_frame)
        trow1.pack(fill="x", side="top", pady=2)
        
        add_text_section_btn = ttk.Button(trow1, text="+ Añadir Sección", 
                                          command=self.add_text_section)
        add_text_section_btn.pack(side="left", padx=5)
        
        bulk_text_btn = ttk.Button(trow1, text="📄 Pegar y Segmentar Texto", 
                                   command=self.show_bulk_text_segmentation_dialog)
        bulk_text_btn.pack(side="left", padx=5)
        
        check_text_status_btn = ttk.Button(trow1, text="✓ Chequear Estado",
                                           command=self.check_text_sections_status)
        check_text_status_btn.pack(side="left", padx=5)
        
        clear_all_text_sections_btn = ttk.Button(trow1, text="🗑 Limpiar Todo",
                                                 command=self.clear_all_text_sections)
        clear_all_text_sections_btn.pack(side="left", padx=5)
        
        check_api_btn = ttk.Button(trow1, text="🔌 Chequear API",
                                   command=self.check_gemini_api_text)
        check_api_btn.pack(side="left", padx=5)
        
        # Fila 2: Acciones y Configuración
        trow2 = ttk.Frame(bottom_frame)
        trow2.pack(fill="x", side="top", pady=2)
        
        self.process_text_sections_btn = ttk.Button(trow2, text="🚀 Procesar Secciones",
                                                    command=self.process_all_text_sections)
        self.process_text_sections_btn.pack(side="left", padx=5)
        ttk.Button(trow2, text="🧠 Filtrar Interferencia (IA)", command=self.open_deduplication_window).pack(side="left", padx=5)
        ttk.Button(trow2, text="🎓 Rúbrica Pedagógica (IA)", command=self.open_evaluation_window).pack(side="left", padx=5)
        ttk.Button(trow2, text="✅ Ejecutar Sincronización", command=self.execute_deduplicated_import).pack(side="left", padx=5)
        
        # Botón Importar Pendientes
        self.pending_text_btn = ttk.Button(trow2, text="📋 Importar Pendientes", 
                                         command=self.import_pending_flashcards)
        self.pending_text_btn.pack(side="left", padx=5)
        
        ttk.Button(trow2, text="📂 Recuperar Sesión",
                  command=self.show_recover_text_session_dialog).pack(side="left", padx=5)
        
        config_btn = ttk.Button(trow2, text="⚙️ Configuración",
                               command=self.show_config_dialog)
        config_btn.pack(side="left", padx=5)

        ai_struct_cb = ttk.Checkbutton(trow2, text="✨ Estructurar con IA (Estudiante Experto)", 
                                      variable=self.use_ai_structuring_text)
        ai_struct_cb.pack(side="left", padx=10)
        
        # Label del set activo
        self.text_set_label = ttk.Label(trow2, text=f"Set: {self.config_manager.active_set_name}",
                                        font=("Segoe UI", 9, "bold"), foreground="blue")
        self.text_set_label.pack(side="right", padx=10)
        
        # YouTube Downloader
        from youtube_downloader import YoutubeDownloader
        self.youtube_downloader = YoutubeDownloader()
        self.youtube_url_var = tk.StringVar()

    def setup_automatic_books_mode(self):
        """Configura la vista del modo automático para libros (PDF/Word)."""
        self.automatic_books_frame = ttk.Frame(self.root, padding="10")
        self.automatic_books_frame.columnconfigure(0, weight=3)
        self.automatic_books_frame.columnconfigure(1, weight=1)
        self.automatic_books_frame.rowconfigure(3, weight=1)
        
        # Header con botón de retroceso
        header_frame = ttk.Frame(self.automatic_books_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)
        
        back_btn = ttk.Button(header_frame, text="← Volver", command=self.show_normal_mode)
        back_btn.grid(row=0, column=0, sticky="w")
        
        title_label = ttk.Label(header_frame, text="📚 Modo Libros - PDF y Word completo",
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=1, sticky="w", padx=20)
        
        # Frame de configuración y carga
        config_frame = ttk.LabelFrame(self.automatic_books_frame, text="⚙️ Carga y Segmentación", padding="10")
        config_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 5), padx=5)
        config_frame.columnconfigure(1, weight=1)
        
        # Fila 1: Archivo
        ttk.Label(config_frame, text="Archivo (PDF/Word):").grid(row=0, column=0, sticky="w", pady=2)
        self.book_path_var = tk.StringVar()
        book_entry = ttk.Entry(config_frame, textvariable=self.book_path_var, width=60)
        book_entry.grid(row=0, column=1, sticky="ew", padx=5)
        
        def browse_book():
            path = filedialog.askopenfilename(
                title="Seleccionar libro",
                filetypes=[("Documentos", "*.pdf *.docx")]
            )
            if path:
                self.book_path_var.set(path)
        
        browse_btn = ttk.Button(config_frame, text="🔍 Buscar", command=browse_book)
        browse_btn.grid(row=0, column=2, sticky="w")
        
        # Fila 2: Segmentación
        seg_frame = ttk.Frame(config_frame)
        seg_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=2)
        
        # --- Selector de Modo de Segmentación ---
        ttk.Label(seg_frame, text="Segmentación:").pack(side="left", padx=(0, 5))
        self.book_segmentation_mode_var = tk.StringVar(value="Estándar (Páginas fijas)")
        book_seg_modes = [
            "Estándar (Páginas fijas)",
            "Semántico (Gemini Cloud)",
            "Semántico (Local: BGE-M3)"
        ]
        book_mode_combo = ttk.Combobox(seg_frame, textvariable=self.book_segmentation_mode_var,
                                       values=book_seg_modes, state="readonly", width=25)
        book_mode_combo.pack(side="left", padx=5)
        
        ttk.Label(seg_frame, text="Páginas:").pack(side="left", padx=(15, 5))
        self.pages_per_section_var = tk.IntVar(value=10)
        pages_spin = ttk.Spinbox(seg_frame, from_=1, to=100, textvariable=self.pages_per_section_var, width=5)
        pages_spin.pack(side="left", padx=5)
        
        ttk.Label(seg_frame, text="Solape:").pack(side="left", padx=(15, 5))
        self.pages_overlap_var = tk.IntVar(value=1)
        overlap_spin = ttk.Spinbox(seg_frame, from_=0, to=10, textvariable=self.pages_overlap_var, width=5)
        overlap_spin.pack(side="left", padx=5)
        
        def on_book_mode_change(*args):
            is_standard = self.book_segmentation_mode_var.get() == "Estándar (Páginas fijas)"
            state = "normal" if is_standard else "disabled"
            pages_spin.config(state=state)
            overlap_spin.config(state=state)
            
        self.book_segmentation_mode_var.trace_add("write", on_book_mode_change)
        
        segment_btn = ttk.Button(config_frame, text="📑 Segmentar documento", 
                                command=self.process_book_to_sections)
        segment_btn.grid(row=1, column=2, sticky="e")

        # Frame de Jerarquía
        hierarchy_frame = self._create_hierarchy_config_frame(self.automatic_books_frame)
        hierarchy_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        
        # Panel izquierdo: Secciones (scrollable)
        left_container = ttk.Frame(self.automatic_books_frame)
        left_container.grid(row=3, column=0, sticky="nsew", padx=(0, 10))
        left_container.columnconfigure(0, weight=1)
        left_container.rowconfigure(0, weight=1)
        
        self.book_sections_canvas = tk.Canvas(left_container, highlightthickness=0)
        book_sections_scrollbar = ttk.Scrollbar(left_container, orient="vertical", 
                                                command=self.book_sections_canvas.yview)
        
        self.book_sections_inner_frame = ttk.Frame(self.book_sections_canvas)
        self.book_sections_inner_frame.columnconfigure(0, weight=1)
        
        self.book_sections_canvas.create_window((0, 0), window=self.book_sections_inner_frame, 
                                                anchor="nw", tags="inner")
        self.book_sections_canvas.configure(yscrollcommand=book_sections_scrollbar.set)
        
        self.book_sections_canvas.grid(row=0, column=0, sticky="nsew")
        book_sections_scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.book_sections_inner_frame.bind("<Configure>", self._on_book_sections_configure)
        self.book_sections_canvas.bind("<Configure>", 
            lambda e: self.book_sections_canvas.itemconfig("inner", width=e.width))

        # Panel derecho: Logs
        right_frame = ttk.LabelFrame(self.automatic_books_frame, text="Logs de Libros", padding="5")
        right_frame.grid(row=3, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        
        self.book_logs_text = tk.Text(right_frame, width=40, wrap="word")
        self.book_logs_text.grid(row=0, column=0, sticky="nsew")
        
        book_logs_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", 
                                            command=self.book_logs_text.yview)
        book_logs_scrollbar.grid(row=0, column=1, sticky="ns")
        self.book_logs_text.config(yscrollcommand=book_logs_scrollbar.set)
        
        # Panel inferior: Botones
        bottom_frame = ttk.Frame(self.automatic_books_frame)
        bottom_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        brow1 = ttk.Frame(bottom_frame)
        brow1.pack(fill="x", side="top", pady=2)
        
        ttk.Button(brow1, text="+ Añadir Sección", command=self.add_book_section).pack(side="left", padx=5)
        ttk.Button(brow1, text="🗑 Limpiar Todo", command=self.clear_all_book_sections).pack(side="left", padx=5)
        ttk.Button(brow1, text="🔌 Chequear API", command=self.check_gemini_api_book).pack(side="left", padx=5)
        
        brow2 = ttk.Frame(bottom_frame)
        brow2.pack(fill="x", side="top", pady=2)
        
        self.process_book_sections_btn = ttk.Button(brow2, text="🚀 Procesar Secciones",
                                                    command=self.process_all_book_sections)
        self.process_book_sections_btn.pack(side="left", padx=5)
        ttk.Button(brow2, text="🧠 Filtrar Interferencia (IA)", command=self.open_deduplication_window).pack(side="left", padx=5)
        ttk.Button(brow2, text="🎓 Rúbrica Pedagógica (IA)", command=self.open_evaluation_window).pack(side="left", padx=5)
        ttk.Button(brow2, text="✅ Ejecutar Sincronización", command=self.execute_deduplicated_import).pack(side="left", padx=5)
        
        ttk.Button(brow2, text="📋 Importar Pendientes", 
                  command=self.import_pending_flashcards).pack(side="left", padx=5)
        
        ttk.Button(brow2, text="⚙️ Configuración", command=self.show_config_dialog).pack(side="left", padx=5)

        ttk.Button(brow2, text="📂 Recuperar Sesión", 
                  command=self.show_book_recovery_dialog).pack(side="left", padx=5)

        ttk.Label(brow2, text="Modo Extracción:").pack(side="left", padx=(10, 2))
        modes = ["Extracción Cruda (Fiel al documento)", "Apuntes de Estudiante Experto", "Estructuración Completa"]
        mode_cb = ttk.Combobox(brow2, textvariable=self.extraction_mode_book, values=modes, state="readonly", width=35)
        mode_cb.pack(side="left", padx=5)
        
        self.book_set_label = ttk.Label(brow2, text=f"Set: {self.config_manager.active_set_name}",
                                        font=("Segoe UI", 9, "bold"), foreground="blue")
        self.book_set_label.pack(side="right", padx=10)

    def _on_book_sections_configure(self, event):
        self.book_sections_canvas.configure(scrollregion=self.book_sections_canvas.bbox("all"))

    def book_log(self, message):
        """Añade un mensaje al log de libros."""
        self.ui_queue.put({"type": "log", "target": "book", "message": message})

    def process_book_to_sections(self):
        """Procesa el PDF y crea las secciones con IMÁGENES en el modo libros."""
        path = self.book_path_var.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning("Archivo no encontrado", "Por favor selecciona un archivo PDF válido.")
            return
            
        # 0. Determinar el modo de segmentación
        mode_type = getattr(self, "book_segmentation_mode_var", None)
        segmentation_mode = mode_type.get() if mode_type else "Estándar (Páginas fijas)"
        
        self.book_log(f"\n{'='*60}")
        self.book_log(f"📚 PROCESANDO LIBRO (Modo: {segmentation_mode})")
        self.book_log(f"{'='*60}")
        
        # --- RUTA SEMÁNTICA (GEMINI CLOUD) ---
        if segmentation_mode == "Semántico (Gemini Cloud)":
            threading.Thread(target=self._process_book_semantic_gemini, args=(path,), daemon=True).start()
            return
        
        # --- RUTA SEMÁNTICA (LOCAL: BGE-M3) ---
        if segmentation_mode == "Semántico (Local: BGE-M3)":
            threading.Thread(target=self._process_book_semantic_local, args=(path,), daemon=True).start()
            return
            
        # --- RUTA ESTÁNDAR (LEGACY) ---
            
        if not path.lower().endswith('.pdf'):
            # Si es Word, por ahora seguimos con texto o avisamos
            if path.lower().endswith('.docx'):
                self.book_log("⚠️ Modo imágenes no disponible para Word directamente. Usando extracción de texto.")
                return self._process_book_to_sections_text(path)
            messagebox.showwarning("Solo PDF", "La conversión a imágenes está optimizada para archivos PDF.")
            return

        pages_per_section = self.pages_per_section_var.get()
        overlap = self.pages_overlap_var.get()
        
        self.book_log(f"📑 Procesando libro: {os.path.basename(path)}...")
        self.book_log("🖼️ Generando imágenes de cada página... (un momento)")
        
        # Carpeta temporal para las imágenes
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        book_name = "".join(x for x in os.path.splitext(os.path.basename(path))[0] if x.isalnum() or x in "._- ")
        output_dir = os.path.join("temp_books", f"{book_name}_{timestamp}")
        
        # Redirigir logs
        old_callback = self.document_processor.log_callback
        self.document_processor.log_callback = self.book_log
        
        try:
            pages_content = self.document_processor.render_pdf_pages_to_images(path, output_dir)
        finally:
            self.document_processor.log_callback = old_callback
            
        if not pages_content:
            messagebox.showerror("Error", "No se pudo renderizar el PDF.")
            return
            
        sections = self.document_processor.segment_pages(pages_content, pages_per_section, overlap)
        
        self.clear_all_book_sections()
        
        for sec_data in sections:
            self.add_book_section()
            last_section = self.book_sections[-1]
            last_section.title = sec_data["title"]
            
            # Añadir imágenes renderizadas para la previsualización en la UI
            for img_path in sec_data.get("images", []):
                last_section.add_image(img_path)
            
            # [NUEVO] Generar un fragmento de PDF fiel para el procesamiento con Gemini
            pdf_segment_name = f"segment_{last_section.section_id}.pdf"
            pdf_segment_path = os.path.join(output_dir, pdf_segment_name)
            if self.document_processor.split_pdf(path, sec_data["pages"], pdf_segment_path):
                # Guardamos la ruta del PDF segmentado para usarlo después
                setattr(last_section, 'pdf_segment_path', pdf_segment_path)
                self.book_log(f"   📎 PDF segmentado creado para {sec_data['title']}")
            
            self._update_book_section_info(last_section)
                
        self.book_log(f"✅ Se han creado {len(sections)} secciones con PDF fiel e imágenes de previsualización.")
        self._save_current_book_session()
        messagebox.showinfo("Procesamiento Completo", f"Libro listo: {len(sections)} secciones con PDF fiel.")

    def _process_book_semantic_gemini(self, path: str):
        """Segmentación semántica usando Gemini Cloud (hilo de fondo)."""
        try:
            self.book_log("\n🧠 Iniciando Segmentación Semántica con Gemini Cloud...")
            
            # 1. Extraer texto con marcadores de página
            old_callback = self.document_processor.log_callback
            self.document_processor.log_callback = self.book_log
            text_with_markers = self.document_processor.extract_full_text_with_page_markers(path)
            self.document_processor.log_callback = old_callback
            
            if not text_with_markers:
                self.book_log("❌ No se pudo extraer texto del PDF")
                return
            
            # Obtener total de páginas
            import fitz
            doc = fitz.open(path)
            total_pages = len(doc)
            doc.close()
            
            # 2. Enviar a Gemini para análisis semántico
            active_set = self.config_manager.get_active_set()
            if not self.flashcard_generator:
                from gemini_flashcard_generator import GeminiFlashcardGenerator
                self.flashcard_generator = GeminiFlashcardGenerator(log_callback=self.book_log, config_set=active_set)
            else:
                self.flashcard_generator.log_callback = self.book_log
            
            semantic_sections = self.flashcard_generator.analyze_book_semantic_sections(
                text_with_markers, total_pages
            )
            
            if not semantic_sections:
                self.book_log("⚠️ Gemini no pudo identificar secciones. Usando segmentación estándar como fallback...")
                self.root.after(0, lambda: self._fallback_to_standard_segmentation(path))
                return
            
            # 3. Crear secciones en la UI
            self.root.after(0, lambda: self._create_sections_from_semantic_ranges(path, semantic_sections))
            
        except Exception as e:
            self.book_log(f"❌ Error en segmentación semántica Gemini: {e}")

    def _process_book_semantic_local(self, path: str):
        """Segmentación semántica usando BGE-M3 local (hilo de fondo)."""
        try:
            self.book_log("\n🧠 Iniciando Segmentación Semántica Local (BGE-M3)...")
            self.book_log("   ⏳ Esto puede tardar la primera vez (descarga del modelo ~2 GB)...")
            
            # Usar el chunker del motor de segmentación
            chunker = self.chunking_factory.get_chunker(path, "semantic")
            result = chunker.process_and_chunk(
                path, 
                document_processor=self.document_processor,
                similarity_threshold=0.55,
                min_pages_per_section=3
            )
            
            if not result.get("success"):
                self.book_log(f"❌ Error: {result.get('error', 'Fallo desconocido')}")
                return
            
            self.book_log(f"✓ {result.get('message')}")
            
            semantic_sections = result.get("semantic_sections", [])
            if not semantic_sections:
                self.book_log("⚠️ No se detectaron secciones. Usando segmentación estándar como fallback...")
                self.root.after(0, lambda: self._fallback_to_standard_segmentation(path))
                return
            
            # Crear secciones en la UI
            self.root.after(0, lambda: self._create_sections_from_semantic_ranges(path, semantic_sections))
            
        except Exception as e:
            self.book_log(f"❌ Error en segmentación semántica local: {e}")

    def _create_sections_from_semantic_ranges(self, pdf_path: str, semantic_sections: list):
        """
        Crea secciones en la UI a partir de rangos de páginas semánticos.
        Reutiliza la lógica estándar: renderiza imágenes + genera PDFs segmentados.
        
        Args:
            pdf_path: Ruta al PDF original
            semantic_sections: Lista de dicts con 'title', 'pages', 'start_page', 'end_page'
        """
        self.book_log(f"\n📑 Creando {len(semantic_sections)} secciones semánticas en la UI...")
        
        # 1. Renderizar imágenes del PDF completo (si no se hizo antes)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        book_name = "".join(x for x in os.path.splitext(os.path.basename(pdf_path))[0] if x.isalnum() or x in "._- ")
        output_dir = os.path.join("temp_books", f"{book_name}_{timestamp}")
        
        old_callback = self.document_processor.log_callback
        self.document_processor.log_callback = self.book_log
        
        try:
            pages_content = self.document_processor.render_pdf_pages_to_images(pdf_path, output_dir)
        finally:
            self.document_processor.log_callback = old_callback
        
        if not pages_content:
            self.book_log("❌ No se pudo renderizar el PDF para previsualización.")
            return
        
        # Crear un mapa rápido: page_number -> image_path
        page_image_map = {}
        for pc in pages_content:
            page_image_map[pc["page_number"]] = pc.get("image_path", "")
        
        # 2. Limpiar secciones anteriores y crear las nuevas
        self.clear_all_book_sections()
        
        for sec_data in semantic_sections:
            self.add_book_section()
            last_section = self.book_sections[-1]
            
            # Usar título descriptivo del análisis semántico
            prefix = self.parent_prefix.get().strip()
            if prefix:
                last_section.title = f"{prefix} - {sec_data['title']}"
            else:
                last_section.title = sec_data["title"]
            
            # Añadir imágenes de previsualización para las páginas de esta sección
            for pg_num in sec_data.get("pages", []):
                img_path = page_image_map.get(pg_num)
                if img_path and os.path.exists(img_path):
                    last_section.add_image(img_path)
            
            # Generar PDF segmentado para esta sección
            pdf_segment_name = f"segment_{last_section.section_id}.pdf"
            pdf_segment_path = os.path.join(output_dir, pdf_segment_name)
            if self.document_processor.split_pdf(pdf_path, sec_data["pages"], pdf_segment_path):
                setattr(last_section, 'pdf_segment_path', pdf_segment_path)
                self.book_log(f"   📎 [{sec_data.get('start_page', '?')}-{sec_data.get('end_page', '?')}] {sec_data['title']}")
            
            self._update_book_section_info(last_section)
        
        self.book_log(f"\n✅ {len(semantic_sections)} secciones semánticas creadas con éxito.")
        self.book_log("   🚀 Ahora puedes pulsar 'Procesar Secciones' para generar flashcards.")
        self._save_current_book_session()
        messagebox.showinfo(
            "Segmentación Semántica Completa", 
            f"Se han creado {len(semantic_sections)} secciones agrupadas por tema.\n"
            f"Pulsa '🚀 Procesar Secciones' para generar flashcards."
        )

    def _fallback_to_standard_segmentation(self, path: str):
        """Fallback a segmentación estándar si la semántica falla."""
        self.book_segmentation_mode_var.set("Estándar (Páginas fijas)")
        self.process_book_to_sections()

    def _process_book_to_sections_text(self, path):
        """Fallback para procesar Word como texto."""
        pages_per_section = self.pages_per_section_var.get()
        overlap = self.pages_overlap_var.get()
        pages_content = self.document_processor.extract_text_from_docx(path)
        
        if not pages_content:
            messagebox.showerror("Error", "No se pudo extraer texto del Word.")
            return
            
        sections = self.document_processor.segment_pages(pages_content, pages_per_section, overlap)
        self.clear_all_book_sections()
        for sec_data in sections:
            self.add_book_section()
            last_section = self.book_sections[-1]
            last_section.title = sec_data["title"]
            # Convertimos la sección de imágenes en una con texto para este caso especial
            setattr(last_section, 'text', sec_data["content"])
            
            widgets = self.book_section_widgets.get(last_section.section_id)
            if widgets:
                widgets["title_var"].set(sec_data["title"])
                # Ocultar área de imágenes, mostrar texto (si quisiéramos complicarlo)
                # Por ahora, simplemente lo tratamos como ImageSection vacía pero con 'text'
        self.book_log(f"✅ Se han creado {len(sections)} secciones de texto desde Word.")
        self._save_current_book_session()

    def add_book_section(self):
        """Añade una nueva sección de libro (basada en imágenes)."""
        self.book_section_counter += 1
        self.hierarchy_counter += 1
        
        # Usamos ImageSection para tener soporte de imágenes
        section = ImageSection(self.book_section_counter)
        
        prefix = self.parent_prefix.get().strip()
        if prefix:
            section.title = f"{prefix} {self.hierarchy_counter}"
        else:
            section.title = f"Sección {self.book_section_counter}"
            
        self.book_sections.append(section)
        self._create_book_section_widget(section)
        self.book_log(f"📁 Sección {section.section_id} creada")

    def _create_book_section_widget(self, section: ImageSection):
        """Crea el widget visual para una sección de libro con soporte para imágenes."""
        section_frame = ttk.LabelFrame(self.book_sections_inner_frame, padding="10")
        section_frame.grid(row=len(self.book_sections)-1, column=0, sticky="ew", pady=5, padx=5)
        section_frame.columnconfigure(0, weight=1)
        
        # Header
        header_frame = ttk.Frame(section_frame)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(1, weight=1)
        
        title_var = tk.StringVar(value=section.title)
        title_label = ttk.Label(header_frame, text=section.title, font=("Arial", 11, "bold"))
        title_label.grid(row=0, column=0, sticky="w")
        
        title_entry = ttk.Entry(header_frame, textvariable=title_var, width=20)
        
        edit_btn = ttk.Button(header_frame, text="✏", width=3)
        edit_btn.grid(row=0, column=1, sticky="w", padx=5)
        
        def confirm_edit():
            new_title = title_var.get().strip() or f"Sección {section.section_id}"
            section.title = new_title
            title_label.config(text=new_title)
            title_entry.grid_forget()
            confirm_btn.grid_forget()
            title_label.grid(row=0, column=0, sticky="w")
            edit_btn.grid(row=0, column=1, sticky="w", padx=5)
            self.book_log(f"📝 Sección {section.section_id} renombrada a: {new_title}")
        
        confirm_btn = ttk.Button(header_frame, text="✓", width=3, command=confirm_edit)

        def start_edit():
            title_label.grid_forget()
            edit_btn.grid_forget()
            title_entry.grid(row=0, column=0, sticky="w")
            confirm_btn.grid(row=0, column=1, sticky="w", padx=5)
            title_entry.focus()
            
        edit_btn.config(command=start_edit)
        
        ttk.Button(header_frame, text="🗑", width=3, 
                  command=lambda: self.delete_book_section(section)).grid(row=0, column=3, sticky="e", padx=5)
        
        # Status indicators
        status_frame = ttk.Frame(section_frame)
        status_frame.grid(row=1, column=0, sticky="w", pady=(5, 0))
        
        status_labels = {}
        active_config = self.config_manager.get_active_set()
        active_types = active_config.get("active_types", {})
        
        for idx, (card_type, is_active) in enumerate(active_types.items()):
            if is_active:
                type_frame = ttk.Frame(status_frame)
                type_frame.grid(row=0, column=idx, padx=5)
                
                state_label = tk.Label(type_frame, text="⬜", font=("Segoe UI", 9), fg="gray")
                state_label.grid(row=0, column=0)
                
                count_label = ttk.Label(type_frame, text="", font=("Segoe UI", 8))
                count_label.grid(row=0, column=1)
                
                status_labels[card_type] = {
                    "state": state_label,
                    "count": count_label
                }

        # Área de thumbnails (para las páginas del PDF)
        thumbnails_frame = ttk.Frame(section_frame)
        thumbnails_frame.grid(row=2, column=0, sticky="ew", pady=5)
        
        info_label = ttk.Label(section_frame, text="0 páginas", foreground="gray")
        info_label.grid(row=3, column=0, sticky="w")
        
        # Botón procesar individual
        proc_btn = ttk.Button(section_frame, text="🚀 Procesar esta sección",
                             command=lambda: self.process_book_section_auto(section))
        proc_btn.grid(row=4, column=0, sticky="w", pady=(5,0))

        self.book_section_widgets[section.section_id] = {
            "frame": section_frame,
            "title_label": title_label,
            "title_var": title_var,
            "thumbnails_frame": thumbnails_frame,
            "info_label": info_label,
            "status_labels": status_labels
        }

    def _update_book_section_info(self, section: ImageSection):
        """Actualiza la información visual de una sección de libro."""
        widgets = self.book_section_widgets.get(section.section_id)
        if not widgets: return
        
        # Actualizar contador
        count = len(section.images)
        widgets["info_label"].config(text=f"📄 {count} páginas/imágenes")
        
        # Actualizar thumbnails (primeras 5 para no saturar)
        for child in widgets["thumbnails_frame"].winfo_children():
            child.destroy()
            
        for i, img_data in enumerate(section.images[:10]): # Mostrar hasta 10 thumbnails
            if "thumbnail_tk" not in img_data:
                from PIL import ImageTk
                img_data["thumbnail_tk"] = ImageTk.PhotoImage(img_data["thumbnail"])
            
            lbl = tk.Label(widgets["thumbnails_frame"], image=img_data["thumbnail_tk"])
            lbl.grid(row=0, column=i, padx=2)

    def delete_book_section(self, section):
        if section in self.book_sections:
            widgets = self.book_section_widgets.pop(section.section_id, None)
            if widgets:
                widgets["frame"].destroy()
            self.book_sections.remove(section)
            self.book_log(f"🗑 Sección {section.section_id} eliminada")

    def clear_all_book_sections(self):
        for widgets in self.book_section_widgets.values():
            widgets["frame"].destroy()
        self.book_sections = []
        self.book_section_widgets = {}
        self.book_section_counter = 0
        self.hierarchy_counter = 0
        self.book_log("🗑 Todas las secciones de libro eliminadas")

    def check_gemini_api_book(self):
        self.book_log("🔌 Verificando conexión con Gemini API...")
        try:
            if not self.flashcard_generator:
                from gemini_flashcard_generator import GeminiFlashcardGenerator
                self.flashcard_generator = GeminiFlashcardGenerator(log_callback=self.book_log)
            else:
                # Actualizar el callback por si acaso
                self.flashcard_generator.log_callback = self.book_log
            
            # Verificar las 4 APIs
            all_ok = True
            for i in range(1, 5):
                if not self.flashcard_generator.check_api_connection(i):
                    all_ok = False
            
            if all_ok:
                self.book_log("✅ Todas las APIs conectadas correctamente.")
                messagebox.showinfo("API OK", "Conexión con Gemini establecida correctamente (todas las APIs).")
            else:
                self.book_log("⚠️ Algunas APIs fallaron. Revisa el log y tu .env.")
                messagebox.showwarning("API Parcial", "Algunas APIs de Gemini no están respondiendo.")
        except Exception as e:
            self.book_log(f"❌ Error: {e}")
            messagebox.showerror("Error", str(e))

    def process_book_section_auto(self, section):
        # Implementación similar a texto pero con log de libros
        if not self._check_and_confirm_clear_pending_queue(mode="book"):
            return
        self.book_log(f"🚀 Iniciando procesamiento: {section.title}...")
        if self.flashcard_generator:
            self.flashcard_generator.reset_exhausted_keys()
        self._generate_cards_for_book_section(section)

    def _get_full_deck_path(self, section_title):
        """Construye la ruta completa del mazo: Bisabuelo::Abuelo::Sección."""
        bisabuelo = self.great_grandparent_deck.get().strip()
        abuelo = self.grandparent_deck.get().strip()
        
        parts = []
        if bisabuelo: parts.append(bisabuelo)
        if abuelo: parts.append(abuelo)
        if section_title: parts.append(section_title)
        
        return "::".join(parts) if parts else "Libros_Importados"

    def _get_deck_with_type_label(self, base_deck: str, card_type: str) -> str:
        """Construye la ruta del mazo agregando el nombre amigable del tipo de tarjeta."""
        type_labels = {
            "basic": "Basic",
            "multiple_choice": "Multiple Choice", 
            "cloze": "Cloze",
            "vocabulary": "Vocabulary",
            "level_1_cloze": "Nivel 1 - Cloze",
            "level_2_relations": "Nivel 2 - Relaciones",
            "level_3_application": "Nivel 3 - Aplicación",
            "level_4_analysis": "Nivel 4 - Análisis",
            "atomic_extraction": "Extracción Atómica",
            "high_performance_architect": "Alto Rendimiento",
            "exam_pareto": "Examen Pareto",
            "exam_faithful": "Examen Fiel"
        }
        label = type_labels.get(card_type, card_type)
        if base_deck.endswith(f"::{label}"):
            return base_deck
        return f"{base_deck}::{label}"

    def _generate_cards_for_book_section_logic(self, section: ImageSection):
        """Lógica de generación para una sección de libro (Síncrona)."""
        if not section.images and not hasattr(section, 'text'):
            self.book_log(f"⚠️ Sección {section.section_id} está vacía.")
            return

        deck_path = self._get_full_deck_path(section.title)
        widgets = self.book_section_widgets.get(section.section_id)
        try:
            active_set = self.config_manager.get_active_set()
            if not self.flashcard_generator:
                from gemini_flashcard_generator import GeminiFlashcardGenerator
                self.flashcard_generator = GeminiFlashcardGenerator(log_callback=self.book_log, config_set=active_set)
            else:
                self.flashcard_generator.log_callback = self.book_log
                self.flashcard_generator.update_config(active_set)
            
            content_to_process = ""
            multimodal_flashcards = None
            
            # Determinar el modo de extracción seleccionado
            selected_mode = self.extraction_mode_book.get()
            
            # [NUEVO] FLUJO MULTIMODAL DIRECTO (Para Extracción Cruda)
            # Evita la capa de extracción de texto y manda el PDF directamente a las APIs de flashcards
            if selected_mode == "Extracción Cruda (Fiel al documento)" and hasattr(section, 'pdf_segment_path') and os.path.exists(section.pdf_segment_path):
                self.book_log(f"🚀 INICIANDO GENERACIÓN MULTIMODAL DIRECTA PARA {section.title}...")
                multimodal_flashcards = self.flashcard_generator.generate_all_flashcards_multimodal(section.pdf_segment_path)
                
                # No extraemos texto extra para ahorrar tokens/tiempo, ya que es "Cruda"
                content_to_process = "[Extracción Multimodal Directa - Archivo crudo sin OCR intermedio]"
            
            else:
                # FLUJO ESTÁNDAR (Extraer texto -> Generar desde texto)
                extraction_mode = 2 if selected_mode != "Extracción Cruda (Fiel al documento)" else 1
                
                # Caso A: Tenemos fragmento de PDF
                if hasattr(section, 'pdf_segment_path') and os.path.exists(section.pdf_segment_path):
                    self.book_log(f"📄 Procesando PDF con Gemini para {section.title}...")
                    content_to_process = self.flashcard_generator.extract_text_from_pdf_file(section.pdf_segment_path, extraction_mode=extraction_mode)
                
                # Caso B: Tenemos imágenes (Fallback)
                if not content_to_process and section.images:
                    self.book_log(f"📷 Extrayendo texto con Vision OCR (Imágenes) para {section.title}...")
                    image_paths = [img["path"] for img in section.images]
                    content_to_process = self.flashcard_generator.extract_text_from_images(image_paths)
                
                # Caso C: Tenemos texto (Word fallback)
                if not content_to_process and hasattr(section, 'text'):
                    content_to_process = section.text
            
            if not content_to_process and not multimodal_flashcards:
                self.book_log(f"❌ No se pudo obtener contenido para {section.title}")
                return

            # [NUEVO] Determinar carpeta de guardado técnica para 'libros' respetando jerarquía
            bisabuelo = self.great_grandparent_deck.get().strip()
            grandparent = self.grandparent_deck.get().strip()
            
            book_full_path = self.book_path_var.get().strip()
            book_filename = "Libro_General"
            if book_full_path:
                book_filename = os.path.splitext(os.path.basename(book_full_path))[0]
                book_filename = "".join(x for x in book_filename if x.isalnum() or x in "._- ").strip()
            
            # Construir la ruta base: MASTER_FOLDER / libros / bisabuelo / abuelo / book_filename
            path_parts = [MASTER_FOLDER, "libros"]
            if bisabuelo:
                path_parts.append(bisabuelo)
            if grandparent:
                path_parts.append(grandparent)
            path_parts.append(book_filename)
            
            libros_root = os.path.join(*path_parts)
            os.makedirs(libros_root, exist_ok=True)

            # Apuntes expertos (Solo si se seleccionó "Estructuración Completa")
            if selected_mode == "Estructuración Completa":
                self.book_log(f"✨ Optimizando apuntes expertos para {section.title}...")
                content_to_process = self.flashcard_generator.structure_content_expert(content_to_process)

            # [NUEVO] Guardar Apuntes Expertos en subcarpeta
            expert_notes_dir = os.path.join(libros_root, "expert_notes")
            os.makedirs(expert_notes_dir, exist_ok=True)
            safe_section_title = "".join(c for c in section.title if c.isalnum() or c in " -_").strip()
            expert_save_path = os.path.join(expert_notes_dir, f"{safe_section_title}_Expert_Notes.md")
            try:
                with open(expert_save_path, 'w', encoding='utf-8') as f:
                    f.write(content_to_process)
                self.book_log(f"   💾 Apuntes guardados en: {os.path.relpath(expert_notes_dir, MASTER_FOLDER)}")
            except Exception as e:
                self.book_log(f"   ⚠️ Error guardando apuntes: {e}")

            # Generación de tarjetas (Selecciona flujo multimodal o estándar)
            if multimodal_flashcards:
                flashcards = multimodal_flashcards
            else:
                flashcards = self.flashcard_generator.generate_all_flashcards_parallel(
                    content_to_process
                )
            
            count = 0
            for card_type, result in flashcards.items():
                if result.get("success"):
                    raw_content = result.get("content", "")
                    
                    # 1. Convertir a TSV (FORMATO ANKI)
                    tsv_content = self.converter.convert(raw_content, card_type)
                    if not tsv_content:
                        self.book_log(f"   ⚠️ Error convirtiendo {card_type} a TSV")
                        continue
                        
                    # 2. Parsear a lista de flashcards para el manager de Anki
                    parsed_cards = self.flashcard_generator._parse_tsv_to_flashcards(tsv_content)
                    if not parsed_cards:
                        self.book_log(f"   ⚠️ No se pudieron extraer tarjetas de {card_type}")
                        continue
                    
                    # 4. Importar a Anki con jerarquía completa y nombres legibles
                    type_labels = {
                        "basic": "Basic",
                        "multiple_choice": "Multiple Choice", 
                        "cloze": "Cloze",
                        "vocabulary": "Vocabulary",
                        "level_1_cloze": "Nivel 1 - Cloze",
                        "level_2_relations": "Nivel 2 - Relaciones",
                        "level_3_application": "Nivel 3 - Aplicación",
                        "level_4_analysis": "Nivel 4 - Análisis",
                        "atomic_extraction": "Extracción Atómica",
                        "high_performance_architect": "Alto Rendimiento",
                        "exam_pareto": "Examen Pareto",
                        "exam_faithful": "Examen Fiel"
                    }
                    
                    label = type_labels.get(card_type, card_type)
                    
                    # 3. Guardar flashcards TSV en carpeta libros, separadas por tipo de tarjeta (Nombre legible)
                    flashcard_save_dir = os.path.join(libros_root, "flashcards", label)
                    os.makedirs(flashcard_save_dir, exist_ok=True)
                    fc_save_path = os.path.join(flashcard_save_dir, f"{safe_section_title}_{card_type}.txt")
                    try:
                        with open(fc_save_path, 'w', encoding='utf-8') as f:
                            f.write(tsv_content)
                    except: pass

                    # 4. Sincronizar con Anki usando la misma jerarquía
                    base_deck = self._get_full_deck_path(section.title)
                    deck_path = f"{base_deck}::{label}"
                    
                    self.pending_flashcard_imports.append({
                        "deck_name": deck_path,
                        "card_type": card_type,
                        "flashcards": parsed_cards
                    })
                    success = True
                    count_imported = len(parsed_cards)
                    
                    if success:
                        count += count_imported
                        if widgets and card_type in widgets["status_labels"]:
                            self.root.after(0, lambda t=card_type: widgets["status_labels"][t]["state"].config(text="✅", foreground="green"))
                    else:
                        self.book_log(f"   ⚠️ Error importando {card_type}: {msg}")
                else:
                    err_msg = result.get("error", "Error desconocido")
                    self.book_log(f"   ❌ Error al generar tipo '{card_type}': {err_msg}")

            self.book_log(f"✅ Sección {section.title} lista: {count} flashcards importadas.")
        except Exception as e:
            self.book_log(f"❌ Error en {section.title}: {e}")

    def _generate_cards_for_book_section(self, section: ImageSection):
        """Wrapper asíncrono para procesar una sección individual."""
        def run_single():
            self._generate_cards_for_book_section_logic(section)
            self._save_pending_queue()
            self._update_pending_button()
        threading.Thread(target=run_single, daemon=True).start()

    def process_all_book_sections(self):
        """Procesa todas las secciones del libro de forma secuencial."""
        if not self.book_sections:
            messagebox.showwarning("Sin secciones", "No hay secciones de libro para procesar.")
            return
        if not self._check_and_confirm_clear_pending_queue(mode="book"):
            return
        if self.flashcard_generator:
            self.flashcard_generator.reset_exhausted_keys()
            
        def run_all_sequentially():
            self.book_log("📋 Iniciando procesamiento SECUENCIAL de todo el libro...")
            total = len(self.book_sections)
            for i, section in enumerate(self.book_sections, 1):
                self.book_log(f"📦 [{i}/{total}] Procesando: {section.title}")
                self._generate_cards_for_book_section_logic(section)
                if i < total:
                    self.book_log("⌛ Esperando 10 segundos entre secciones para estabilidad...")
                    time.sleep(10)
            self.book_log("✅ LIBRO COMPLETO PROCESADO.")
            self._save_pending_queue()
            self._update_pending_button()

        threading.Thread(target=run_all_sequentially, daemon=True).start()

    def show_normal_mode(self):
        self._hide_all_frames()
        self.normal_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "normal"

    def show_automatic_images_mode(self):
        self._hide_all_frames()
        self.automatic_images_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "automatic_images"
        self.refresh_all_section_indicators()

    def show_automatic_text_mode(self):
        self._hide_all_frames()
        self.automatic_text_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "automatic_text"
        self.refresh_all_section_indicators()

    def show_automatic_videos_mode(self):
        self._hide_all_frames()
        self.automatic_videos_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "automatic_videos"
        self.refresh_all_section_indicators()

    def show_automatic_books_mode(self):
        self._hide_all_frames()
        self.automatic_books_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "automatic_books"
        self.refresh_all_section_indicators()

    def show_automatic_audio_mode(self):
        self._hide_all_frames()
        self.automatic_audio_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "automatic_audio"
        self.refresh_all_section_indicators()

    def _hide_all_frames(self):
        if self.normal_frame: self.normal_frame.grid_forget()
        if self.automatic_images_frame: self.automatic_images_frame.grid_forget()
        if self.automatic_text_frame: self.automatic_text_frame.grid_forget()
        if self.automatic_videos_frame: self.automatic_videos_frame.grid_forget()
        if self.automatic_books_frame: self.automatic_books_frame.grid_forget()
        if hasattr(self, 'automatic_audio_frame') and self.automatic_audio_frame: 
            self.automatic_audio_frame.grid_forget()
    
    def setup_automatic_audio_mode(self):
        """Configura la vista del modo automático para audios."""
        self.automatic_audio_frame = ttk.Frame(self.root, padding="10")
        self.automatic_audio_frame.columnconfigure(0, weight=1)
        self.automatic_audio_frame.rowconfigure(3, weight=1)
        
        # Header con botón de retroceso
        header_frame = ttk.Frame(self.automatic_audio_frame)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)
        
        back_btn = ttk.Button(header_frame, text="← Volver", command=self.show_normal_mode)
        back_btn.grid(row=0, column=0, sticky="w")
        
        title_label = ttk.Label(header_frame, text="🎧 Modo Automático - Procesamiento de Audios",
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=1, sticky="w", padx=20)
        
        # Frame de Jerarquía
        hierarchy_frame = self._create_hierarchy_config_frame(self.automatic_audio_frame)
        hierarchy_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # Frame de configuración y carga de audio
        config_frame = ttk.LabelFrame(self.automatic_audio_frame, text="⚙️ Configuración y Audio", padding="20")
        config_frame.grid(row=2, column=0, sticky="ew", pady=(10, 20), padx=5)
        config_frame.columnconfigure(1, weight=1)
        
        # Duración de segmento
        ttk.Label(config_frame, text="Duración de segmento (min):").grid(row=0, column=0, sticky="w", pady=5)
        self.audio_segment_duration_var = tk.DoubleVar(value=5.0)
        segment_spinbox = ttk.Spinbox(config_frame, from_=0.1, to=999.0, increment=0.5, 
                                      textvariable=self.audio_segment_duration_var, width=10)
        segment_spinbox.grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(config_frame, text="minutos").grid(row=0, column=2, sticky="w")
        
        # Overlap
        ttk.Label(config_frame, text="Overlap (seg):").grid(row=1, column=0, sticky="w", pady=5)
        self.audio_overlap_var = tk.IntVar(value=30)
        overlap_scale = ttk.Scale(config_frame, from_=0, to=120, variable=self.audio_overlap_var, 
                                 orient="horizontal")
        overlap_scale.grid(row=1, column=1, sticky="ew", padx=5)
        self.audio_overlap_label = ttk.Label(config_frame, text="30 seg")
        self.audio_overlap_label.grid(row=1, column=2, sticky="w")
        
        def update_audio_overlap_label(*args):
            self.audio_overlap_label.config(text=f"{self.audio_overlap_var.get()} seg")
        self.audio_overlap_var.trace_add("write", update_audio_overlap_label)
        
        # Modo de Segmentación (Estándar vs Semántico)
        ttk.Label(config_frame, text="Modo de Segmentación:").grid(row=2, column=0, sticky="w", pady=5)
        self.audio_segmentation_mode_var = tk.StringVar(value="standard")
        audio_mode_combo = ttk.Combobox(config_frame, textvariable=self.audio_segmentation_mode_var, 
                                   values=["standard", "semantic"], 
                                   state="readonly", width=30)
        def on_audio_mode_select(event):
            mode = self.audio_segmentation_mode_var.get()
            # Si es semántico, deshabilitar la duración y el overlap porque PyAnnote decide
            state = "disabled" if mode == "semantic" else "normal"
            segment_spinbox.config(state=state)
            overlap_scale.config(state=state)
            
        audio_mode_combo.bind("<<ComboboxSelected>>", on_audio_mode_select)
        audio_mode_combo.grid(row=2, column=1, sticky="w", padx=5)

        # Idioma
        ttk.Label(config_frame, text="Idioma del audio:").grid(row=3, column=0, sticky="w", pady=5)
        self.audio_language_var = tk.StringVar(value="es")
        language_combo = ttk.Combobox(config_frame, textvariable=self.audio_language_var, 
                                     values=["es", "en", "fr", "de", "it", "pt"], 
                                     state="readonly", width=10)
        language_combo.grid(row=3, column=1, sticky="w", padx=5)
        
        # Descarga de YouTube (Audio)
        ttk.Label(config_frame, text="🎧 Descargar de YouTube (URL):").grid(row=4, column=0, sticky="w", pady=5)
        self.audio_yt_url_entry = ttk.Entry(config_frame, textvariable=self.youtube_url_var, width=50)
        self.audio_yt_url_entry.grid(row=4, column=1, sticky="w", padx=5)
        
        self.audio_yt_download_btn = ttk.Button(config_frame, text="📥 Descargar", command=self.download_youtube_audio)
        self.audio_yt_download_btn.grid(row=4, column=2, sticky="w")
        
        # ----- Área de Drop de Audio -----
        drop_frame = tk.Frame(config_frame, bg="#e0f0ff", height=80, relief="groove", bd=2)
        drop_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(15, 15))
        drop_frame.grid_propagate(False)
        self.audio_drop_frame = drop_frame
        
        self.audio_drop_label = tk.Label(drop_frame, text="🎧 Arrastra un audio aquí o haz clic para buscar",
                             bg="#e0f0ff", fg="#004488", font=("Arial", 11, "bold"))
        self.audio_drop_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Bind click
        drop_frame.bind("<Button-1>", lambda e: self.upload_audio_for_processing())
        self.audio_drop_label.bind("<Button-1>", lambda e: self.upload_audio_for_processing())
        
        # Eventos Drag & Drop
        if hasattr(drop_frame, 'drop_target_register'):
            from tkinterdnd2 import DND_FILES
            drop_frame.drop_target_register(DND_FILES)
            drop_frame.dnd_bind('<<Drop>>', self._on_audio_drop)
            drop_frame.dnd_bind('<Enter>', lambda e: drop_frame.config(bg="#cce5ff"))
            drop_frame.dnd_bind('<Leave>', lambda e: drop_frame.config(bg="#e0f0ff"))
        
        # Botones de control y status
        buttons_frame = ttk.Frame(config_frame)
        buttons_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 5))
        
        # Separador visual
        ttk.Separator(config_frame, orient="horizontal").grid(row=5, column=0, columnspan=3, sticky="ew", pady=(30, 0))
        
        self.process_audio_btn = ttk.Button(buttons_frame, text="🚀 Procesar Audio",
                                            command=self.process_audio_complete, state="disabled")
        self.process_audio_btn.pack(side="left", padx=5)
        
        self.audio_info_label = ttk.Label(buttons_frame, text="", foreground="blue", font=("Arial", 10, "bold"))
        self.audio_info_label.pack(side="left", padx=10)

        self.change_audio_btn = ttk.Button(buttons_frame, text="🔄 Cambiar Audio",
                                            command=self.upload_audio_for_processing)
        
        # Contenedor principal con 2 columnas
        main_container = ttk.Frame(self.automatic_audio_frame)
        main_container.grid(row=3, column=0, sticky="nsew")
        main_container.columnconfigure(0, weight=2)
        main_container.columnconfigure(1, weight=1)
        main_container.rowconfigure(0, weight=1)
        
        # Panel izquierdo: Segmentos y Secciones
        left_panel = ttk.Frame(main_container)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(0, weight=0)
        left_panel.rowconfigure(1, weight=1)

        # Contenedor para segmentos de audio
        self.audio_segments_window = tk.Toplevel(self.root)
        self.audio_segments_window.title("Segmentos de Audio Procesados")
        self.audio_segments_window.geometry("800x600")
        self.audio_segments_window.withdraw()
        self.audio_segments_window.protocol("WM_DELETE_WINDOW", self.hide_audio_segments_window)
        
        self.audio_segments_container = ttk.Frame(self.audio_segments_window)
        self.audio_segments_container.pack(fill="both", expand=True, padx=10, pady=10)
        self.audio_segments_container.columnconfigure(0, weight=1)
        self.audio_segments_container.rowconfigure(0, weight=1)
        
        self.audio_segments_canvas = tk.Canvas(self.audio_segments_container, highlightthickness=0, height=300)
        segments_scrollbar = ttk.Scrollbar(self.audio_segments_container, orient="vertical", 
                                          command=self.audio_segments_canvas.yview)
        self.audio_segments_inner_frame = ttk.Frame(self.audio_segments_canvas)
        self.audio_segments_inner_frame.columnconfigure(0, weight=1)
        self.audio_segments_canvas.create_window((0, 0), window=self.audio_segments_inner_frame, anchor="nw", tags="inner")
        self.audio_segments_canvas.configure(yscrollcommand=segments_scrollbar.set)
        self.audio_segments_canvas.grid(row=0, column=0, sticky="nsew")
        segments_scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.audio_segments_inner_frame.bind("<Configure>", lambda e: self.audio_segments_canvas.configure(scrollregion=self.audio_segments_canvas.bbox("all")))
        self.audio_segments_canvas.bind("<Configure>", lambda e: self.audio_segments_canvas.itemconfig("inner", width=e.width))
        
        # Área de configuración de agrupación
        grouping_frame = ttk.LabelFrame(left_panel, text="📋 Configurar Agrupación", padding="10")
        grouping_frame.grid(row=0, column=0, sticky="ew", pady=5)
        grouping_frame.columnconfigure(1, weight=1)
        
        ttk.Label(grouping_frame, text="Transcripciones por sección:").grid(row=0, column=0, sticky="w", padx=5)
        self.audio_segments_per_section_var = tk.IntVar(value=2)
        segments_spinbox = ttk.Spinbox(grouping_frame, from_=1, to=10, 
                                       textvariable=self.audio_segments_per_section_var, width=10)
        segments_spinbox.grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(grouping_frame, text="Modo Procesamiento:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        audio_modes = ["Transcripción Estándar", "Generación Directa (Multimodal)"]
        mode_cb = ttk.Combobox(grouping_frame, textvariable=self.extraction_mode_audio, 
                              values=audio_modes, state="readonly", width=25)
        mode_cb.grid(row=1, column=1, columnspan=2, sticky="w", padx=5)
        
        self.create_audio_sections_btn = ttk.Button(grouping_frame, text="✨ Crear Secciones",
                                                   command=self.create_audio_sections_from_segments,
                                                   state="disabled")
        self.create_audio_sections_btn.grid(row=0, column=2, padx=5)
        
        self.view_audio_segments_btn = ttk.Button(grouping_frame, text="👁️ Ver Segmentos Procesados",
                                                  command=self.show_audio_segments_window,
                                                  state="disabled")
        self.view_audio_segments_btn.grid(row=2, column=0, columnspan=3, pady=(10, 0), sticky="ew")

        # Área de secciones creadas
        sections_frame = ttk.LabelFrame(left_panel, text="📚 Secciones Creadas", padding="5")
        sections_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        sections_frame.columnconfigure(0, weight=1)
        sections_frame.rowconfigure(0, weight=1)
        
        self.audio_sections_canvas = tk.Canvas(sections_frame, highlightthickness=0)
        sections_scrollbar = ttk.Scrollbar(sections_frame, orient="vertical", 
                                          command=self.audio_sections_canvas.yview)
        self.audio_sections_inner_frame = ttk.Frame(self.audio_sections_canvas)
        self.audio_sections_inner_frame.columnconfigure(0, weight=1)
        self.audio_sections_canvas.create_window((0, 0), window=self.audio_sections_inner_frame, anchor="nw", tags="inner")
        self.audio_sections_canvas.configure(yscrollcommand=sections_scrollbar.set)
        self.audio_sections_canvas.grid(row=0, column=0, sticky="nsew")
        sections_scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.audio_sections_inner_frame.bind("<Configure>", lambda e: self.audio_sections_canvas.configure(scrollregion=self.audio_sections_canvas.bbox("all")))
        self.audio_sections_canvas.bind("<Configure>", lambda e: self.audio_sections_canvas.itemconfig("inner", width=e.width))
        
        # Panel derecho: Logs
        right_panel = ttk.LabelFrame(main_container, text="📋 Logs de Audio", padding="5")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)        
        
        self.audio_logs_text = tk.Text(right_panel, width=40, wrap="word")
        self.audio_logs_text.grid(row=0, column=0, sticky="nsew")
        
        audio_logs_scrollbar = ttk.Scrollbar(right_panel, orient="vertical", command=self.audio_logs_text.yview)
        audio_logs_scrollbar.grid(row=0, column=1, sticky="ns")
        self.audio_logs_text.config(yscrollcommand=audio_logs_scrollbar.set)
        
        # Panel inferior: Botones de acción
        bottom_frame = ttk.Frame(self.automatic_audio_frame)
        bottom_frame.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        
        self.process_audio_sections_btn = ttk.Button(bottom_frame, text="🚀 Procesar Secciones",
                                                    command=self.process_audio_sections,
                                                    state="disabled")
        self.process_audio_sections_btn.pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="🧠 Filtrar Interferencia (IA)", command=self.open_deduplication_window).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="🎓 Rúbrica Pedagógica (IA)", command=self.open_evaluation_window).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="✅ Ejecutar Sincronización", command=self.execute_deduplicated_import).pack(side="left", padx=5)
        
        self.clear_audio_btn = ttk.Button(bottom_frame, text="🗑 Limpiar Todo", command=self.clear_audio_mode)
        self.clear_audio_btn.pack(side="left", padx=5)
        
        recover_btn = ttk.Button(bottom_frame, text="📂 Recuperar Sesión", command=self.show_recover_audio_session_dialog)
        recover_btn.pack(side="left", padx=5)
        
        self.pending_audio_btn = ttk.Button(bottom_frame, text="📋 Importar Pendientes", command=self.import_pending_flashcards)
        self.pending_audio_btn.pack(side="left", padx=5)
        
        config_btn = ttk.Button(bottom_frame, text="⚙️ Configuración", command=self.show_config_dialog)
        config_btn.pack(side="left", padx=5)
        
        self.audio_set_label = ttk.Label(bottom_frame, text=f"Set: {self.config_manager.active_set_name}", font=("Segoe UI", 9), foreground="blue")
        self.audio_set_label.pack(side="right", padx=10)

    def show_audio_segments_window(self):
        """Abre la ventana emergente con los segmentos de audio procesados."""
        if self.audio_segments_window:
            self.audio_segments_window.deiconify()
            self.audio_segments_window.lift()
            self.root.update_idletasks()

    def hide_audio_segments_window(self):
        """Oculta la ventana de segmentos de audio sin perder los datos."""
        if self.audio_segments_window:
            self.audio_segments_window.withdraw()

    def setup_automatic_videos_mode(self):
        """Configura la vista del modo automático para videos."""
        self.automatic_videos_frame = ttk.Frame(self.root, padding="10")
        self.automatic_videos_frame.columnconfigure(0, weight=1)
        self.automatic_videos_frame.rowconfigure(3, weight=1)
        
        # Header con botón de retroceso
        header_frame = ttk.Frame(self.automatic_videos_frame)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)
        
        back_btn = ttk.Button(header_frame, text="← Volver", command=self.show_normal_mode)
        back_btn.grid(row=0, column=0, sticky="w")
        
        title_label = ttk.Label(header_frame, text="🎬 Modo Automático - Procesamiento de Videos",
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=1, sticky="w", padx=20)
        
        # Frame de Jerarquía
        hierarchy_frame = self._create_hierarchy_config_frame(self.automatic_videos_frame)
        hierarchy_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # Frame de configuración y carga de video
        config_frame = ttk.LabelFrame(self.automatic_videos_frame, text="⚙️ Configuración y Video", padding="20")
        config_frame.grid(row=2, column=0, sticky="ew", pady=(10, 20), padx=5)
        config_frame.columnconfigure(1, weight=1)
        
        # --- NUEVO: Modo de Segmentación ---
        ttk.Label(config_frame, text="Modo de Segmentación:").grid(row=0, column=0, sticky="w", pady=5)
        self.video_segmentation_mode_var = tk.StringVar(value="standard")
        video_mode_combo = ttk.Combobox(config_frame, textvariable=self.video_segmentation_mode_var,
                                        values=["standard", "semantic"], state="readonly", width=15)
        video_mode_combo.grid(row=0, column=1, sticky="w", padx=5)

        # Duración de segmento
        ttk.Label(config_frame, text="Duración de segmento (min):").grid(row=1, column=0, sticky="w", pady=5)
        self.segment_duration_var = tk.DoubleVar(value=3.0)
        segment_spinbox = ttk.Spinbox(config_frame, from_=0.1, to=999.0, increment=0.5, 
                                      textvariable=self.segment_duration_var, width=10)
        segment_spinbox.grid(row=1, column=1, sticky="w", padx=5)
        ttk.Label(config_frame, text="minutos").grid(row=1, column=2, sticky="w")
        
        # Overlap
        ttk.Label(config_frame, text="Overlap (seg):").grid(row=2, column=0, sticky="w", pady=5)
        self.overlap_var = tk.IntVar(value=30)
        overlap_scale = ttk.Scale(config_frame, from_=0, to=120, variable=self.overlap_var, 
                                 orient="horizontal")
        overlap_scale.grid(row=2, column=1, sticky="ew", padx=5)
        self.overlap_label = ttk.Label(config_frame, text="30 seg")
        self.overlap_label.grid(row=2, column=2, sticky="w")
        
        def update_overlap_label(*args):
            self.overlap_label.config(text=f"{self.overlap_var.get()} seg")
        self.overlap_var.trace_add("write", update_overlap_label)

        def on_video_mode_change(*args):
            state = "normal" if self.video_segmentation_mode_var.get() == "standard" else "disabled"
            segment_spinbox.config(state=state)
            overlap_scale.config(state=state)
            
        self.video_segmentation_mode_var.trace_add("write", on_video_mode_change)
        
        # Calidad de transcripción (Modelo de Whisper)
        ttk.Label(config_frame, text="Calidad de Transcripción (Modelo):").grid(row=3, column=0, sticky="w", pady=5)
        self.whisper_model_var = tk.StringVar(value="base")
        model_combo = ttk.Combobox(config_frame, textvariable=self.whisper_model_var, 
                                   values=["base (rápido, ~1GB RAM)", "small (~2GB RAM)", "medium (Preciso, ~5GB RAM)", "large (Lento, ~10GB RAM)"], 
                                   state="readonly", width=30)
        # Extraer solo el nombre base "base", "small", "medium", "large" al seleccionar
        def on_model_select(event):
            selected = self.whisper_model_var.get()
            model_name = selected.split(" ")[0]
            self.whisper_model_var.set(model_name)
        model_combo.bind("<<ComboboxSelected>>", on_model_select)
        model_combo.grid(row=3, column=1, sticky="w", padx=5)

        # Idioma
        ttk.Label(config_frame, text="Idioma del video:").grid(row=4, column=0, sticky="w", pady=5)
        self.language_var = tk.StringVar(value="es")
        language_combo = ttk.Combobox(config_frame, textvariable=self.language_var, 
                                     values=["es", "en", "fr", "de", "it", "pt"], 
                                     state="readonly", width=10)
        language_combo.grid(row=4, column=1, sticky="w", padx=5)
        
        # --- NUEVO: Cookies del navegador ---
        self.use_browser_cookies_var = tk.BooleanVar(value=False)
        cookies_cb = ttk.Checkbutton(config_frame, text="🍪 Usar Cookies del Navegador (Chrome/Firefox)", 
                                    variable=self.use_browser_cookies_var)
        cookies_cb.grid(row=4, column=2, sticky="w", padx=5)
        
        # --- NUEVO: Descarga de YouTube ---
        ttk.Label(config_frame, text="📺 Descargar de YouTube (URL):").grid(row=5, column=0, sticky="w", pady=5)
        self.yt_url_entry = ttk.Entry(config_frame, textvariable=self.youtube_url_var, width=50)
        self.yt_url_entry.grid(row=5, column=1, sticky="w", padx=5)
        
        self.yt_download_btn = ttk.Button(config_frame, text="📥 Descargar", command=self.download_youtube_video)
        self.yt_download_btn.grid(row=5, column=2, sticky="w")
        
        # Botones de control y status
        buttons_frame = ttk.Frame(config_frame)
        buttons_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, 5))
        
        # Separador visual
        ttk.Separator(config_frame, orient="horizontal").grid(row=6, column=0, columnspan=3, sticky="ew", pady=(30, 0))
        
        # ----- Área de Drop de Video -----
        drop_frame = tk.Frame(config_frame, bg="#e0e0e0", height=80, relief="groove", bd=2)
        drop_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(15, 15))
        drop_frame.grid_propagate(False)
        self.video_drop_frame = drop_frame # Reference
        
        self.video_drop_label = tk.Label(drop_frame, text="🎥 Arrastra un video aquí o haz clic para buscar",
                             bg="#e0e0e0", fg="#444444", font=("Arial", 11, "bold"))
        self.video_drop_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Bind click
        drop_frame.bind("<Button-1>", lambda e: self.upload_video_for_processing())
        self.video_drop_label.bind("<Button-1>", lambda e: self.upload_video_for_processing())
        
        # Eventos Drag & Drop si la librería está disponible
        if hasattr(drop_frame, 'drop_target_register'):
            from tkinterdnd2 import DND_FILES
            drop_frame.drop_target_register(DND_FILES)
            drop_frame.dnd_bind('<<Drop>>', self._on_video_drop)
            drop_frame.dnd_bind('<Enter>', lambda e: drop_frame.config(bg="#c0c0c0"))
            drop_frame.dnd_bind('<Leave>', lambda e: drop_frame.config(bg="#e0e0e0"))
        
        # (El botón Cargar Video original se oculta ya que el drop hace lo mismo,
        # pero mantenemos la referencia si otro método lo requiere, o dejamos Procesar)
        
        self.process_video_btn = ttk.Button(buttons_frame, text="🚀 Procesar Video",
                                            command=self.process_video_complete, state="disabled")
        self.process_video_btn.pack(side="left", padx=5)
        
        self.video_info_label = ttk.Label(buttons_frame, text="", foreground="blue", font=("Arial", 10, "bold"))
        self.video_info_label.pack(side="left", padx=10)

        self.change_video_btn = ttk.Button(buttons_frame, text="🔄 Cambiar Video",
                                            command=self.upload_video_for_processing)
        # Se empaca dinámicamente cuando hay un video cargado
        
        # Contenedor principal con 2 columnas
        main_container = ttk.Frame(self.automatic_videos_frame)
        main_container.grid(row=3, column=0, sticky="nsew")
        main_container.columnconfigure(0, weight=2)
        main_container.columnconfigure(1, weight=1)
        main_container.rowconfigure(0, weight=1)
        
        # Panel izquierdo: Segmentos y Secciones
        left_panel = ttk.Frame(main_container)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(0, weight=0)  # grouping_frame fijo
        left_panel.rowconfigure(1, weight=1)  # sections_frame expande

        # Contenedor para la ventana emergente de segmentos
        self.segments_window = tk.Toplevel(self.root)
        self.segments_window.title("Segmentos Procesados")
        self.segments_window.geometry("800x600")
        self.segments_window.withdraw() # Ocultar inicialmente
        self.segments_window.protocol("WM_DELETE_WINDOW", self.hide_segments_window)
        
        self.segments_container = ttk.Frame(self.segments_window)
        self.segments_container.pack(fill="both", expand=True, padx=10, pady=10)
        self.segments_container.columnconfigure(0, weight=1)
        self.segments_container.rowconfigure(0, weight=1)
        
        # Canvas con scrollbar para segmentos
        self.segments_canvas = tk.Canvas(self.segments_container, highlightthickness=0, height=300)
        segments_scrollbar = ttk.Scrollbar(self.segments_container, orient="vertical", 
                                          command=self.segments_canvas.yview)
        
        self.segments_inner_frame = ttk.Frame(self.segments_canvas)
        self.segments_inner_frame.columnconfigure(0, weight=1)
        
        self.segments_canvas.create_window((0, 0), window=self.segments_inner_frame, 
                                          anchor="nw", tags="inner")
        self.segments_canvas.configure(yscrollcommand=segments_scrollbar.set)
        
        self.segments_canvas.grid(row=0, column=0, sticky="nsew")
        segments_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Bind para actualizar scroll region
        self.segments_inner_frame.bind("<Configure>", 
            lambda e: self.segments_canvas.configure(scrollregion=self.segments_canvas.bbox("all")))
        self.segments_canvas.bind("<Configure>", 
            lambda e: self.segments_canvas.itemconfig("inner", width=e.width))
        
        # Área de configuración de agrupación
        grouping_frame = ttk.LabelFrame(left_panel, text="📋 Configurar Agrupación", padding="10")
        grouping_frame.grid(row=0, column=0, sticky="ew", pady=5)
        grouping_frame.columnconfigure(1, weight=1)
        
        ttk.Label(grouping_frame, text="Transcripciones por sección:").grid(row=0, column=0, sticky="w", padx=5)
        self.segments_per_section_var = tk.IntVar(value=2)
        segments_spinbox = ttk.Spinbox(grouping_frame, from_=1, to=10, 
                                       textvariable=self.segments_per_section_var, width=10)
        segments_spinbox.grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(grouping_frame, text="Modo Procesamiento:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        video_modes = ["Transcripción Estándar", "Generación Directa (Multimodal)"]
        mode_cb = ttk.Combobox(grouping_frame, textvariable=self.extraction_mode_video, 
                              values=video_modes, state="readonly", width=25)
        mode_cb.grid(row=1, column=1, columnspan=2, sticky="w", padx=5)
        
        self.create_sections_btn = ttk.Button(grouping_frame, text="✨ Crear Secciones",
                                             command=self.create_video_sections_from_segments,
                                             state="disabled")
        self.create_sections_btn.grid(row=0, column=2, padx=5)
        
        self.view_segments_btn = ttk.Button(grouping_frame, text="👁️ Ver Segmentos Procesados",
                                            command=self.show_segments_window,
                                            state="disabled")
        self.view_segments_btn.grid(row=2, column=0, columnspan=3, pady=(10, 0), sticky="ew")
        
        # --- Fuente de Consulta Completa ---
        source_frame = ttk.LabelFrame(grouping_frame, text="📋 Fuente de Consulta", padding="5")
        source_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        source_frame.columnconfigure(1, weight=1)
        
        source_cb = ttk.Checkbutton(source_frame, text="Usar Fuente Completa (mejora contexto y coherencia)",
                                     variable=self.use_source_context_var,
                                     command=self._toggle_source_duration_visibility)
        source_cb.grid(row=0, column=0, columnspan=3, sticky="w", padx=5)
        
        self.source_duration_label = ttk.Label(source_frame, text="Duración segmento fuente (min):")
        self.source_duration_spinbox = ttk.Spinbox(source_frame, from_=1.0, to=30.0, increment=0.5,
                                                    textvariable=self.source_segment_duration_var, width=8)
        self.source_duration_info = ttk.Label(source_frame, text="⚠️ Genera transcripción previa del material completo",
                                               foreground="orange", font=("Segoe UI", 8))
        
        # Inicialmente ocultos
        self._toggle_source_duration_visibility()

        # Área de secciones creadas
        sections_frame = ttk.LabelFrame(left_panel, text="📚 Secciones Creadas", padding="5")
        sections_frame.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        sections_frame.columnconfigure(0, weight=1)
        sections_frame.rowconfigure(0, weight=1)
        
        # Canvas con scrollbar para secciones
        self.video_sections_canvas = tk.Canvas(sections_frame, highlightthickness=0)
        sections_scrollbar = ttk.Scrollbar(sections_frame, orient="vertical", 
                                          command=self.video_sections_canvas.yview)
        
        self.video_sections_inner_frame = ttk.Frame(self.video_sections_canvas)
        self.video_sections_inner_frame.columnconfigure(0, weight=1)
        
        self.video_sections_canvas.create_window((0, 0), window=self.video_sections_inner_frame, 
                                                anchor="nw", tags="inner")
        self.video_sections_canvas.configure(yscrollcommand=sections_scrollbar.set)
        
        self.video_sections_canvas.grid(row=0, column=0, sticky="nsew")
        sections_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Bind para actualizar scroll region
        self.video_sections_inner_frame.bind("<Configure>", 
            lambda e: self.video_sections_canvas.configure(scrollregion=self.video_sections_canvas.bbox("all")))
        self.video_sections_canvas.bind("<Configure>", 
            lambda e: self.video_sections_canvas.itemconfig("inner", width=e.width))
        
        # Panel derecho: Logs
        right_panel = ttk.LabelFrame(main_container, text="📋 Logs de Videos", padding="5")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)
        
        self.video_logs_text = tk.Text(right_panel, width=40, wrap="word")
        self.video_logs_text.grid(row=0, column=0, sticky="nsew")
        
        video_logs_scrollbar = ttk.Scrollbar(right_panel, orient="vertical", 
                                            command=self.video_logs_text.yview)
        video_logs_scrollbar.grid(row=0, column=1, sticky="ns")
        self.video_logs_text.config(yscrollcommand=video_logs_scrollbar.set)
        
        # Panel inferior: Botones de acción
        bottom_frame = ttk.Frame(self.automatic_videos_frame)
        bottom_frame.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        
        self.process_sections_btn = ttk.Button(bottom_frame, text="🚀 Procesar Secciones",
                                              command=self.process_video_sections,
                                              state="disabled")
        self.process_sections_btn.pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="🧠 Filtrar Interferencia (IA)", command=self.open_deduplication_window).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="🎓 Rúbrica Pedagógica (IA)", command=self.open_evaluation_window).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="✅ Ejecutar Sincronización", command=self.execute_deduplicated_import).pack(side="left", padx=5)
        
        self.clear_video_btn = ttk.Button(bottom_frame, text="🗑 Limpiar Todo",
                                         command=self.clear_video_mode)
        self.clear_video_btn.pack(side="left", padx=5)
        
        # Botón de recuperación de sesiones
        recover_btn = ttk.Button(bottom_frame, text="📂 Recuperar Sesión",
                                 command=self.show_recover_video_session_dialog)
        recover_btn.pack(side="left", padx=5)
        
        # Botón de importar pendientes
        self.pending_video_btn = ttk.Button(bottom_frame, text="📋 Importar Pendientes",
                                      command=self.import_pending_flashcards)
        self.pending_video_btn.pack(side="left", padx=5)
        self._update_pending_button() # Llama al método general para actualizar contadores
        
        # Botón de configuración
        config_btn = ttk.Button(bottom_frame, text="⚙️ Configuración",
                               command=self.show_config_dialog)
        config_btn.pack(side="left", padx=5)
        
        # Label del set activo
        self.video_set_label = ttk.Label(bottom_frame, text=f"Set: {self.config_manager.active_set_name}",
                                         font=("Segoe UI", 9), foreground="blue")
        self.video_set_label.pack(side="right", padx=10)
    
    def show_segments_window(self):
        """Abre la ventana emergente con los segmentos procesados."""
        if self.segments_window:
            self.segments_window.deiconify()
            self.segments_window.lift()
            self.root.update_idletasks()

    def hide_segments_window(self):
        """Oculta la ventana de segmentos sin perder los datos."""
        if self.segments_window:
            self.segments_window.withdraw()

    def _on_sections_configure(self, event):
        """Actualiza el scroll region cuando cambia el contenido."""
        self.sections_canvas.configure(scrollregion=self.sections_canvas.bbox("all"))
    
    def _on_canvas_configure(self, event):
        """Ajusta el ancho del frame interno al canvas."""
        self.sections_canvas.itemconfig("inner", width=event.width)


    def add_section(self):
        """Añade una nueva sección de imágenes."""
        self.section_counter += 1
        self.hierarchy_counter += 1
        
        section = ImageSection(self.section_counter)
        
        # Asignar nombre automático con el prefijo padre si existe
        prefix = self.parent_prefix.get().strip()
        if prefix:
            section.title = f"{prefix} {self.hierarchy_counter}"
        else:
            section.title = f"Sección {self.section_counter}"
            
        self.sections.append(section)
        
        self._create_section_widget(section)
        self.auto_log(f"📁 Sección {section.section_id} creada")
    
    def _create_section_widget(self, section: ImageSection):
        """Crea el widget visual para una sección."""
        section_frame = ttk.LabelFrame(self.sections_inner_frame, padding="10")
        section_frame.grid(row=len(self.sections)-1, column=0, sticky="ew", pady=5, padx=5)
        section_frame.columnconfigure(0, weight=1)
        
        # Header de la sección con título editable
        header_frame = ttk.Frame(section_frame)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(1, weight=1)
        
        # Título (label por defecto, entry al editar)
        title_var = tk.StringVar(value=section.title)
        title_label = ttk.Label(header_frame, text=section.title, font=("Arial", 11, "bold"))
        title_label.grid(row=0, column=0, sticky="w")
        
        title_entry = ttk.Entry(header_frame, textvariable=title_var, width=20)
        
        # Botones de edición
        edit_btn = ttk.Button(header_frame, text="✏", width=3)
        edit_btn.grid(row=0, column=1, sticky="w", padx=5)
        
        confirm_btn = ttk.Button(header_frame, text="✓", width=3)

        def start_edit():
            title_label.grid_forget()
            edit_btn.grid_forget()
            title_entry.grid(row=0, column=0, sticky="w")
            confirm_btn.grid(row=0, column=1, sticky="w", padx=5)
            title_entry.focus()
        
        def confirm_edit():
            new_title = title_var.get().strip() or f"Sección {section.section_id}"
            section.title = new_title
            title_label.config(text=new_title)
            title_entry.grid_forget()
            confirm_btn.grid_forget()
            title_label.grid(row=0, column=0, sticky="w")
            edit_btn.grid(row=0, column=1, sticky="w", padx=5)
            self.auto_log(f"📝 Sección {section.section_id} renombrada a: {new_title}")
        
        edit_btn.config(command=start_edit)
        confirm_btn.config(command=confirm_edit)
        title_entry.bind("<Return>", lambda e: confirm_edit())
        
        # Botón pegar desde portapapeles
        paste_btn = ttk.Button(header_frame, text="📋 Pegar", width=8,
                               command=lambda: self.paste_from_clipboard(section))
        paste_btn.grid(row=0, column=2, sticky="w", padx=5)
        
        # Botón eliminar sección
        delete_btn = ttk.Button(header_frame, text="🗑 Eliminar", 
                               command=lambda: self.delete_section(section))
        delete_btn.grid(row=0, column=3, sticky="e", padx=5)
        
        # Frame para indicadores de estado de los 4 tipos de flashcards
        status_frame = ttk.Frame(section_frame)
        status_frame.grid(row=1, column=0, sticky="w", pady=(5, 0))
        
        # Crear los indicadores según el set activo
        status_labels = {}
        
        # Obtener tipos activos del config manager
        active_config = self.config_manager.get_active_set()
        active_types = active_config.get("active_types", {})
        
        # Iconos para cada tipo
        type_icons = {
            "basic": ("📝", "Basic"),
            "multiple_choice": ("🔘", "Multiple"),
            "cloze": ("🔲", "Cloze"),
            "vocabulary": ("🔤", "Vocab"),
            "level_1_cloze": ("1️⃣", "L1-Cloze"),
            "level_2_relations": ("2️⃣", "L2-Rel"),
            "level_3_application": ("3️⃣", "L3-App"),
            "level_4_analysis": ("4️⃣", "L4-Anal"),
            "atomic_extraction": ("⚛️", "Atomic")
        }
        
        # Filtrar solo los tipos activos
        card_types_icons = [
            (card_type, *type_icons.get(card_type, ("❓", card_type[:6])))
            for card_type, is_active in active_types.items() if is_active
        ]
        
        for idx, (card_type, icon, label) in enumerate(card_types_icons):
            type_frame = ttk.Frame(status_frame)
            type_frame.grid(row=0, column=idx, padx=(0, 15))
            
            # Icono del tipo
            icon_label = ttk.Label(type_frame, text=icon, font=("Segoe UI", 9))
            icon_label.grid(row=0, column=0)
            
            # Estado (⬜ inicial, ✅ éxito, ❌ fallo)
            state_label = tk.Label(type_frame, text="⬜", font=("Segoe UI", 9), fg="gray")
            state_label.grid(row=0, column=1, padx=2)
            
            # Contador (vacío inicialmente)
            count_label = ttk.Label(type_frame, text="", font=("Segoe UI", 8))
            count_label.grid(row=0, column=2)
            
            status_labels[card_type] = {
                "state": state_label,
                "count": count_label
            }
        
        # Área de drop para imágenes (se oculta al tener imágenes)
        drop_frame = tk.Frame(section_frame, bg="#e0e0e0", height=60, relief="groove", bd=2)
        drop_frame.grid(row=2, column=0, sticky="ew", pady=5)
        drop_frame.grid_propagate(False)
        
        drop_label = tk.Label(drop_frame, text="🖼 Arrastra imágenes aquí o haz clic",
                             bg="#e0e0e0", fg="#666666", font=("Arial", 10))
        drop_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Bind click para seleccionar archivos
        drop_frame.bind("<Button-1>", lambda e, s=section: self.browse_images(s))
        drop_label.bind("<Button-1>", lambda e, s=section: self.browse_images(s))
        
        # Botón compacto para añadir imágenes (oculto inicialmente)
        add_more_btn = ttk.Button(section_frame, text="➕ Añadir más imágenes", 
                                  command=lambda s=section: self.browse_images(s))

        # Frame para thumbnails
        thumbnails_frame = ttk.Frame(section_frame)
        thumbnails_frame.grid(row=3, column=0, sticky="ew")
        
        # Info de la sección
        info_label = ttk.Label(section_frame, text="0 imágenes", foreground="gray")
        info_label.grid(row=4, column=0, sticky="w", pady=(5, 0))
        
        # Guardar referencias
        self.section_widgets[section.section_id] = {
            "frame": section_frame,
            "title_label": title_label,
            "title_var": title_var,
            "drop_frame": drop_frame,
            "add_more_btn": add_more_btn,
            "thumbnails_frame": thumbnails_frame,
            "info_label": info_label,
            "status_labels": status_labels
        }
        
        # Configurar drag and drop (usando tkinterdnd2 si está disponible, sino solo click)
        self._setup_drop_bindings(drop_frame, section)
    
    def _setup_drop_bindings(self, drop_frame, section):
        """Configura los bindings para drag and drop desde el explorador de archivos."""
        # En Windows, tkinter soporta drag & drop nativamente
        # Necesitamos registrar el widget para recibir eventos de drop
        
        try:
            # Intentar usar tkinterdnd2 si está disponible
            from tkinterdnd2 import DND_FILES, TkinterDnD
            
            drop_frame.drop_target_register(DND_FILES)
            drop_frame.dnd_bind('<<Drop>>', lambda e, s=section: self._on_drop(e, s))
            drop_frame.dnd_bind('<<DragEnter>>', lambda e: drop_frame.config(bg="#c0e0c0"))
            drop_frame.dnd_bind('<<DragLeave>>', lambda e: drop_frame.config(bg="#e0e0e0"))
            
            self.auto_log("✅ Drag & drop habilitado (tkinterdnd2)")
            
        except ImportError:
            # Fallback: usar método alternativo con tkinter nativo
            # En Windows, podemos usar el protocolo WM_DROPFILES
            self.auto_log("⚠️ tkinterdnd2 no disponible, usando método alternativo")
            
            # Configurar el frame para aceptar drops
            drop_frame.bind("<Enter>", lambda e: drop_frame.config(bg="#c0e0c0"))
            drop_frame.bind("<Leave>", lambda e: drop_frame.config(bg="#e0e0e0"))
            
            # Nota: El drag & drop nativo de Windows requiere configuración adicional
            # Por ahora, el usuario puede usar el botón "Añadir Imágenes" o "Pegar"
    
    def _on_drop(self, event, section):
        """Maneja el evento de drop de archivos."""
        # Restaurar color del frame
        widgets = self.section_widgets.get(section.section_id)
        if widgets:
            widgets["drop_frame"].config(bg="#e0e0e0")
        
        # Obtener las rutas de los archivos
        files = self._parse_drop_files(event.data)
        
        if not files:
            self.auto_log("⚠️ No se detectaron archivos válidos")
            return
        
        # Filtrar solo imágenes
        image_files = [f for f in files if f.lower().endswith(self.SUPPORTED_FORMATS)]
        
        if not image_files:
            self.auto_log(f"⚠️ No se encontraron imágenes válidas (formatos soportados: {', '.join(self.SUPPORTED_FORMATS)})")
            messagebox.showwarning("Sin imágenes", 
                                  f"No se encontraron imágenes válidas.\n\nFormatos soportados: {', '.join(self.SUPPORTED_FORMATS)}")
            return
        
        # Añadir imágenes a la sección
        self.auto_log(f"📥 Añadiendo {len(image_files)} imagen(es) a {section.title}...")
        
        added = 0
        for file_path in image_files:
            result = section.add_image(file_path)
            if "error" in result:
                self.auto_log(f"   ❌ {result['error']}")
            else:
                added += 1
        
        if added > 0:
            self.auto_log(f"   ✅ {added} imagen(es) añadidas")
            self._update_section_info(section)
        else:
            self.auto_log(f"   ⚠️ No se pudieron añadir imágenes")
    
    def _parse_drop_files(self, data):
        """Parsea los datos del evento de drop para extraer rutas de archivos."""
        # El formato puede variar según el sistema
        # En Windows con tkinterdnd2, viene como string con rutas separadas
        
        if not data:
            return []
        
        # Convertir a string si es necesario
        data_str = str(data)
        
        # Limpiar y separar rutas
        # Puede venir como: "{C:/path/file1.png} {C:/path/file2.png}"
        # O como: "C:/path/file1.png C:/path/file2.png"
        
        files = []
        
        # Método 1: Rutas entre llaves
        if '{' in data_str:
            import re
            matches = re.findall(r'\{([^}]+)\}', data_str)
            files.extend(matches)
        
        # Método 2: Rutas separadas por espacios (cuidado con espacios en nombres)
        if not files:
            # Intentar split simple
            parts = data_str.split()
            for part in parts:
                part = part.strip('{}')
                if os.path.exists(part):
                    files.append(part)
        
        # Método 3: Una sola ruta
        if not files:
            data_clean = data_str.strip('{}').strip()
            if os.path.exists(data_clean):
                files.append(data_clean)
        
        return files
    
    def browse_images(self, section: ImageSection):
        """Abre diálogo para seleccionar imágenes."""
        filetypes = [
            ("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tiff *.ico"),
            ("Todos los archivos", "*.*")
        ]
        files = filedialog.askopenfilenames(title="Seleccionar imágenes", filetypes=filetypes)
        
        for file_path in files:
            self._add_image_to_section(section, file_path)
    
    def paste_from_clipboard(self, section: ImageSection):
        """Pega una imagen desde el portapapeles."""
        try:
            # Intentar obtener imagen del portapapeles
            from PIL import ImageGrab
            
            img = ImageGrab.grabclipboard()
            
            if img is None:
                self.auto_log("⚠️ No hay imagen en el portapapeles")
                messagebox.showwarning("Sin imagen", 
                                      "No hay ninguna imagen en el portapapeles.\n\n"
                                      "Haz una captura (Win+Shift+S) o copia una imagen primero.")
                return
            
            # Verificar que sea una imagen
            if not isinstance(img, Image.Image):
                self.auto_log("⚠️ El contenido del portapapeles no es una imagen")
                messagebox.showwarning("No es imagen", 
                                      "El contenido del portapapeles no es una imagen válida.")
                return
            
            # Guardar temporalmente la imagen
            temp_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_path = os.path.join(temp_dir, f"clipboard_{timestamp}.png")
            
            img.save(temp_path, "PNG")
            self.auto_log(f"📋 Imagen pegada desde portapapeles")
            
            # Añadir a la sección
            self._add_image_to_section(section, temp_path)
            
        except ImportError:
            self.auto_log("❌ PIL.ImageGrab no disponible")
            messagebox.showerror("Error", 
                               "La funcionalidad de portapapeles requiere PIL/Pillow.\n"
                               "Ejecuta: pip install pillow")
        except Exception as e:
            self.auto_log(f"❌ Error al pegar: {e}")
            messagebox.showerror("Error", f"No se pudo pegar la imagen:\n{str(e)}")
    
    def _add_image_to_section(self, section: ImageSection, file_path: str):
        """Añade una imagen a una sección."""
        result = section.add_image(file_path)
        
        if "error" in result:
            self.auto_log(f"❌ Error: {result['error']}")
            return
        
        # Log de éxito
        size_mb = result["size"] / (1024 * 1024)
        self.auto_log(f"✅ Imagen añadida a {section.title}:")
        self.auto_log(f"   📄 Nombre: {result['name']}")
        self.auto_log(f"   📐 Tamaño: {size_mb:.2f} MB")
        self.auto_log(f"   🎨 Formato: {result['format']}")
        self.auto_log(f"   📅 Fecha: {result['date']}")
        
        # Actualizar UI
        self._update_section_thumbnails(section)
        self._update_section_info(section)
    
    def _update_section_thumbnails(self, section: ImageSection):
        """Actualiza los thumbnails de una sección."""
        widgets = self.section_widgets.get(section.section_id)
        if not widgets:
            return
        
        thumbnails_frame = widgets["thumbnails_frame"]
        
        # Limpiar thumbnails existentes
        for widget in thumbnails_frame.winfo_children():
            widget.destroy()
        
        # Limpiar referencias antiguas
        if section.section_id in self.thumbnail_refs:
            self.thumbnail_refs[section.section_id].clear()
        else:
            self.thumbnail_refs[section.section_id] = []

        # Crear nuevos thumbnails
        for idx, img_data in enumerate(section.images):
            thumb_container = ttk.Frame(thumbnails_frame)
            thumb_container.pack(side="left", padx=5, pady=5)
            
            # Convertir PIL Image a PhotoImage
            photo = ImageTk.PhotoImage(img_data["thumbnail"])
            self.thumbnail_refs[section.section_id].append(photo)
            
            # Label con la imagen
            thumb_label = ttk.Label(thumb_container, image=photo)
            thumb_label.pack()
            
            # Botón X para eliminar
            delete_btn = tk.Button(thumb_container, text="×", fg="red", 
                                  font=("Arial", 10, "bold"),
                                  command=lambda s=section, i=idx: self._remove_image(s, i),
                                  relief="flat", bd=0, padx=2, pady=0)
            delete_btn.place(relx=1.0, rely=0, anchor="ne")
            
            # Tooltip con nombre
            thumb_label.bind("<Enter>", lambda e, n=img_data["name"]: 
                           self._show_tooltip(e, n))
            thumb_label.bind("<Leave>", self._hide_tooltip)
    
    def _remove_image(self, section: ImageSection, index: int):
        """Elimina una imagen de una sección."""
        if 0 <= index < len(section.images):
            img_name = section.images[index]["name"]
            section.remove_image(index)
            self.auto_log(f"🗑 Imagen eliminada de {section.title}: {img_name}")
            self._update_section_thumbnails(section)
            self._update_section_info(section)
    
    def _update_section_info(self, section: ImageSection):
        """Actualiza la información de una sección."""
        widgets = self.section_widgets.get(section.section_id)
        if not widgets:
            return
        
        count = len(section.images)
        total_size = sum(img["size"] for img in section.images) / (1024 * 1024)
        widgets["info_label"].config(
            text=f"{count} imagen{'es' if count != 1 else ''} - {total_size:.2f} MB total"
        )
        
        # Lógica de mostrar/ocultar el drop_frame para ahorrar espacio
        if count > 0:
            widgets["drop_frame"].grid_forget()
            widgets["add_more_btn"].grid(row=2, column=0, sticky="w", pady=2, padx=5)
        else:
            widgets["add_more_btn"].grid_forget()
            widgets["drop_frame"].grid(row=2, column=0, sticky="ew", pady=5)

    def _show_tooltip(self, event, text):
        """Muestra un tooltip."""
        self.tooltip = tk.Toplevel()
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        label = tk.Label(self.tooltip, text=text, bg="yellow", relief="solid", bd=1)
        label.pack()
    
    def _hide_tooltip(self, event):
        """Oculta el tooltip."""
        if hasattr(self, 'tooltip'):
            self.tooltip.destroy()
    
    def delete_section(self, section: ImageSection):
        """Elimina una sección completa."""
        if len(self.sections) <= 1:
            messagebox.showwarning("Aviso", "Debe haber al menos una sección")
            return
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar {section.title}?"):
            # Eliminar widget
            widgets = self.section_widgets.get(section.section_id)
            if widgets:
                widgets["frame"].destroy()
                del self.section_widgets[section.section_id]
            
            # Eliminar referencias de thumbnails
            if section.section_id in self.thumbnail_refs:
                del self.thumbnail_refs[section.section_id]
            
            # Eliminar sección
            self.sections.remove(section)
            self.auto_log(f"🗑 Sección eliminada: {section.title}")
            
            # Reorganizar grid
            self._reorganize_sections()
    
    def _reorganize_sections(self):
        """Reorganiza las secciones en el grid."""
        for section_id, widgets in self.section_widgets.items():
            widgets["frame"].grid_forget()
        
        for idx, section in enumerate(self.sections):
            widgets = self.section_widgets.get(section.section_id)
            if widgets:
                widgets["frame"].grid(row=idx // 2, column=idx % 2, sticky="nsew", padx=5, pady=5)

    def load_image_batch(self):
        """Carga un lote de imágenes y permite distribuirlas en secciones."""
        files = filedialog.askopenfilenames(
            title="Seleccionar lote de imágenes",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")]
        )
        
        if not files:
            return
            
        # Preguntar cuántas imágenes por sección
        count_per_section = simpledialog.askinteger(
            "Distribuir lote", 
            f"Se seleccionaron {len(files)} imágenes.\n¿Cuántas imágenes por sección?",
            initialvalue=5, minvalue=1, maxvalue=20
        )
        
        if not count_per_section:
            return
            
        self.auto_log(f"📦 Cargando lote de {len(files)} imágenes...")
        
        # Crear secciones y distribuir
        for i in range(0, len(files), count_per_section):
            batch = files[i:i + count_per_section]
            
            # Crear nueva sección
            self.section_counter += 1
            self.hierarchy_counter += 1
            new_section = ImageSection(self.section_counter)
            
            # Título dinámico
            prefix = self.parent_prefix.get().strip()
            if prefix:
                new_section.title = f"{prefix} {self.hierarchy_counter}"
            else:
                new_section.title = f"Sección {self.section_counter}"
                
            self.sections.append(new_section)
            self._create_section_widget(new_section)
            
            # Añadir imágenes a la sección
            for img_path in batch:
                self._add_image_to_section(new_section, img_path)
            
            self.auto_log(f"   ✅ Creada {new_section.title} con {len(batch)} imágenes.")
            
        self._reorganize_sections()
        messagebox.showinfo("Lote cargado", f"Se han creado {math.ceil(len(files)/count_per_section)} secciones automáticamente.")

    def check_sections_status(self):
        """Chequea el estado de todas las secciones."""
        self.auto_log("\n" + "="*50)
        self.auto_log("📊 CHEQUEO DE ESTADO DE SECCIONES")
        self.auto_log("="*50)
        
        total_images = 0
        total_size = 0
        ready_sections = 0
        
        for section in self.sections:
            status = section.get_status()
            self.auto_log(f"\n📁 {section.title}:")
            self.auto_log(f"   • Imágenes: {status['image_count']}")
            
            size_mb = status['total_size'] / (1024 * 1024)
            self.auto_log(f"   • Tamaño total: {size_mb:.2f} MB")
            
            if status['ready']:
                self.auto_log(f"   • Estado: ✅ LISTO para envío")
                ready_sections += 1
            else:
                self.auto_log(f"   • Estado: ⚠️ SIN IMÁGENES")
            
            # Detalles de cada imagen
            for img in section.images:
                img_size_mb = img['size'] / (1024 * 1024)
                self.auto_log(f"      - {img['name']}")
                self.auto_log(f"        Tamaño: {img_size_mb:.2f} MB | Formato: {img['format']}")
                self.auto_log(f"        Fecha: {img['date']}")
            
            total_images += status['image_count']
            total_size += status['total_size']
        
        self.auto_log(f"\n{'='*50}")
        self.auto_log(f"📈 RESUMEN:")
        self.auto_log(f"   • Total secciones: {len(self.sections)}")
        self.auto_log(f"   • Secciones listas: {ready_sections}/{len(self.sections)}")
        self.auto_log(f"   • Total imágenes: {total_images}")
        self.auto_log(f"   • Tamaño total: {total_size / (1024 * 1024):.2f} MB")
        
        if ready_sections == len(self.sections) and total_images > 0:
            self.auto_log(f"\n✅ TODOS LOS LOTES LISTOS PARA ENVÍO")
        elif total_images == 0:
            self.auto_log(f"\n⚠️ NO HAY IMÁGENES CARGADAS")
        else:
            self.auto_log(f"\n⚠️ ALGUNOS LOTES NO ESTÁN LISTOS")
        
        self.auto_log("="*50 + "\n")

    def clear_all_sections(self):
        """Limpia todas las secciones."""
        if messagebox.askyesno("Confirmar", "¿Eliminar todas las secciones y sus imágenes?"):
            # Eliminar todos los widgets
            for section_id, widgets in list(self.section_widgets.items()):
                widgets["frame"].destroy()
            
            self.section_widgets.clear()
            self.thumbnail_refs.clear()
            self.sections.clear()
            self.section_counter = 0
            self.hierarchy_counter = 0
            
            # Añadir una sección inicial
            self.add_section()
            self.auto_log("🗑 Todas las secciones eliminadas")
    
    def check_gemini_api(self):
        """Chequea la conexión con la API de Gemini."""
        def check():
            self.auto_log("\n" + "="*50)
            self.auto_log("🔌 CHEQUEANDO TODAS LAS APIs DE GEMINI...")
            self.auto_log("="*50)
            
            try:
                # Inicializar generador si no existe
                if not self.flashcard_generator:
                    self.flashcard_generator = GeminiFlashcardGenerator(log_callback=self.auto_log)
                
                # Verificar las 4 APIs
                all_ok = True
                for i in range(1, 5):
                    if not self.flashcard_generator.check_api_connection(i):
                        all_ok = False
                
                if all_ok:
                    self.auto_log(f"\n✅ TODAS LAS APIs CONECTADAS CORRECTAMENTE")
                    self.auto_log(f"   Modelo: {self.flashcard_generator.model_name}")
                else:
                    self.auto_log(f"\n⚠️ ALGUNAS APIs NO ESTÁN DISPONIBLES")
                
            except ImportError:
                self.auto_log(f"\n❌ ERROR: Módulo google-generativeai no instalado")
                self.auto_log(f"   Ejecuta: pip install google-generativeai")
            except Exception as e:
                self.auto_log(f"\n❌ ERROR DE CONEXIÓN:")
                self.auto_log(f"   {str(e)}")
            
            self.auto_log("="*50 + "\n")
        
        thread = threading.Thread(target=check, daemon=True)
        thread.start()
    
    def process_all_sections_auto(self):
        """Procesa todas las secciones: OCR → APIs → Conversión → Importación Anki."""
        # Validar que hay secciones con imágenes
        sections_with_images = [s for s in self.sections if s.images]
        
        if not sections_with_images:
            messagebox.showwarning("Sin imágenes", "No hay secciones con imágenes para procesar.")
            return
        
        if self.is_processing:
            messagebox.showwarning("En proceso", "Ya hay un procesamiento en curso.")
            return

        if not self._check_and_confirm_clear_pending_queue(mode="auto"):
            return

        if self.flashcard_generator:
            self.flashcard_generator.reset_exhausted_keys()
        
        # Confirmar
        total_images = sum(len(s.images) for s in sections_with_images)
        msg = f"¿Procesar {len(sections_with_images)} sección(es) con {total_images} imagen(es)?\n\n"
        msg += "Esto realizará:\n"
        msg += "1. Extracción OCR de cada sección\n"
        msg += "2. Generación de 4 tipos de flashcards con Gemini\n"
        msg += "3. Almacenamiento en Sala de Espera\n\n"
        msg += "Nota: Hay 60 segundos de espera entre secciones para evitar límites de API."
        
        if not messagebox.askyesno("Confirmar procesamiento", msg):
            return
        
        # Guardar sesión automáticamente antes de procesar
        self._save_current_session()
        
        # Resetear indicadores de estado
        self._reset_all_status_indicators()
        
        # Iniciar procesamiento en thread
        self.is_processing = True
        self.process_sections_btn.config(state="disabled", text="⏳ Procesando...")
        
        # Extraer variables Tkinter en hilo principal
        bisabuelo_str = self.great_grandparent_deck.get().strip()
        grandparent_str = self.grandparent_deck.get().strip()
        
        thread = threading.Thread(target=self._process_sections_thread, args=(bisabuelo_str, grandparent_str), daemon=True)
        thread.start()
    
    def _process_sections_thread(self, bisabuelo_str, grandparent_str):
        """Thread de procesamiento de secciones."""
        try:
            # Obtener configuración activa
            active_config = self.config_manager.get_active_set()
            
            # Inicializar o actualizar generador con la configuración
            if not self.flashcard_generator:
                self.flashcard_generator = GeminiFlashcardGenerator(
                    log_callback=self.auto_log,
                    config_set=active_config
                )
            else:
                self.flashcard_generator.log_callback = self.auto_log
                self.flashcard_generator.update_config(active_config)
            
            self.auto_log(f"📋 Usando configuración: {active_config.get('name', 'Por Defecto')}")
            self.auto_log(f"   Modelo: {self.flashcard_generator.model_name}")
            self.auto_log(f"   Tipos activos: {[k for k, v in self.flashcard_generator.active_types.items() if v]}")
            
            # Preparar datos de secciones
            sections_data = []
            for section in self.sections:
                if section.images:
                    sections_data.append({
                        "title": section.title,
                        "image_paths": [img["path"] for img in section.images]
                    })
            
            # 0. Crear sesión para guardado jerárquico
            bisabuelo = bisabuelo_str
            grandparent = grandparent_str or "General"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if bisabuelo:
                self.current_image_session = os.path.join(MASTER_FOLDER, bisabuelo, grandparent, f"Session_{timestamp}")
            else:
                self.current_image_session = os.path.join(MASTER_FOLDER, grandparent, f"Session_{timestamp}")
            
            # Procesar todas las secciones
            results = self.flashcard_generator.process_all_sections(
                sections=sections_data,
                converter=self.converter,
                anki_manager=self.anki_manager,
                bisabuelo_str=bisabuelo_str,
                grandparent_str=grandparent_str,
                progress_callback=self._on_section_progress,
                session_path=self.current_image_session
            )
            
            # Mostrar resumen final
            self._show_processing_summary(results)
            
        except Exception as e:
            error_msg = str(e)
            self.auto_log(f"\n❌ ERROR CRÍTICO: {error_msg}")
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("Error", f"Error durante el procesamiento:\n{msg}"))
        
        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.process_sections_btn.config(
                state="normal", text="🚀 Procesar Secciones"
            ))
    
    def _on_section_progress(self, section_title: str, current: int, total: int):
        """Callback de progreso de sección."""
        self.auto_log(f"\n📊 Progreso: {current}/{total} - {section_title}")
    
    def _log_qyi_metrics(self, metrics: dict, logger_func):
        """Loguea las métricas QYI de forma legible."""
        if not metrics:
            return
            
        qyi = metrics.get('qyi', 0.0)
        phi_q = metrics.get('phi_q', 0.0)
        phi_y = metrics.get('phi_y', 0.0)
        phi_c = metrics.get('phi_c', 0.0)
        
        status = "✅ EXCELENTE" if qyi >= 0.80 else "⚠️ MEJORABLE" if qyi >= 0.60 else "❌ BAJA CALIDAD"
        
        logger_func(f"   📊 MÉTRICAS DE CALIDAD PEDAGÓGICA (QYI):")
        logger_func(f"      • Índice QYI: {qyi:.2f} [{status}]")
        logger_func(f"      • Φ_Q (Calidad Fáctica): {phi_q:.2f}")
        logger_func(f"      • Φ_Y (Yield Instruccional): {phi_y:.2f}")
        logger_func(f"      • Φ_C (Cobertura Topológica): {phi_c:.2f}")

    def _show_processing_summary(self, results: list):
        """Muestra resumen del procesamiento, llena sala de espera y actualiza indicadores."""
        log_func = self._mode_log
        log_func("\n" + "="*60)
        log_func("📊 RESUMEN FINAL DE PROCESAMIENTO")
        log_func("="*60)
        
        total_generated = 0
        successful_sections = 0
        
        for result in results:
            section_title = result.get("section", "Unknown")
            if not result.get("success"):
                log_func(f"\n❌ {section_title}: ERROR")
                continue
                
            successful_sections += 1
            log_func(f"\n📁 {section_title}:")
            
            # Mostrar métricas QYI
            if "qyi_metrics" in result:
                self._log_qyi_metrics(result["qyi_metrics"], log_func)
            
            # Procesar cada tipo de tarjeta
            section_results = result.get("results", {})
            for card_type, res in section_results.items():
                if res.get("success"):
                    flashcards = res.get("flashcards", [])
                    count = len(flashcards)
                    deck = res.get("deck", "Default")
                    deck_path = self._get_deck_with_type_label(deck, card_type)
                    
                    if count > 0:
                        # AGREGAR A SALA DE ESPERA (No automático)
                        self.pending_flashcard_imports.append({
                            "deck_name": deck_path,
                            "card_type": card_type,
                            "flashcards": flashcards
                        })
                        total_generated += count
                        log_func(f"   ✅ {card_type}: {count} cards generadas")
                    
                    # Actualizar UI (bolitas de estado)
                    # Necesitamos encontrar el ID de la sección por su título
                    for sdata in self.sections:
                        if sdata.title == section_title:
                            self.root.after(0, lambda i=sdata.section_id, t=card_type, c=count: 
                                          self._update_section_status(i, t, True, c))
                            break
                else:
                    error_msg = res.get("error", "Error desconocido")
                    log_func(f"   ⚠️ {card_type}: Falló ({error_msg})")

        log_func(f"\n{'='*60}")
        log_func(f"✅ GENERACIÓN COMPLETADA")
        log_func(f"   • Secciones procesadas: {successful_sections}/{len(results)}")
        log_func(f"   • Total flashcards en sala de espera: {total_generated}")
        log_func(f"   • ACCIÓN REQUERIDA: Presiona '✅ Ejecutar Sincronización' para importar.")
        log_func("="*60 + "\n")
        
        # Actualizar botón de pendientes y guardar en disco
        self._save_pending_queue()
        self.root.after(0, self._update_pending_button)
        
        # Mostrar popup informativo
        self.root.after(0, lambda: messagebox.showinfo(
            "Generación Exitosa",
            f"Se han generado {total_generated} flashcards.\n\n"
            "Están en la 'Sala de Espera'.\n"
            "Debes presionar '✅ Ejecutar Sincronización' para enviarlas a Anki."
        ))
    
    def _update_section_status(self, section_id: int, card_type: str, success: bool, count: int):
        """Actualiza el indicador visual de estado de una sección."""
        widgets = self.section_widgets.get(section_id)
        if not widgets or "status_labels" not in widgets:
            return
        
        status_labels = widgets["status_labels"]
        if card_type not in status_labels:
            return
        
        state_label = status_labels[card_type]["state"]
        count_label = status_labels[card_type]["count"]
        
        if success:
            state_label.config(text="✅", fg="green")
            count_label.config(text=str(count))
        else:
            state_label.config(text="❌", fg="red")
            count_label.config(text="")
    
    def _reset_all_status_indicators(self):
        """Resetea todos los indicadores de estado a su valor inicial (⬜)."""
        for section_id, widgets in self.section_widgets.items():
            if "status_labels" not in widgets:
                continue
            
            for card_type, labels in widgets["status_labels"].items():
                labels["state"].config(text="⬜", fg="gray")
                labels["count"].config(text="")
    
    def auto_log(self, message: str):
        """Añade un mensaje al log del modo automático."""
        self.ui_queue.put({"type": "log", "target": "auto", "message": message})
    
    def video_log(self, message: str):
        """Añade un mensaje al log del modo de videos."""
        self.ui_queue.put({"type": "log", "target": "video", "message": message})
    
    def text_log(self, message: str):
        """Añade un mensaje al log del modo de texto."""
        self.ui_queue.put({"type": "log", "target": "text", "message": message})
    
    def _mode_log(self, message: str):
        """Añade un mensaje al log según el modo activo."""
        if self.current_mode == "automatic_text":
            self.text_log(message)
        elif self.current_mode == "automatic_audio":
            self.audio_log(message)
        elif self.current_mode == "automatic_videos":
            self.video_log(message)
        elif self.current_mode == "automatic_books":
            self.book_log(message)
        else:
            self.auto_log(message)
    
    # ==================== MÉTODOS DE TEXTO ====================
    
    def add_text_section(self):
        """Añade una nueva sección de texto."""
        self.text_section_counter += 1
        self.hierarchy_counter += 1
        
        section = TextSection(self.text_section_counter)
        
        prefix = self.parent_prefix.get().strip()
        if prefix:
            section.title = f"{prefix} {self.hierarchy_counter}"
        else:
            section.title = f"Sección {self.text_section_counter}"
            
        self.text_sections.append(section)
        
        self._create_text_section_widget(section)
        self.text_log(f"📁 Sección {section.section_id} creada")
        self._save_current_text_session()
    
    def _create_text_section_widget(self, section: TextSection):
        """Crea el widget visual para una sección de texto."""
        section_frame = ttk.LabelFrame(self.text_sections_inner_frame, padding="10")
        section_frame.grid(row=len(self.text_sections)-1, column=0, sticky="ew", pady=5, padx=5)
        section_frame.columnconfigure(0, weight=1)
        
        # Header de la sección con título editable
        header_frame = ttk.Frame(section_frame)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(1, weight=1)
        
        # Título (label por defecto, entry al editar)
        title_var = tk.StringVar(value=section.title)
        title_label = ttk.Label(header_frame, text=section.title, font=("Arial", 11, "bold"))
        title_label.grid(row=0, column=0, sticky="w")
        
        title_entry = ttk.Entry(header_frame, textvariable=title_var, width=20)
        
        # Botones de edición
        edit_btn = ttk.Button(header_frame, text="✏", width=3)
        edit_btn.grid(row=0, column=1, sticky="w", padx=5)
        
        confirm_btn = ttk.Button(header_frame, text="✓", width=3)

        def start_edit():
            title_label.grid_forget()
            edit_btn.grid_forget()
            title_entry.grid(row=0, column=0, sticky="w")
            confirm_btn.grid(row=0, column=1, sticky="w", padx=5)
            title_entry.focus()
        
        def confirm_edit():
            new_title = title_var.get().strip() or f"Sección {section.section_id}"
            section.title = new_title
            title_label.config(text=new_title)
            title_entry.grid_forget()
            confirm_btn.grid_forget()
            title_label.grid(row=0, column=0, sticky="w")
            edit_btn.grid(row=0, column=1, sticky="w", padx=5)
            self.text_log(f"📝 Sección {section.section_id} renombrada a: {new_title}")
            self._save_current_text_session()
        
        edit_btn.config(command=start_edit)
        confirm_btn.config(command=confirm_edit)
        title_entry.bind("<Return>", lambda e: confirm_edit())
        
        # Botón pegar desde portapapeles
        paste_btn = ttk.Button(header_frame, text="📋 Pegar", width=8,
                               command=lambda: self.paste_text_from_clipboard(section))
        paste_btn.grid(row=0, column=2, sticky="w", padx=5)
        
        # Botón eliminar sección
        delete_btn = ttk.Button(header_frame, text="🗑 Eliminar", 
                               command=lambda: self.delete_text_section(section))
        delete_btn.grid(row=0, column=3, sticky="e", padx=5)
        
        # Frame para indicadores de estado de los tipos de flashcards
        status_frame = ttk.Frame(section_frame)
        status_frame.grid(row=1, column=0, sticky="w", pady=(5, 0))
        
        # Crear los indicadores según el set activo
        status_labels = {}
        
        # Obtener tipos activos del config manager
        active_config = self.config_manager.get_active_set()
        active_types = active_config.get("active_types", {})
        
        # Iconos para cada tipo
        type_icons = {
            "basic": ("📝", "Basic"),
            "multiple_choice": ("🔘", "Multiple"),
            "cloze": ("🔲", "Cloze"),
            "vocabulary": ("🔤", "Vocab"),
            "level_1_cloze": ("1️⃣", "L1-Cloze"),
            "level_2_relations": ("2️⃣", "L2-Rel"),
            "level_3_application": ("3️⃣", "L3-App"),
            "level_4_analysis": ("4️⃣", "L4-Anal"),
            "atomic_extraction": ("⚛️", "Atomic")
        }
        
        # Filtrar solo los tipos activos
        card_types_icons = [
            (card_type, *type_icons.get(card_type, ("❓", card_type[:6])))
            for card_type, is_active in active_types.items() if is_active
        ]
        
        for idx, (card_type, icon, label) in enumerate(card_types_icons):
            type_frame = ttk.Frame(status_frame)
            type_frame.grid(row=0, column=idx, padx=(0, 15))
            
            # Icono del tipo
            icon_label = ttk.Label(type_frame, text=icon, font=("Segoe UI", 9))
            icon_label.grid(row=0, column=0)
            
            # Estado (⬜ inicial, ✅ éxito, ❌ fallo)
            state_label = tk.Label(type_frame, text="⬜", font=("Segoe UI", 9), fg="gray")
            state_label.grid(row=0, column=1, padx=2)
            
            # Contador (vacío inicialmente)
            count_label = ttk.Label(type_frame, text="", font=("Segoe UI", 8))
            count_label.grid(row=0, column=2)
            
            status_labels[card_type] = {
                "state": state_label,
                "count": count_label
            }
        
        # Text widget para el contenido
        text_frame = ttk.Frame(section_frame)
        text_frame.grid(row=2, column=0, sticky="nsew", pady=10)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        text_widget = tk.Text(text_frame, height=10, wrap="word", font=("Consolas", 10))
        text_widget.grid(row=0, column=0, sticky="nsew")
        
        text_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        text_scrollbar.grid(row=0, column=1, sticky="ns")
        text_widget.config(yscrollcommand=text_scrollbar.set)
        
        # Bind para actualizar contador de caracteres
        def update_char_count(event=None):
            content = text_widget.get("1.0", "end-1c")
            section.set_text(content)
            char_count = len(content)
            info_label.config(text=f"{char_count:,} caracteres")
        
        text_widget.bind("<KeyRelease>", update_char_count)
        # Bind para guardar al cambiar foco
        text_widget.bind("<FocusOut>", lambda e: self._save_current_text_session())
        
        # Info de la sección
        info_label = ttk.Label(section_frame, text="0 caracteres", foreground="gray")
        info_label.grid(row=3, column=0, sticky="w", pady=(5, 0))
        
        # Guardar referencias
        self.text_section_widgets[section.section_id] = {
            "frame": section_frame,
            "title_label": title_label,
            "title_var": title_var,
            "text_widget": text_widget,
            "info_label": info_label,
            "status_labels": status_labels
        }
    
    def paste_text_from_clipboard(self, section: TextSection):
        """Pega texto desde el portapapeles."""
        try:
            clipboard_text = self.root.clipboard_get()
            
            if not clipboard_text or not clipboard_text.strip():
                self.text_log("⚠️ El portapapeles está vacío")
                messagebox.showwarning("Portapapeles vacío", 
                                      "No hay texto en el portapapeles.")
                return
            
            # Obtener el text widget de la sección
            widgets = self.text_section_widgets.get(section.section_id)
            if widgets:
                text_widget = widgets["text_widget"]
                # Insertar al final del texto existente
                text_widget.insert("end", clipboard_text)
                # Actualizar contador
                content = text_widget.get("1.0", "end-1c")
                section.set_text(content)
                widgets["info_label"].config(text=f"{len(content):,} caracteres")
                
                self.text_log(f"📋 Texto pegado en {section.title} ({len(clipboard_text)} caracteres)")
        
        except tk.TclError:
            self.text_log("⚠️ No se pudo acceder al portapapeles")
            messagebox.showwarning("Error", "No se pudo acceder al portapapeles.")
        except Exception as e:
            self.text_log(f"❌ Error al pegar: {e}")
            messagebox.showerror("Error", f"No se pudo pegar el texto:\n{str(e)}")
    
    def delete_text_section(self, section: TextSection):
        """Elimina una sección de texto."""
        if len(self.text_sections) <= 1:
            messagebox.showwarning("Aviso", "Debe haber al menos una sección")
            return
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar {section.title}?"):
            # Eliminar widget
            widgets = self.text_section_widgets.get(section.section_id)
            if widgets:
                widgets["frame"].destroy()
                del self.text_section_widgets[section.section_id]
            
            # Eliminar sección
            self.text_sections.remove(section)
            self.text_log(f"🗑 Sección eliminada: {section.title}")
            self._save_current_text_session()
            
            # Reorganizar grid
            self._reorganize_text_sections()
    
    def _reorganize_text_sections(self):
        """Reorganiza las secciones de texto en el grid."""
        for idx, section in enumerate(self.text_sections):
            widgets = self.text_section_widgets.get(section.section_id)
            if widgets:
                widgets["frame"].grid(row=idx, column=0, sticky="ew", pady=5, padx=5)
    
    def check_text_sections_status(self):
        """Chequea el estado de todas las secciones de texto."""
        self.text_log("\n" + "="*50)
        self.text_log("📊 CHEQUEO DE ESTADO DE SECCIONES")
        self.text_log("="*50)
        
        total_chars = 0
        ready_sections = 0
        
        for section in self.text_sections:
            status = section.get_status()
            self.text_log(f"\n📁 {section.title}:")
            self.text_log(f"   • Caracteres: {status['char_count']:,}")
            
            if status['ready']:
                self.text_log(f"   • Estado: ✅ LISTO para envío")
                ready_sections += 1
            else:
                self.text_log(f"   • Estado: ⚠️ SIN TEXTO")
            
            total_chars += status['char_count']
        
        self.text_log(f"\n{'='*50}")
        self.text_log(f"📈 RESUMEN:")
        self.text_log(f"   • Total secciones: {len(self.text_sections)}")
        self.text_log(f"   • Secciones listas: {ready_sections}/{len(self.text_sections)}")
        self.text_log(f"   • Total caracteres: {total_chars:,}")
        
        if ready_sections == len(self.text_sections) and total_chars > 0:
            self.text_log(f"\n✅ TODOS LOS LOTES LISTOS PARA ENVÍO")
        elif total_chars == 0:
            self.text_log(f"\n⚠️ NO HAY TEXTO CARGADO")
        else:
            self.text_log(f"\n⚠️ ALGUNOS LOTES NO ESTÁN LISTOS")
        
        self.text_log("="*50 + "\n")
    
    def clear_all_text_sections(self):
        """Limpia todas las secciones de texto."""
        if messagebox.askyesno("Confirmar", "¿Eliminar todas las secciones de texto?"):
            # Eliminar todos los widgets
            for section_id, widgets in list(self.text_section_widgets.items()):
                widgets["frame"].destroy()
            
            self.text_section_widgets.clear()
            self.text_sections.clear()
            self.text_section_counter = 0
            self.hierarchy_counter = 0
            
            # Añadir una sección inicial
            self.add_text_section()
            self.text_log("🗑 Todas las secciones eliminadas")
            self._save_current_text_session()
    
    def check_gemini_api_text(self):
        """Chequea la conexión con la API de Gemini (para modo texto)."""
        def check():
            self.text_log("\n" + "="*50)
            self.text_log("🔌 CHEQUEANDO TODAS LAS APIs DE GEMINI...")
            self.text_log("="*50)
            
            try:
                # Inicializar generador si no existe
                if not self.flashcard_generator:
                    self.flashcard_generator = GeminiFlashcardGenerator(log_callback=self.text_log)
                
                # Verificar las 4 APIs
                all_ok = True
                for i in range(1, 5):
                    if not self.flashcard_generator.check_api_connection(i):
                        all_ok = False
                
                if all_ok:
                    self.text_log(f"\n✅ TODAS LAS APIs CONECTADAS CORRECTAMENTE")
                    self.text_log(f"   Modelo: {self.flashcard_generator.model_name}")
                else:
                    self.text_log(f"\n⚠️ ALGUNAS APIs NO ESTÁN DISPONIBLES")
                
            except ImportError:
                self.text_log(f"\n❌ ERROR: Módulo google-generativeai no instalado")
                self.text_log(f"   Ejecuta: pip install google-generativeai")
            except Exception as e:
                self.text_log(f"\n❌ ERROR DE CONEXIÓN:")
                self.text_log(f"   {str(e)}")
            
            self.text_log("="*50 + "\n")
        
        thread = threading.Thread(target=check, daemon=True)
        thread.start()
    
    def process_all_text_sections(self):
        """Procesa todas las secciones de texto."""
        # Validar que hay secciones con texto
        sections_with_text = [s for s in self.text_sections if s.get_text().strip()]
        
        if not sections_with_text:
            messagebox.showwarning("Sin texto", "No hay secciones con texto para procesar.")
            return
        
        if self.is_processing:
            messagebox.showwarning("En proceso", "Ya hay un procesamiento en curso.")
            return

        if not self._check_and_confirm_clear_pending_queue(mode="text"):
            return

        if self.flashcard_generator:
            self.flashcard_generator.reset_exhausted_keys()
        
        # Confirmar
        total_chars = sum(len(s.get_text()) for s in sections_with_text)
        msg = f"¿Procesar {len(sections_with_text)} sección(es) con {total_chars:,} caracteres?\n\n"
        msg += "Esto realizará:\n"
        msg += "1. Generación SECUENCIAL de flashcards con Gemini\n"
        msg += "2. Almacenamiento en Sala de Espera\n\n"
        msg += "Nota: El procesamiento es secuencial para evitar límites de API."
        
        if not messagebox.askyesno("Confirmar procesamiento", msg):
            return
        
        # Resetear indicadores de estado
        self._reset_all_text_status_indicators()
        
        # Iniciar procesamiento en thread
        self.is_processing = True
        self.process_text_sections_btn.config(state="disabled", text="⏳ Procesando...")
        
        # Extraer string de tkinter en el hilo principal para evitar vacíos
        bisabuelo_str = self.great_grandparent_deck.get().strip()
        grandparent_str = self.grandparent_deck.get().strip()
        
        thread = threading.Thread(target=self._process_text_sections_thread, args=(bisabuelo_str, grandparent_str), daemon=True)
        thread.start()
    
    def _process_text_sections_thread(self, bisabuelo_str, grandparent_str):
        """Thread de procesamiento de secciones de texto."""
        try:
            # 0. Asegurar sesión activa
            if not hasattr(self, 'current_text_session') or not self.current_text_session:
                bisabuelo = bisabuelo_str
                grandparent = grandparent_str or "General"
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if bisabuelo:
                    self.current_text_session = os.path.join(MASTER_FOLDER, bisabuelo, grandparent, f"Session_{timestamp}")
                else:
                    self.current_text_session = os.path.join(MASTER_FOLDER, grandparent, f"Session_{timestamp}")

            # Obtener configuración activa
            active_config = self.config_manager.get_active_set()
            
            # Inicializar o actualizar generador con la configuración
            if not self.flashcard_generator:
                self.flashcard_generator = GeminiFlashcardGenerator(
                    log_callback=self.text_log,
                    config_set=active_config
                )
            else:
                self.flashcard_generator.log_callback = self.text_log
                self.flashcard_generator.update_config(active_config)
            
            self.text_log(f"📋 Usando configuración: {active_config.get('name', 'Por Defecto')}")
            self.text_log(f"   Modelo: {self.flashcard_generator.model_name}")
            self.text_log(f"   Tipos activos: {[k for k, v in self.flashcard_generator.active_types.items() if v]}")
            self.text_log(f"   Modo: SECUENCIAL (API1→API2→API3→API4)")
            
            total_flashcards = 0
            processing_results = []
            
            # Procesar cada sección
            for idx, section in enumerate(self.text_sections, 1):
                texto = section.get_text().strip()
                if not texto:
                    continue
                
                self.text_log(f"\n{'='*60}")
                self.text_log(f"📁 PROCESANDO SECCIÓN {idx}/{len(self.text_sections)}: {section.title}")
                self.text_log(f"{'='*60}")
                
                # ... (lógica de estructuración existente) ...
                
                results = self.flashcard_generator.generate_all_flashcards_sequential(texto)
                
                # Capturar métricas QYI
                qyi_metrics = getattr(self.flashcard_generator, 'last_evaluation_metrics', {})
                
                # Determinar deck name base (Bisabuelo::Abuelo::Sección)
                deck_base = ""
                if bisabuelo_str:
                    deck_base += f"{bisabuelo_str}::"
                deck_base += f"{grandparent_str}::{section.title}"
                
                section_res = {
                    "section": section.title,
                    "success": True,
                    "results": {},
                    "qyi_metrics": qyi_metrics
                }
                
                # Procesar resultados
                for card_type, result in results.items():
                    if result.get("success"):
                        raw_content = result.get("content", "")
                        tsv_content = self.converter.convert(raw_content, card_type)
                        flashcard_list = self.flashcard_generator._parse_tsv_to_flashcards(tsv_content)
                        
                        if flashcard_list:
                            count = len(flashcard_list)
                            total_flashcards += count
                            
                            # Guardar flashcards generadas en la carpeta de la sesión de texto
                            if hasattr(self, 'current_text_session') and self.current_text_session:
                                self.flashcard_generator._save_flashcards_tsv(
                                    tsv_content, self.current_text_session, section.title, card_type
                                )
                            
                            self.root.after(0, lambda sid=section.section_id, ct=card_type, c=count:
                                          self._update_text_section_status(sid, ct, True, c))
                            
                            section_res["results"][card_type] = {
                                "success": True,
                                "count": count,
                                "flashcards": flashcard_list,
                                "deck": deck_base
                            }
                        else:
                            self.text_log(f"   ⚠️ No se pudieron estructurar tarjetas para '{card_type}' (respuesta: '{raw_content[:60]}...')")
                            self.root.after(0, lambda sid=section.section_id, ct=card_type:
                                          self._update_text_section_status(sid, ct, False, 0))
                            
                            section_res["results"][card_type] = {
                                "success": False,
                                "error": "No flashcards parsed"
                            }
                    else:
                        error_msg = result.get("error", "Error desconocido")
                        self.text_log(f"   ❌ Error al generar tipo '{card_type}': {error_msg}")
                        self.root.after(0, lambda sid=section.section_id, ct=card_type:
                                      self._update_text_section_status(sid, ct, False, 0))
                        
                        section_res["results"][card_type] = {
                            "success": False,
                            "error": error_msg
                        }
                
                processing_results.append(section_res)
            
            # Asegurar que la sesión de texto se guarde con su ruta de flashcards vinculada
            self._save_current_text_session()
            
            # Mostrar resumen final
            self.root.after(0, lambda: self._show_processing_summary(processing_results))
            
        except Exception as e:
            error_msg = str(e)
            self.text_log(f"\n❌ ERROR CRÍTICO: {error_msg}")
            self.root.after(0, lambda msg=error_msg: messagebox.showerror(
                "Error", f"Error durante el procesamiento:\n{msg}"))
        
        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.process_text_sections_btn.config(
                state="normal", text="🚀 Procesar Secciones"
            ))
    
    def _update_text_section_status(self, section_id: int, card_type: str, success: bool, count: int):
        """Actualiza el indicador visual de estado de una sección de texto."""
        widgets = self.text_section_widgets.get(section_id)
        if not widgets or "status_labels" not in widgets:
            return
        
        status_labels = widgets["status_labels"]
        if card_type not in status_labels:
            return
        
        state_label = status_labels[card_type]["state"]
        count_label = status_labels[card_type]["count"]
        
        if success:
            state_label.config(text="✅", fg="green")
            count_label.config(text=str(count))
        else:
            state_label.config(text="❌", fg="red")
            count_label.config(text="")
    
    def _reset_all_text_status_indicators(self):
        """Resetea todos los indicadores de estado de texto a su valor inicial (⬜)."""
        for section_id, widgets in self.text_section_widgets.items():
            if "status_labels" not in widgets:
                continue
            
            for card_type, labels in widgets["status_labels"].items():
                labels["state"].config(text="⬜", fg="gray")
                labels["count"].config(text="")
    
    # ==================== MÉTODOS DE VIDEOS ====================
    
    def _on_video_drop(self, event):
        """Manejador para el evento drop de videos."""
        # Limpiar ruta (tkinterdnd2 a veces añade llaves {} a rutas con espacios)
        file_path = event.data
        if file_path.startswith('{') and file_path.endswith('}'):
            file_path = file_path[1:-1]
            
        # Llamar al método de carga con la ruta directa
        self.upload_video_for_processing(file_path=file_path)

    def download_youtube_video(self):
        """Descarga un video de YouTube a través de una URL."""
        url = self.youtube_url_var.get().strip()
        if not url:
            messagebox.showwarning("URL vacía", "Por favor ingresa una URL de YouTube.")
            return
            
        self.yt_download_btn.config(state="disabled", text="⏳ Descargando...")
        self.video_log(f"🎬 Iniciando descarga de YouTube: {url}")
        
        # Obtener preferencia de cookies
        use_cookies = self.use_browser_cookies_var.get()
        
        def run_download():
            path = self.youtube_downloader.download_video(url, self.video_log, use_browser_cookies=use_cookies)
            
            def on_complete():
                self.yt_download_btn.config(state="normal", text="📥 Descargar")
                if path and os.path.exists(path):
                    self.video_log(f"✅ Video de YouTube descargado: {path}")
                    self.upload_video_for_processing(file_path=path)
                else:
                    messagebox.showerror("Error", "No se pudo descargar el video de YouTube.")
            
            self.root.after(0, on_complete)
            
        threading.Thread(target=run_download, daemon=True).start()

    def upload_video_for_processing(self, file_path: str = None):
        """Abre diálogo para seleccionar un video y lo prepara para procesamiento (o usa ruta directa)."""
        if not file_path:
            filetypes = [
                ("Videos", "*.mp4 *.avi *.mov *.mkv"),
                ("Todos los archivos", "*.*")
            ]
            file_path = filedialog.askopenfilename(title="Seleccionar video", filetypes=filetypes)
        
        if not file_path:
            return
        
        # Validar video
        valid, msg = self.video_processor.validate_video(file_path)
        
        if not valid:
            self.video_log(f"❌ {msg}")
            messagebox.showerror("Video inválido", msg)
            return
        
        self.video_log(f"✅ {msg}")
        self.video_log(f"📁 Video cargado: {os.path.basename(file_path)}")
        
        # Guardar referencia al video
        self.current_video_path = file_path
        self.video_info_label.config(text=f"📹 {os.path.basename(file_path)}")
        
        # Ocultar zona de drag&drop, mostrar botón compacto
        if hasattr(self, 'video_drop_frame'):
            self.video_drop_frame.grid_forget()
        if hasattr(self, 'change_video_btn'):
            self.change_video_btn.pack(side="left", padx=5)
            
        # Habilitar botón de procesamiento
        self.process_video_btn.config(state="normal")
    
    def process_video_complete(self):
        """Procesa el video completo: segmenta, extrae audio y transcribe."""
        if not self.current_video_path:
            messagebox.showwarning("Sin video", "No hay video cargado.")
            return
        
        if self.is_processing:
            messagebox.showwarning("En proceso", "Ya hay un procesamiento en curso.")
            return
        
        # Confirmar
        msg = f"¿Procesar el video?\n\n"
        msg += "Esto realizará:\n"
        msg += "1. Segmentación del video según configuración\n"
        msg += "2. Extracción de fragmentos de video completos (MP4)\n"
        msg += "3. Transcripción Multimodal Inteligente con Gemini AI\n\n"
        msg += "Nota: Este proceso puede tomar varios minutos según su conexión y longitud."
        
        if not messagebox.askyesno("Confirmar procesamiento", msg):
            return
        
        # Iniciar procesamiento en thread
        self.is_processing = True
        self.process_video_btn.config(state="disabled", text="⏳ Procesando...")
        
        thread = threading.Thread(target=self._process_video_thread, daemon=True)
        thread.start()
    
    def _process_video_thread(self):
        """Thread de procesamiento del video."""
        try:
            # 0. Determinar el modo de segmentación
            mode_type = getattr(self, "video_segmentation_mode_var", None)
            segmentation_mode = mode_type.get() if mode_type else "standard"
            
            self.video_log(f"\n{'='*60}")
            self.video_log(f"🎬 PROCESANDO VIDEO (Modo: {segmentation_mode.upper()})")
            self.video_log(f"{'='*60}")
            
            # Variables para segmentación
            explicit_timestamps = None
            
            # --- RUTA SEMÁNTICA (FASE 3) ---
            if segmentation_mode == "semantic":
                self.video_log("\n🧠 Iniciando Segmentación Semántica con IA (PySceneDetect)...")
                chunker = self.chunking_factory.get_chunker(self.current_video_path, "semantic")
                
                # Ejecutar estrategia
                result = chunker.process_and_chunk(self.current_video_path)
                
                if not result.get("success"):
                    self.video_log(f"❌ Error Semántico: {result.get('error')}")
                    self.is_processing = False
                    self.root.after(0, lambda: self.process_video_btn.config(state="normal", text="🚀 Procesar Video"))
                    return
                
                self.video_log(f"✓ {result.get('message')}")
                explicit_timestamps = result.get("timestamps")
                self.video_log("🔄 Delegando extracción y multimodal al procesador principal...")
                
            # --- RUTA ESTÁNDAR O POST-SEMÁNTICA ---
            # Obtener configuración
            segment_duration = self.segment_duration_var.get() * 60  # Convertir a segundos
            overlap = self.overlap_var.get()
            language = self.language_var.get()
            
            # 0. Crear sesión para guardado jerárquico
            bisabuelo = self.great_grandparent_deck.get().strip()
            grandparent = self.grandparent_deck.get().strip() or "General"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if bisabuelo:
                self.current_video_session = os.path.join(MASTER_FOLDER, bisabuelo, grandparent, f"Session_{timestamp}")
            else:
                self.current_video_session = os.path.join(MASTER_FOLDER, grandparent, f"Session_{timestamp}")
            
            # Crear la carpeta de sesión jerárquica INMEDIATAMENTE (checkpoint de inicio)
            os.makedirs(os.path.join(self.current_video_session, "chunks"), exist_ok=True)
            
            # Guardar registro inicial de sesión para poder recuperarla aunque el proceso se interrumpa
            try:
                session_registry = {
                    "video_path": self.current_video_path,
                    "video_name": os.path.basename(self.current_video_path) if self.current_video_path else "",
                    "great_grandparent": self.great_grandparent_deck.get(),
                    "grandparent": self.grandparent_deck.get(),
                    "father_prefix": self.parent_prefix.get(),
                    "extraction_mode": self.extraction_mode_video.get(),
                    "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "segmenting"
                }
                registry_path = os.path.join(self.current_video_session, "session_registry.json")
                with open(registry_path, 'w', encoding='utf-8') as rf:
                    json.dump(session_registry, rf, ensure_ascii=False, indent=2)
                self.video_log(f"   📌 Sesión jerárquica iniciada: {self.current_video_session}")
            except Exception as reg_err:
                self.video_log(f"   ⚠️ Error guardando registro de sesión: {reg_err}")
            
            # 0.1. Inicializar flashcard_generator ANTES de procesar para guardado incremental
            if not hasattr(self, 'flashcard_generator') or not self.flashcard_generator:
                # Usar el generador global

                active_config = self.config_manager.get_active_set()
                self.flashcard_generator = GeminiFlashcardGenerator(log_callback=self.video_log, config_set=active_config)
            
            # 0.2. Contador de segmentos guardados incrementalmente
            saved_count = [0]
            
            # Callback para guardado incremental: se llama cada vez que un segmento termina de transcribirse
            def on_segment_complete(segment):
                """Guarda la transcripción del segmento al instante para no perder progreso."""
                if segment.transcription_text:
                    self.flashcard_generator._save_ocr_transcript(
                        segment.transcription_text, self.current_video_session, 
                        f"segment_{segment.segment_id:03d}", 
                        subfolder="chunks"
                    )
                    saved_count[0] += 1
                    self.video_log(f"   💾 Segmento {segment.segment_id} guardado incrementalmente ({saved_count[0]} guardados)")
            
            # Procesar video con video_processor (con callback de guardado incremental)
            mode = self.extraction_mode_video.get()
            result = self.video_processor.process_video(
                video_path=self.current_video_path,
                segment_duration=segment_duration,
                overlap=overlap,
                use_silence_detection=False,
                use_transcription_analysis=False,
                language=language,
                on_segment_complete=on_segment_complete,
                great_grandparent=self.great_grandparent_deck.get(),
                grandparent=self.grandparent_deck.get(),
                father_prefix=self.parent_prefix.get(),
                extraction_mode=mode,
                explicit_timestamps=explicit_timestamps
            )
            
            # Actualizar el estado del registro de sesión tras completar el procesamiento
            try:
                registry_path = os.path.join(self.current_video_session, "session_registry.json")
                if os.path.exists(registry_path):
                    with open(registry_path, 'r', encoding='utf-8') as rf:
                        session_registry = json.load(rf)
                    session_registry["status"] = "segmented" if result.get("success") else "failed"
                    session_registry["total_segments"] = len(result.get("segments", []))
                    session_registry["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with open(registry_path, 'w', encoding='utf-8') as rf:
                        json.dump(session_registry, rf, ensure_ascii=False, indent=2)
            except Exception:
                pass

            
            if not result.get("success"):
                self.video_log(f"❌ Error procesando video: {result.get('error')}")
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", f"Error procesando video:\n{result.get('error')}"))
                return
            
            # Guardar segmentos
            self.current_video_segments = result.get("segments", [])
            
            # Guardar la transcripción completa consolidada (bonus, los chunks ya están guardados)
            try:
                full_transcription = "\n\n".join([
                    f"--- Segmento {s.segment_id} ({s.start_time} - {s.end_time}) ---\n{s.transcription_text}"
                    for s in self.current_video_segments
                ])
                
                self.flashcard_generator._save_ocr_transcript(
                    full_transcription, self.current_video_session, "original_full_transcription", 
                    subfolder="original_text"
                )
                self.video_log(f"   💾 Transcripción completa consolidada guardada")
            except Exception as save_err:
                self.video_log(f"   ⚠️ Error guardando transcripción consolidada (los chunks individuales ya están guardados): {save_err}")
            
            self.video_log(f"\n✅ Video procesado exitosamente")
            self.video_log(f"   📊 {len(self.current_video_segments)} segmentos creados")
            self.video_log(f"   💾 {saved_count[0]} segmentos guardados incrementalmente")
            self.video_log(f"   📝 Total de caracteres: {result.get('total_chars', 0):,}")
            self.video_log(f"   📂 Sesión guardada en: {self.current_video_session}")
            
            # Guardar vínculo entre la sesión temporal del video_processor y la sesión jerárquica
            # Esto permite recuperar la sesión sin re-procesar el video
            temp_session_dir = result.get("session_dir")
            if temp_session_dir and os.path.isdir(temp_session_dir):
                try:
                    link_data = {
                        "flashcard_session_path": self.current_video_session,
                        "video_path": self.current_video_path,
                        "great_grandparent": self.great_grandparent_deck.get(),
                        "grandparent": self.grandparent_deck.get(),
                        "father_prefix": self.parent_prefix.get(),
                        "linked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "total_segments": len(self.current_video_segments),
                        "total_chars": result.get("total_chars", 0)
                    }
                    link_path = os.path.join(temp_session_dir, "session_link.json")
                    with open(link_path, 'w', encoding='utf-8') as lf:
                        json.dump(link_data, lf, ensure_ascii=False, indent=2)
                    self.video_log(f"   🔗 Vínculo de sesión guardado en: {link_path}")
                except Exception as link_err:
                    self.video_log(f"   ⚠️ Error guardando vínculo de sesión: {link_err}")

            
            # Mostrar segmentos en la UI
            self.root.after(0, self._display_video_segments)
            
            # Habilitar botón de crear secciones y botón de ventana emergente
            self.root.after(0, lambda: self.create_sections_btn.config(state="normal"))
            self.root.after(0, lambda: self.view_segments_btn.config(state="normal"))
            self.root.after(0, self.show_segments_window)
            
            # Mostrar popup
            self.root.after(0, lambda: messagebox.showinfo(
                "Procesamiento completado",
                f"Video procesado exitosamente\n\n"
                f"Segmentos creados: {len(self.current_video_segments)}\n"
                f"Segmentos guardados: {saved_count[0]}\n"
                f"Total de caracteres: {result.get('total_chars', 0):,}\n\n"
                f"Ahora puedes configurar la agrupación en secciones."
            ))
            
        except Exception as e:
            error_msg = str(e)
            self.video_log(f"\n❌ ERROR CRÍTICO: {error_msg}")
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda msg=error_msg: messagebox.showerror(
                "Error", f"Error durante el procesamiento:\n{msg}"))
        
        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.process_video_btn.config(
                state="normal", text="🚀 Procesar Video"
            ))
    
    def _display_video_segments(self):
        """Muestra los segmentos procesados en la UI."""
        # Limpiar segmentos anteriores
        for widget in self.segments_inner_frame.winfo_children():
            widget.destroy()
        
        self.video_segment_widgets.clear()
        
        # Crear tarjetas para cada segmento
        for segment in self.current_video_segments:
            self._create_segment_widget(segment)
            
        # Forzar actualización de UI y scrollregion tras crear los widgets
        self.root.update_idletasks()
        self.segments_canvas.configure(scrollregion=self.segments_canvas.bbox("all"))
    
    def _create_segment_widget(self, segment: VideoSegment):
        """Crea el widget visual para un segmento de video."""
        segment_frame = ttk.Frame(self.segments_inner_frame, relief="groove", borderwidth=2)
        segment_frame.grid(row=segment.segment_id-1, column=0, sticky="ew", pady=5, padx=5)
        segment_frame.columnconfigure(0, weight=1)
        
        # Header con info del segmento
        header_frame = ttk.Frame(segment_frame)
        header_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ttk.Label(header_frame, text=f"Segmento {segment.segment_id}", 
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(header_frame, text=f"{segment.get_time_range_str()}", 
                 font=("Segoe UI", 9), foreground="gray").pack(side="left", padx=10)
        ttk.Label(header_frame, text=f"{segment.char_count:,} caracteres", 
                 font=("Segoe UI", 9), foreground="blue").pack(side="left")
        
        # Botones de acción
        buttons_frame = ttk.Frame(segment_frame)
        buttons_frame.grid(row=1, column=0, pady=5)
        
        # Botón de reproducción
        play_btn = ttk.Button(buttons_frame, text="▶️", width=5,
                             command=lambda s=segment: self.play_segment_audio(s))
        play_btn.pack(side="left", padx=5)
        
        # Botón ver transcripción
        view_btn = ttk.Button(buttons_frame, text="📄 Ver Transcripción", width=18,
                             command=lambda s=segment: self.show_transcription_dialog(s))
        view_btn.pack(side="left", padx=5)
        
        # Guardar referencias
        self.video_segment_widgets[segment.segment_id] = {
            "frame": segment_frame,
            "play_btn": play_btn,
            "view_btn": view_btn,
            "segment": segment
        }
    
    def play_segment_audio(self, segment: VideoSegment):
        """Reproduce el audio de un segmento."""
        if not segment.audio_path or not os.path.exists(segment.audio_path):
            self.video_log(f"❌ Audio no encontrado para segmento {segment.segment_id}")
            messagebox.showerror("Error", "Archivo de audio no encontrado.")
            return
        
        # Cambiar icono a pause
        widgets = self.video_segment_widgets.get(segment.segment_id)
        if widgets:
            widgets["play_btn"].config(text="⏸️")
        
        self.video_log(f"▶️ Reproduciendo segmento {segment.segment_id}...")
        
        # Reproducir en thread para no bloquear UI
        def play_thread():
            try:
                self.video_processor.play_audio(segment.audio_path)
            except Exception as e:
                self.video_log(f"❌ Error reproduciendo audio: {e}")
            finally:
                # Restaurar icono
                if widgets:
                    self.root.after(0, lambda: widgets["play_btn"].config(text="▶️"))
        
        thread = threading.Thread(target=play_thread, daemon=True)
        thread.start()
    
    def show_transcription_dialog(self, segment: VideoSegment):
        """Muestra una ventana emergente con la transcripción completa."""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Transcripción - Segmento {segment.segment_id}")
        dialog.geometry("600x400")
        
        # Header
        header_frame = ttk.Frame(dialog, padding="10")
        header_frame.pack(fill="x")
        
        ttk.Label(header_frame, text=f"Segmento {segment.segment_id}: {segment.get_time_range_str()}", 
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(header_frame, text=f"Duración: {segment.duration:.1f}s | Caracteres: {segment.char_count:,}", 
                 font=("Segoe UI", 9), foreground="gray").pack(anchor="w")
        
        # Text widget con scrollbar
        text_frame = ttk.Frame(dialog, padding="10")
        text_frame.pack(fill="both", expand=True)
        
        text_widget = tk.Text(text_frame, wrap="word", font=("Consolas", 10))
        text_widget.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        scrollbar.pack(side="right", fill="y")
        text_widget.config(yscrollcommand=scrollbar.set)
        
        # Insertar transcripción
        text_widget.insert("1.0", segment.transcription_text)
        text_widget.config(state="disabled")  # Solo lectura
        
        # Botones
        buttons_frame = ttk.Frame(dialog, padding="10")
        buttons_frame.pack(fill="x")
        
        def copy_to_clipboard():
            self.root.clipboard_clear()
            self.root.clipboard_append(segment.transcription_text)
            self.video_log(f"📋 Transcripción del segmento {segment.segment_id} copiada al portapapeles")
        
        ttk.Button(buttons_frame, text="📋 Copiar", command=copy_to_clipboard).pack(side="left", padx=5)
        ttk.Button(buttons_frame, text="Cerrar", command=dialog.destroy).pack(side="right", padx=5)
    
    def create_video_sections_from_segments(self):
        """Crea secciones automáticamente agrupando segmentos."""
        if not self.current_video_segments:
            messagebox.showwarning("Sin segmentos", "No hay segmentos procesados.")
            return
        
        segments_per_section = self.segments_per_section_var.get()
        
        if segments_per_section < 1 or segments_per_section > 10:
            messagebox.showerror("Error", "El número de transcripciones por sección debe estar entre 1 y 10.")
            return
        
        # Limpiar secciones anteriores
        self.video_sections.clear()
        for widget in self.video_sections_inner_frame.winfo_children():
            widget.destroy()
        self.video_section_widgets.clear()
        
        # Crear secciones
        self.video_section_counter = 0
        total_segments = len(self.current_video_segments)
        
        for i in range(0, total_segments, segments_per_section):
            self.video_section_counter += 1
            self.hierarchy_counter += 1
            
            section = VideoSection(self.video_section_counter)
            
            # Configurar sufijo padre
            prefix = self.parent_prefix.get().strip()
            if prefix:
                section.title = f"{prefix} {self.hierarchy_counter}"
            else:
                section.title = f"Sección {self.video_section_counter}"
            
            # Añadir segmentos a la sección
            for j in range(i, min(i + segments_per_section, total_segments)):
                segment = self.current_video_segments[j]
                section.add_segment(segment)
            
            self.video_sections.append(section)
            self._create_video_section_widget(section)
        
        self.video_log(f"✨ Creadas {len(self.video_sections)} secciones con {segments_per_section} transcripciones cada una")
        
        # Habilitar botón de procesamiento
        self.process_sections_btn.config(state="normal")
        
        messagebox.showinfo("Secciones creadas", 
                           f"Se crearon {len(self.video_sections)} secciones.\n\n"
                           f"Ahora puedes reorganizar los segmentos arrastrándolos\n"
                           f"entre secciones si lo deseas, o procesar directamente.")
    
    def _create_video_section_widget(self, section: VideoSection):
        """Crea el widget visual para una sección de video."""
        section_frame = ttk.LabelFrame(self.video_sections_inner_frame, padding="10")
        section_frame.grid(row=len(self.video_sections)-1, column=0, sticky="ew", pady=5, padx=5)
        section_frame.columnconfigure(0, weight=1)
        
        # Header con título editable
        header_frame = ttk.Frame(section_frame)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(1, weight=1)
        
        title_var = tk.StringVar(value=section.title)
        title_label = ttk.Label(header_frame, text=section.title, font=("Arial", 11, "bold"))
        title_label.grid(row=0, column=0, sticky="w")
        
        title_entry = ttk.Entry(header_frame, textvariable=title_var, width=20)
        
        edit_btn = ttk.Button(header_frame, text="✏", width=3)
        edit_btn.grid(row=0, column=1, sticky="w", padx=5)
        
        confirm_btn = ttk.Button(header_frame, text="✓", width=3)
        
        def start_edit():
            title_label.grid_forget()
            edit_btn.grid_forget()
            title_entry.grid(row=0, column=0, sticky="w")
            confirm_btn.grid(row=0, column=1, sticky="w", padx=5)
            title_entry.focus()
        
        def confirm_edit():
            new_title = title_var.get().strip() or f"Sección {section.section_id}"
            section.title = new_title
            title_label.config(text=new_title)
            title_entry.grid_forget()
            confirm_btn.grid_forget()
            title_label.grid(row=0, column=0, sticky="w")
            edit_btn.grid(row=0, column=1, sticky="w", padx=5)
            self.video_log(f"📝 Sección {section.section_id} renombrada a: {new_title}")
        
        edit_btn.config(command=start_edit)
        confirm_btn.config(command=confirm_edit)
        title_entry.bind("<Return>", lambda e: confirm_edit())
        
        # Botón eliminar sección
        delete_btn = ttk.Button(header_frame, text="🗑 Eliminar", 
                               command=lambda: self.delete_video_section(section))
        delete_btn.grid(row=0, column=2, sticky="e", padx=5)
        
        # Info de la sección
        info_frame = ttk.Frame(section_frame)
        info_frame.grid(row=1, column=0, sticky="w", pady=5)
        
        segments_label = ttk.Label(info_frame, 
                                   text=f"Segmentos: {', '.join([str(s.segment_id) for s in section.segments])}")
        segments_label.pack(side="left", padx=5)
        
        chars_label = ttk.Label(info_frame, text=f"Total: {section.get_total_chars():,} caracteres",
                               foreground="blue")
        chars_label.pack(side="left", padx=5)
        
        # Indicadores de estado
        status_frame = ttk.Frame(section_frame)
        status_frame.grid(row=2, column=0, sticky="w", pady=(5, 0))
        
        # Obtener tipos activos
        active_config = self.config_manager.get_active_set()
        active_types = active_config.get("active_types", {})
        
        type_icons = {
            "basic": ("📝", "Basic"),
            "multiple_choice": ("🔘", "Multiple"),
            "cloze": ("🔲", "Cloze"),
            "vocabulary": ("🔤", "Vocab"),
            "level_1_cloze": ("1️⃣", "L1"),
            "level_2_relations": ("2️⃣", "L2"),
            "level_3_application": ("3️⃣", "L3"),
            "level_4_analysis": ("4️⃣", "L4"),
            "atomic_extraction": ("⚛️", "Atomic")
        }
        
        status_labels = {}
        card_types_icons = [
            (card_type, *type_icons.get(card_type, ("❓", card_type[:6])))
            for card_type, is_active in active_types.items() if is_active
        ]
        
        for idx, (card_type, icon, label) in enumerate(card_types_icons):
            type_frame = ttk.Frame(status_frame)
            type_frame.grid(row=0, column=idx, padx=(0, 15))
            
            icon_label = ttk.Label(type_frame, text=icon, font=("Segoe UI", 9))
            icon_label.grid(row=0, column=0)
            
            state_label = tk.Label(type_frame, text="⬜", font=("Segoe UI", 9), fg="gray")
            state_label.grid(row=0, column=1, padx=2)
            
            count_label = ttk.Label(type_frame, text="", font=("Segoe UI", 8))
            count_label.grid(row=0, column=2)
            
            status_labels[card_type] = {
                "state": state_label,
                "count": count_label
            }
        
        # Guardar referencias
        self.video_section_widgets[section.section_id] = {
            "frame": section_frame,
            "title_label": title_label,
            "segments_label": segments_label,
            "chars_label": chars_label,
            "status_labels": status_labels,
            "section": section
        }
        
    def delete_video_section(self, section: VideoSection):
        """Elimina una sección de video específica."""
        if messagebox.askyesno("Confirmar", f"¿Eliminar {section.title}?"):
            # Eliminar widget
            widgets = self.video_section_widgets.get(section.section_id)
            if widgets:
                widgets["frame"].destroy()
                del self.video_section_widgets[section.section_id]
            
            # Eliminar de la lista de secciones
            if section in self.video_sections:
                self.video_sections.remove(section)
                self.video_log(f"🗑 Sección eliminada: {section.title}")
            
            # Reorganizar el grid
            self._reorganize_video_sections()
            
            # Deshabilitar botón de procesar si no quedan secciones
            if not self.video_sections:
                self.process_sections_btn.config(state="disabled")
            
    def _reorganize_video_sections(self):
        """Reorganiza las secciones de video en el grid tras eliminar una."""
        for idx, section in enumerate(self.video_sections):
            widgets = self.video_section_widgets.get(section.section_id)
            if widgets:
                widgets["frame"].grid(row=idx, column=0, sticky="ew", pady=5, padx=5)
    
    def process_video_sections(self):
        """Procesa todas las secciones de video con Gemini."""
        if not self.video_sections:
            messagebox.showwarning("Sin secciones", "No hay secciones creadas.")
            return
        
        if self.is_processing:
            messagebox.showwarning("En proceso", "Ya hay un procesamiento en curso.")
            return

        if not self._check_and_confirm_clear_pending_queue(mode="video"):
            return
        
        # Confirmar
        total_chars = sum(s.get_total_chars() for s in self.video_sections)
        msg = f"¿Procesar {len(self.video_sections)} sección(es)?\n\n"
        msg += f"Total de caracteres: {total_chars:,}\n\n"
        msg += "Esto realizará:\n"
        msg += "1. Procesamiento de transcripciones con Gemini OCR\n"
        msg += "2. Generación SECUENCIAL de flashcards\n"
        msg += "3. Importación automática a Anki\n\n"
        msg += "Nota: Este proceso puede tomar varios minutos."
        
        if not messagebox.askyesno("Confirmar procesamiento", msg):
            return
        
        # Resetear indicadores
        self._reset_all_video_status_indicators()
        
        # Iniciar procesamiento en thread
        self.is_processing = True
        self.process_sections_btn.config(state="disabled", text="⏳ Procesando...")
        
        # Extraer string de tkinter en el hilo principal para evitar vacíos o bloqueos
        bisabuelo_str = self.great_grandparent_deck.get().strip()
        grandparent_str = self.grandparent_deck.get().strip()
        mode_str = self.extraction_mode_video.get()
        use_source = self.use_source_context_var.get()
        source_duration = self.source_segment_duration_var.get()
        
        thread = threading.Thread(target=self._process_video_sections_thread, 
                                  args=(bisabuelo_str, grandparent_str, mode_str, use_source, source_duration), 
                                  daemon=True)
        thread.start()
    
    def _process_video_sections_thread(self, bisabuelo_str, grandparent_str, mode_str, use_source=False, source_duration=5.0):
        """Thread de procesamiento de secciones de video."""
        try:
            # Obtener configuración activa
            active_config = self.config_manager.get_active_set()
            
            # Inicializar o actualizar generador
            if not self.flashcard_generator:
                self.flashcard_generator = GeminiFlashcardGenerator(
                    log_callback=self.video_log,
                    config_set=active_config
                )
            else:
                self.flashcard_generator.log_callback = self.video_log
                self.flashcard_generator.update_config(active_config)
            
            self.video_log(f"\n📋 Usando configuración: {active_config.get('name', 'Por Defecto')}")
            self.video_log(f"   Modelo: {self.flashcard_generator.model_name}")
            
            # ============================================================
            # PASO 0: Generar Fuente de Consulta (si el switch está activo)
            # ============================================================
            full_context = ""
            if use_source and self.current_video_path and os.path.exists(self.current_video_path):
                self.video_log(f"\n📋 'Usar Fuente Completa' ACTIVADO — Generando transcripción fiel del material completo...")
                self.video_log(f"   Duración de segmento de fuente: {source_duration} min")
                
                session_dir = getattr(self, 'current_video_session', None)
                full_context = self.video_processor.generate_faithful_source_transcription(
                    media_path=self.current_video_path,
                    segment_duration_min=source_duration,
                    on_progress=self.video_log,
                    session_dir=session_dir
                )
                
                if full_context:
                    self.current_source_context = full_context
                    self.video_log(f"✅ Fuente de consulta lista: {len(full_context):,} caracteres")
                else:
                    self.video_log(f"⚠️ No se pudo generar la fuente de consulta. Continuando sin ella.")
            elif use_source:
                self.video_log(f"⚠️ 'Usar Fuente Completa' activado pero no hay video cargado. Continuando sin fuente.")
            
            total_flashcards = 0
            
            # Procesar cada sección
            for idx, section in enumerate(self.video_sections, 1):
                self.video_log(f"\n{'='*60}")
                self.video_log(f"📁 PROCESANDO SECCIÓN {idx}/{len(self.video_sections)}: {section.title}")
                self.video_log(f"{'='*60}")
                self.video_log(f"   📄 Segmentos: {section.get_segment_count()}")
                self.video_log(f"   📝 Caracteres: {section.get_total_chars():,}")
                if full_context:
                    self.video_log(f"   📋 Fuente de consulta: {len(full_context):,} chars adjuntados")
                
                # Construir deck_prefix para esta sección (Bisabuelo::Abuelo::Sección)
                deck_prefix = ""
                if bisabuelo_str:
                    deck_prefix += f"{bisabuelo_str}::"
                if grandparent_str:
                    deck_prefix += f"{grandparent_str}::"
                deck_prefix += f"{section.title}"
                
                # Obtener modo de procesamiento (pasado como argumento seguro)
                mode = mode_str
                
                # Procesar sección con Gemini (Multimodal o Estándar)
                if mode == "Generación Directa (Multimodal)":
                    # Obtener rutas de video/audio originales
                    video_paths = [seg.audio_path for seg in section.segments if seg.audio_path]
                    if not video_paths:
                        self.video_log(f"⚠️ No hay archivos de video/audio originales en esta sección")
                        continue
                        
                    result = self.flashcard_generator.process_video_section_multimodal(
                        section_title=section.title,
                        video_paths=video_paths,
                        converter=self.converter,
                        anki_manager=self.anki_manager,
                        deck_prefix=deck_prefix,
                        session_path=getattr(self, 'current_video_session', None),
                        full_context=full_context
                    )
                else:
                    # Modo Estándar (Transcripciones)
                    transcription_paths = section.get_transcription_paths()
                    if not transcription_paths:
                        self.video_log(f"⚠️ No hay transcripciones en esta sección")
                        continue
                        
                    result = self.flashcard_generator.process_video_section(
                        section_title=section.title,
                        transcription_paths=transcription_paths,
                        converter=self.converter,
                        anki_manager=self.anki_manager,
                        deck_prefix=deck_prefix,
                        session_path=getattr(self, 'current_video_session', None),
                        full_context=full_context
                    )
                
                if result.get("success"):
                    self.video_log(f"\n   ⏳ FLASHCARDS EN SALA DE ESPERA:")
                    import_results = result.get("results", {})
                    for card_type, card_result in import_results.items():
                        if card_result.get("success"):
                            count = card_result.get("count", 0)
                            flashcards = card_result.get("flashcards", [])
                            deck_name = card_result.get("deck", "")
                            total_flashcards += count
                            self.video_log(f"      • {card_type}: {count} tarjetas en espera → {deck_name}")
                            # Acumular en Sala de Espera para deduplicación
                            if flashcards and deck_name:
                                deck_path = self._get_deck_with_type_label(deck_name, card_type)
                                self.pending_flashcard_imports.append({
                                    "deck_name": deck_path,
                                    "card_type": card_type,
                                    "flashcards": flashcards
                                })
                            self.root.after(0, lambda sid=section.section_id, ct=card_type, c=count:
                                          self._update_video_section_status(sid, ct, True, c))
                        else:
                            error_msg = card_result.get("error", "Error desconocido")
                            self.video_log(f"      ❌ {card_type}: Fallo - {error_msg}")
                            self.root.after(0, lambda sid=section.section_id, ct=card_type:
                                          self._update_video_section_status(sid, ct, False, 0))
                else:
                    self.video_log(f"\n   ❌ SECCIÓN FALLIDA: {result.get('error', 'Error desconocido')}")
            
            self.video_log(f"\n{'='*60}")
            self.video_log(f"⏳ GENERACIÓN COMPLETADA — PENDIENTE DE REVISIÓN")
            self.video_log(f"   • Secciones procesadas: {len(self.video_sections)}")
            self.video_log(f"   • Total flashcards en sala de espera: {total_flashcards}")
            self.video_log(f"   → Usa '🧠 Filtrar Interferencia (IA)' para revisar duplicados")
            self.video_log(f"   → Luego '✅ Ejecutar Sincronización' para importar a Anki")
            self.video_log(f"{'='*60}\n")
            
            self._save_pending_queue()
            self.root.after(0, self._update_pending_button)
            
            # Mostrar popup
            self.root.after(0, lambda: messagebox.showinfo(
                "✅ Generación completada",
                f"Secciones procesadas: {len(self.video_sections)}\n"
                f"Flashcards en sala de espera: {total_flashcards}\n\n"
                f"Presiona '🧠 Filtrar Interferencia (IA)' para revisar duplicados\n"
                f"y luego '✅ Ejecutar Sincronización' para importar a Anki."
            ))
            
        except Exception as e:
            error_msg = str(e)
            self.video_log(f"\n❌ ERROR CRÍTICO: {error_msg}")
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda msg=error_msg: messagebox.showerror(
                "Error", f"Error durante el procesamiento:\n{msg}"))
        
        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.process_sections_btn.config(
                state="normal", text="🚀 Procesar Secciones"
            ))
    
    def _update_video_section_status(self, section_id: int, card_type: str, success: bool, count: int):
        """Actualiza el indicador visual de estado de una sección de video."""
        widgets = self.video_section_widgets.get(section_id)
        if not widgets or "status_labels" not in widgets:
            return
        
        status_labels = widgets["status_labels"]
        if card_type not in status_labels:
            return
        
        state_label = status_labels[card_type]["state"]
        count_label = status_labels[card_type]["count"]
        
        if success:
            state_label.config(text="✅", fg="green")
            count_label.config(text=str(count))
        else:
            state_label.config(text="❌", fg="red")
            count_label.config(text="")
    
    def _reset_all_video_status_indicators(self):
        """Resetea todos los indicadores de estado de video."""
        for section_id, widgets in self.video_section_widgets.items():
            if "status_labels" not in widgets:
                continue
            
            for card_type, labels in widgets["status_labels"].items():
                labels["state"].config(text="⬜", fg="gray")
                labels["count"].config(text="")
                
    def refresh_all_section_indicators(self):
        """Actualiza la UI de TODAS las secciones para reflejar la configuración activa actual de flashcards."""
        active_config = self.config_manager.get_active_set()
        active_types = active_config.get("active_types", {})
        
        type_icons = {
            "basic": ("📝", "Basic"),
            "multiple_choice": ("🔘", "Multiple"),
            "cloze": ("🔲", "Cloze"),
            "vocabulary": ("🔤", "Vocab"),
            "level_1_cloze": ("1️⃣", "L1"),
            "level_2_relations": ("2️⃣", "L2"),
            "level_3_application": ("3️⃣", "L3"),
            "level_4_analysis": ("4️⃣", "L4"),
            "atomic_extraction": ("⚛️", "Atomic")
        }
        
        card_types_icons = [
            (card_type, *type_icons.get(card_type, ("❓", card_type[:6])))
            for card_type, is_active in active_types.items() if is_active
        ]
        
        # Refrescar todas las secciones que tengan indicadores
        for widgets_dict in (self.video_section_widgets, self.section_widgets, 
                             self.text_section_widgets, self.book_section_widgets, 
                             self.audio_section_widgets):
            for section_id, widgets in widgets_dict.items():
                if "status_labels" not in widgets or not widgets["status_labels"]:
                    continue
                    
                first_val = next(iter(widgets["status_labels"].values()))
                if not isinstance(first_val, dict) or "state" not in first_val:
                    continue
                    
                status_frame = first_val["state"].master.master
                
                # Limpiar componentes antiguos
                for child in status_frame.winfo_children():
                    child.destroy()
                
                # Crear los nuevos indicadores según la config activa
                new_status_labels = {}
                for idx, (card_type, icon, label) in enumerate(card_types_icons):
                    type_frame = ttk.Frame(status_frame)
                    type_frame.grid(row=0, column=idx, padx=(0, 15))
                    
                    icon_label = ttk.Label(type_frame, text=icon, font=("Segoe UI", 9))
                    icon_label.grid(row=0, column=0)
                    
                    state_label = tk.Label(type_frame, text="⬜", font=("Segoe UI", 9), fg="gray")
                    state_label.grid(row=0, column=1, padx=2)
                    
                    count_label = ttk.Label(type_frame, text="", font=("Segoe UI", 8))
                    count_label.grid(row=0, column=2)
                    
                    new_status_labels[card_type] = {
                        "state": state_label,
                        "count": count_label
                    }
                
                # Actualizar las referencias internas del widget
                widgets["status_labels"] = new_status_labels

    def _toggle_source_duration_visibility(self):
        """Muestra u oculta el spinbox de duración de fuente según el checkbox."""
        if self.use_source_context_var.get():
            self.source_duration_label.grid(row=1, column=0, sticky="w", padx=5, pady=2)
            self.source_duration_spinbox.grid(row=1, column=1, sticky="w", padx=5, pady=2)
            self.source_duration_info.grid(row=2, column=0, columnspan=3, sticky="w", padx=5)
        else:
            self.source_duration_label.grid_forget()
            self.source_duration_spinbox.grid_forget()
            self.source_duration_info.grid_forget()

    def clear_video_mode(self):
        """Limpia todo el modo video."""
        if not self.current_video_segments and not self.video_sections:
            return
        
        if messagebox.askyesno("Confirmar", "¿Limpiar todo el modo video?\n\nEsto eliminará segmentos y secciones."):
            # Limpiar segmentos
            self.current_video_path = None
            self.current_video_segments.clear()
            for widget in self.segments_inner_frame.winfo_children():
                widget.destroy()
            self.video_segment_widgets.clear()
            
            # Limpiar secciones
            self.video_sections.clear()
            for widget in self.video_sections_inner_frame.winfo_children():
                widget.destroy()
            self.video_section_widgets.clear()
            
            # Resetear UI
            self.video_info_label.config(text="")
            self.process_video_btn.config(state="disabled")
            self.create_sections_btn.config(state="disabled")
            self.process_sections_btn.config(state="disabled")
            self.hierarchy_counter = 0
            
            # Restaurar vista de arrastrar/cargar video
            if hasattr(self, 'video_drop_frame'):
                self.video_drop_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(15, 15))
            if hasattr(self, 'change_video_btn'):
                self.change_video_btn.pack_forget()
            if hasattr(self, 'view_segments_btn'):
                self.view_segments_btn.config(state="disabled")
                
            # Ocultar popup de segmentos si está abierto
            if self.segments_window:
                self.hide_segments_window()
            
            self.video_log("🗑 Modo video limpiado")
    
    def upload_video(self):
        """Método antiguo - redirige al nuevo método."""
        self.upload_video_for_processing()
    
    def clear_videos(self):
        """Método antiguo - redirige al nuevo método."""
        self.clear_video_mode()
    
    def process_videos(self):
        """Método antiguo - redirige al nuevo método."""
        self.process_video_complete()
    
    def _add_video_to_list(self, video_path: str):
        """Método antiguo - ya no se usa."""
        pass
    
    def _remove_video(self, video_path: str, frame: ttk.Frame):
        """Método antiguo - ya no se usa."""
        pass
    
    def log(self, message: str):
        """Añade un mensaje al log del modo normal."""
        self.ui_queue.put({"type": "log", "target": "normal", "message": message})

    def check_anki_status(self):
        """Verifica el estado de Anki."""
        def check():
            is_running = self.anki_manager._check_anki_status()
            if is_running:
                self.status_label.config(text="✓ Anki is running", foreground="green")
                self.log("✓ Anki is running")
            else:
                self.status_label.config(text="✗ Anki is not running", foreground="red")
                self.log("✗ Anki is not running. Trying to start...")
                success, msg = self.anki_manager.ensure_anki_running()
                if success:
                    self.status_label.config(text="✓ Anki started", foreground="green")
                    self.log(f"✓ {msg}")
                else:
                    self.log(f"✗ {msg}")
        
        thread = threading.Thread(target=check, daemon=True)
        thread.start()
    
    def convert_and_import(self):
        """Convierte y importa los flashcards a Anki."""
        def process():
            try:
                self.log("\n" + "="*50)
                self.log("Starting conversion and import...")
                
                total_imported = 0
                
                for card_type, card_label in self.CARD_TYPES.items():
                    text = self.text_widgets[card_type].get("1.0", "end-1c").strip()
                    
                    if not text:
                        self.log(f"⊘ {card_label}: No input")
                        continue
                    
                    self.log(f"\n→ Processing {card_label}...")
                    self.log(f"  Input length: {len(text)} chars")
                    
                    # Convertir a TSV
                    tsv_content = self.converter.convert(text, card_type)
                    
                    if not tsv_content:
                        self.log(f"✗ {card_label}: No flashcards parsed")
                        continue
                    
                    # Parsear flashcards
                    flashcards = []
                    lines = tsv_content.strip().split('\n')
                    
                    for line in lines:
                        if '\t' in line:
                            front, back = line.split('\t', 1)
                            flashcards.append({"front": front.strip(), "back": back.strip()})
                    
                    # Importar a Anki (Pausa por Deduplicación)
                    prefix = self.prefix_var.get().strip() or "Flashcards"
                    deck_name = f"{prefix} - {card_label}"
                    
                    self.pending_flashcard_imports.append({
                        "deck_name": deck_name,
                        "card_type": card_type,
                        "flashcards": flashcards
                    })
                    success = True
                    count = len(flashcards)
                    
                    if success:
                        self.log(f"✓ Puestas en cola de espera: {count} tarjetas")
                        total_imported += count
                    else:
                        self.log(f"✗ {msg}")
                
                self.log(f"\n{'='*50}")
                self.log(f"✓ Total en sala de espera: {total_imported} flashcards")
                self.root.after(0, self._update_pending_button)
                messagebox.showinfo("Sala de Espera", 
                                   f"Se han enviado {total_imported} flashcards a la Sala de Espera.\n\n"
                                   "Ve a la pestaña de 'Sincronización' para revisarlas e importarlas.")
                
            except Exception as e:
                self.log(f"✗ Error: {str(e)}")
                messagebox.showerror("Error", f"Error during import: {str(e)}")
        
        thread = threading.Thread(target=process, daemon=True)
        thread.start()

    def export_tsv(self):
        """Exporta los flashcards como TSV."""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".tsv",
                filetypes=[("TSV files", "*.tsv"), ("All files", "*.*")]
            )
            
            if not file_path:
                return
            
            with open(file_path, 'w', encoding='utf-8') as f:
                for card_type, card_label in self.CARD_TYPES.items():
                    text = self.text_widgets[card_type].get("1.0", "end-1c").strip()
                    
                    if text:
                        tsv_content = self.converter.convert(text, card_type)
                        if tsv_content:
                            f.write(f"# {card_label}\n")
                            f.write(tsv_content)
                            f.write("\n\n")
            
            self.log(f"✓ Exported to {file_path}")
            messagebox.showinfo("Success", f"Exported to {file_path}")
        
        except Exception as e:
            self.log(f"✗ Export error: {str(e)}")
            messagebox.showerror("Error", f"Export error: {str(e)}")
    
    def clear_all(self):
        """Limpia todas las cajitas de texto."""
        for text_widget in self.text_widgets.values():
            text_widget.delete("1.0", "end")
        self.log("✓ All fields cleared")
    
    def count_flashcards(self, card_type: str, card_label: str):
        """Cuenta las flashcards en una cajita específica."""
        text = self.text_widgets[card_type].get("1.0", "end-1c").strip()
        
        if not text:
            messagebox.showinfo("Count Result", f"{card_label}\n\nNo flashcards found (empty input)")
            return
        
        try:
            tsv_content = self.converter.convert(text, card_type)
            
            if not tsv_content:
                messagebox.showinfo("Count Result", f"{card_label}\n\nNo flashcards parsed (0 cards)")
                return
            
            tsv_lines = [line for line in tsv_content.strip().split('\n') if line.strip()]
            flashcard_count = len(tsv_lines)
            
            messagebox.showinfo("Count Result", f"{card_label}\n\nTotal flashcards: {flashcard_count}")
            self.log(f"ℹ {card_label}: {flashcard_count} flashcards counted")
            
        except Exception as e:
            messagebox.showerror("Count Error", f"Error counting flashcards:\n{str(e)}")

    def show_bulk_text_segmentation_dialog(self):
        """Muestra un diálogo para pegar un bloque grande de texto y segmentarlo."""
        dialog = tk.Toplevel(self.root)
        dialog.title("📄 Pegar y Segmentar Texto")
        # Ajustar tamaño y centrar
        dialog.geometry("800x600")
        dialog.transient(self.root)
        dialog.grab_set()
        
        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.pack(fill="both", expand=True)
        
        ttk.Label(main_frame, text="Pega aquí el texto completo (de YouTube, GitHub, Blogs, etc.):", 
                  font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 5))
        
        text_area = tk.Text(main_frame, height=15, wrap="word", font=("Consolas", 10))
        text_area.pack(fill="both", expand=True, pady=5)
        
        # Opciones de segmentación
        config_frame = ttk.LabelFrame(main_frame, text="⚙️ Configuración de Segmentación", padding="10")
        config_frame.pack(fill="x", pady=10)
        
        # Tamaño de fragmento
        ttk.Label(config_frame, text="Tamaño del Fragmento (caracteres):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        chunk_size_var = tk.IntVar(value=3000)
        ttk.Spinbox(config_frame, from_=500, to=20000, increment=500, textvariable=chunk_size_var, width=10).grid(row=0, column=1, sticky="w")
        
        # Overlap
        ttk.Label(config_frame, text="Solape / Overlap (caracteres):").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        overlap_var = tk.IntVar(value=300)
        ttk.Spinbox(config_frame, from_=0, to=2000, increment=50, textvariable=overlap_var, width=10).grid(row=1, column=1, sticky="w")
        
        # Chunks por sección
        ttk.Label(config_frame, text="Fragmentos por Sección:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        chunks_per_section_var = tk.IntVar(value=2)
        ttk.Spinbox(config_frame, from_=1, to=10, textvariable=chunks_per_section_var, width=10).grid(row=2, column=1, sticky="w")
        
        def start_segmentation():
            full_text = text_area.get("1.0", "end-1c").strip()
            if not full_text:
                messagebox.showwarning("Texto vacío", "Por favor pega algún texto para segmentar.")
                return
            
            size = chunk_size_var.get()
            overlap = overlap_var.get()
            per_section = chunks_per_section_var.get()
            
            if size <= overlap:
                messagebox.showerror("Error", "El tamaño del fragmento debe ser mayor al solape.")
                return
            
            # Realizar segmentación
            self.segment_text_into_sections(full_text, size, overlap, per_section)
            dialog.destroy()
            
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Button(btn_frame, text="✨ Segmentar y Cargar", command=start_segmentation).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side="right", padx=5)

    def segment_text_into_sections(self, text, chunk_size, overlap, chunks_per_section):
        """Segmenta el texto en trozos con overlap y los agrupa en secciones."""
        self.text_log("📄 Iniciando segmentación de texto...")
        
        # 0. Crear sesión para guardado jerárquico
        bisabuelo = self.great_grandparent_deck.get().strip()
        grandparent = self.grandparent_deck.get().strip() or "General"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if bisabuelo:
            self.current_text_session = os.path.join(MASTER_FOLDER, bisabuelo, grandparent, f"Session_{timestamp}")
        else:
            self.current_text_session = os.path.join(MASTER_FOLDER, grandparent, f"Session_{timestamp}")
        
        # Guardar texto original completo
        if getattr(self, 'flashcard_generator', None) is None:
              # Usar el generador global

              active_config = self.config_manager.get_active_set()
              self.flashcard_generator = GeminiFlashcardGenerator(log_callback=self.text_log, config_set=active_config)

        self.flashcard_generator._save_ocr_transcript(
            text, self.current_text_session, "original_full_text", subfolder="original_text"
        )

        # 1. Crear los fragments (chunks)
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk = text[start:end]
            chunks.append(chunk)
            
            # Guardar cada chunk individualmente
            self.flashcard_generator._save_ocr_transcript(
                chunk, self.current_text_session, f"chunk_{len(chunks)}", subfolder="chunks"
            )
            
            if end >= text_len:
                break
            
            # El siguiente inicio es el fin actual menos el solape
            start = end - overlap
            # Si por solape no avanzamos, forzamos avance de 1 caracter para evitar loop infinito
            if start <= (end - chunk_size):
                start = end + 1
            
        self.text_log(f"✅ Texto dividido en {len(chunks)} fragmentos.")
        
        # 2. Agrupar chunks en secciones
        created_count = 0
        for i in range(0, len(chunks), chunks_per_section):
            # Obtener el grupo de chunks para esta sección
            group = chunks[i:i + chunks_per_section]
            # Combinar con un separador claro
            section_content = "\n\n--- SIGUIENTE FRAGMENTO ---\n\n".join(group)
            
            # Crear y añadir la sección
            self.text_section_counter += 1
            self.hierarchy_counter += 1
            
            new_section = TextSection(self.text_section_counter)
            new_section.set_text(section_content)
            
            # Título dinámico respetando prefijo si existe
            prefix = self.parent_prefix.get().strip()
            chunk_range = f"{i+1}-{min(i + chunks_per_section, len(chunks))}"
            if prefix:
                new_section.title = f"{prefix} {self.hierarchy_counter} (Frags {chunk_range})"
            else:
                new_section.title = f"Sección {self.text_section_counter} (Frags {chunk_range})"
            
            self.text_sections.append(new_section)
            
            # Crear el widget visual
            self._create_text_section_widget(new_section)
            
            # Poblar el widget de texto inmediatamente
            widgets = self.text_section_widgets.get(new_section.section_id)
            if widgets:
                text_widget = widgets["text_widget"]
                text_widget.delete("1.0", "end")
                text_widget.insert("1.0", section_content)
                widgets["info_label"].config(text=f"{len(section_content):,} caracteres")
            
            created_count += 1
            
        self.text_log(f"📚 Creadas {created_count} secciones de texto automáticamente.")
        messagebox.showinfo("Segmentación completada", 
                            f"Se han creado {created_count} secciones a partir de {len(chunks)} fragmentos.\nArchivos guardados en: {self.current_text_session}")

    # ==================== SISTEMA DE SESIONES ====================
    
    def _save_current_session(self):
        """Guarda la sesión actual automáticamente."""
        if not self.sections or not any(s.images for s in self.sections):
            return  # No guardar si no hay secciones con imágenes
        
        try:
            # Cargar sesiones existentes
            sessions = self._load_sessions()
            
            # Crear datos de la sesión actual
            first_section_title = self.sections[0].title if self.sections else "Sin título"
            session_data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "great_grandparent": self.great_grandparent_deck.get(),
                "grandparent": self.grandparent_deck.get(),
                "father_prefix": self.parent_prefix.get(),
                "first_section": first_section_title,
                "num_sections": len(self.sections),
                "sections": []
            }
            
            for section in self.sections:
                section_info = {
                    "title": section.title,
                    "images": [img["path"] for img in section.images]
                }
                session_data["sections"].append(section_info)
            
            # Añadir al inicio de la lista
            sessions.insert(0, session_data)
            
            # Mantener solo las últimas 10
            sessions = sessions[:10]
            
            # Guardar
            with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)
            
            self.auto_log(f"💾 Sesión guardada: {session_data['timestamp']} - {first_section_title}")
            
        except Exception as e:
            self.auto_log(f"⚠️ Error guardando sesión: {e}")

    def _save_current_book_session(self):
        """Guarda la sesión actual de libros automáticamente."""
        if not self.book_sections:
            return
            
        try:
            sessions = []
            if os.path.exists(BOOK_SESSIONS_FILE):
                with open(BOOK_SESSIONS_FILE, 'r', encoding='utf-8') as f:
                    sessions = json.load(f)
            
            # Crear datos de la sesión
            first_title = self.book_sections[0].title if self.book_sections else "Sin título"
            session_data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "great_grandparent": self.great_grandparent_deck.get(),
                "grandparent": self.grandparent_deck.get(),
                "father_prefix": self.parent_prefix.get(),
                "book_path": self.book_path_var.get(),
                "num_sections": len(self.book_sections),
                "sections": []
            }
            
            for section in self.book_sections:
                section_info = {
                    "title": section.title,
                    "section_id": section.section_id,
                    "images": [img["path"] for img in section.images],
                    "pdf_segment_path": getattr(section, 'pdf_segment_path', None),
                    "text": getattr(section, 'text', None)
                }
                session_data["sections"].append(section_info)
                
            sessions.insert(0, session_data)
            sessions = sessions[:10]  # Max 10
            
            with open(BOOK_SESSIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)
                
            self.book_log(f"💾 Sesión de libro guardada: {session_data['timestamp']}")
        except Exception as e:
            self.book_log(f"⚠️ Error guardando sesión de libro: {e}")
    
    def _save_current_text_session(self):
        """Guarda la sesión actual de texto automáticamente."""
        if not self.text_sections or not any(s.get_text().strip() for s in self.text_sections):
            return  # No guardar si no hay secciones con texto
        
        try:
            # Cargar sesiones existentes
            sessions = self._load_text_sessions()
            
            # Crear datos de la sesión actual
            first_section_title = self.text_sections[0].title if self.text_sections else "Sin título"
            session_data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "great_grandparent": self.great_grandparent_deck.get(),
                "grandparent": self.grandparent_deck.get(),
                "father_prefix": self.parent_prefix.get(),
                "first_section": first_section_title,
                "num_sections": len(self.text_sections),
                "flashcard_session_path": getattr(self, 'current_text_session', None),
                "sections": []
            }
            
            for section in self.text_sections:
                section_info = {
                    "title": section.title,
                    "text": section.get_text()
                }
                session_data["sections"].append(section_info)
            
            # Añadir al inicio de la lista
            sessions.insert(0, session_data)
            
            # Mantener solo las últimas 10
            sessions = sessions[:10]
            
            # Guardar
            with open(TEXT_SESSIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)
            
            self.text_log(f"💾 Sesión de texto guardada: {session_data['timestamp']} - {first_section_title}")
            
        except Exception as e:
            self.text_log(f"⚠️ Error guardando sesión de texto: {e}")
    
    def _load_sessions(self) -> list:
        """Carga las sesiones guardadas."""
        try:
            if os.path.exists(SESSIONS_FILE):
                with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _load_text_sessions(self) -> list:
        """Carga las sesiones de texto guardadas."""
        try:
            if os.path.exists(TEXT_SESSIONS_FILE):
                with open(TEXT_SESSIONS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return []
    
    def show_recover_session_dialog(self):
        """Muestra el diálogo para recuperar una sesión."""
        sessions = self._load_sessions()
        
        if not sessions:
            messagebox.showinfo("Sin sesiones", "No hay sesiones guardadas para recuperar.")
            return
        
        # Crear ventana de diálogo
        dialog = tk.Toplevel(self.root)
        dialog.title("Recuperar Sesión")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centrar ventana
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 500) // 2
        y = (dialog.winfo_screenheight() - 400) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Título
        ttk.Label(dialog, text="Selecciona una sesión para recuperar:", 
                  font=("Segoe UI", 11, "bold")).pack(pady=10)
        
        # Lista de sesiones
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        listbox = tk.Listbox(list_frame, font=("Segoe UI", 10), 
                            yscrollcommand=scrollbar.set, height=12)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Poblar lista
        for idx, session in enumerate(sessions):
            timestamp = session.get("timestamp", "?")
            ggp = session.get("great_grandparent", "N/A")
            gp = session.get("grandparent", "N/A")
            prefix = session.get("father_prefix", "N/A")
            num_sec = session.get("num_sections", len(session.get("sections", [])))
            total_images = sum(len(s.get("images", [])) for s in session.get("sections", []))
            
            display_text = f"[{timestamp}] {ggp} > {gp} > {prefix} ({num_sec} partes, {total_images} imgs)"
            listbox.insert(tk.END, display_text)
        
        # Seleccionar primera por defecto
        listbox.selection_set(0)
        
        # Frame de botones
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        selected_session = [None]  # Usar lista para poder modificar en closure
        
        def on_replace():
            idx = listbox.curselection()
            if idx:
                selected_session[0] = sessions[idx[0]]
                dialog.destroy()
                self._recover_session(selected_session[0], replace=True)
        
        def on_add():
            idx = listbox.curselection()
            if idx:
                selected_session[0] = sessions[idx[0]]
                dialog.destroy()
                self._recover_session(selected_session[0], replace=False)
        
        def on_cancel():
            dialog.destroy()
        
        def on_delete():
            idx = listbox.curselection()
            if idx:
                if messagebox.askyesno("Confirmar", "¿Eliminar esta sesión guardada?"):
                    sessions.pop(idx[0])
                    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(sessions, f, ensure_ascii=False, indent=2)
                    listbox.delete(idx[0])
                    if not sessions:
                        dialog.destroy()
                        messagebox.showinfo("Info", "No quedan sesiones guardadas.")
        
        ttk.Button(btn_frame, text="🔄 Reemplazar", command=on_replace).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="➕ Añadir", command=on_add).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="🗑 Eliminar", command=on_delete).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="❌ Cancelar", command=on_cancel).pack(side="right", padx=5)
        
        # Info de la sesión seleccionada
        info_frame = ttk.LabelFrame(dialog, text="Detalles de la sesión")
        info_frame.pack(fill="x", padx=10, pady=5)
        
        info_label = ttk.Label(info_frame, text="", wraplength=450)
        info_label.pack(padx=5, pady=5)
        
        def on_select(event):
            idx = listbox.curselection()
            if idx:
                session = sessions[idx[0]]
                sections_info = []
                for s in session.get("sections", []):
                    title = s.get("title", "?")
                    imgs = len(s.get("images", []))
                    sections_info.append(f"• {title} ({imgs} imgs)")
                info_label.config(text="\n".join(sections_info[:5]) + 
                                 ("\n..." if len(sections_info) > 5 else ""))
        
        listbox.bind("<<ListboxSelect>>", on_select)
        on_select(None)  # Mostrar info de la primera
    
    def show_recover_text_session_dialog(self):
        """Muestra el diálogo para recuperar una sesión de texto."""
        sessions = self._load_text_sessions()
        
        if not sessions:
            messagebox.showinfo("Sin sesiones", "No hay sesiones de texto guardadas para recuperar.")
            return
        
        # Crear ventana de diálogo
        dialog = tk.Toplevel(self.root)
        dialog.title("Recuperar Sesión de Texto")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centrar ventana
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 500) // 2
        y = (dialog.winfo_screenheight() - 400) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Título
        ttk.Label(dialog, text="Selecciona una sesión de texto para recuperar:", 
                  font=("Segoe UI", 11, "bold")).pack(pady=10)
        
        # Lista de sesiones
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        listbox = tk.Listbox(list_frame, font=("Segoe UI", 10), 
                            yscrollcommand=scrollbar.set, height=12)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Poblar lista
        for idx, session in enumerate(sessions):
            timestamp = session.get("timestamp", "?")
            ggp = session.get("great_grandparent", "N/A")
            gp = session.get("grandparent", "N/A")
            prefix = session.get("father_prefix", "N/A")
            num_sec = session.get("num_sections", len(session.get("sections", [])))
            
            display_text = f"[{timestamp}] {ggp} > {gp} > {prefix} ({num_sec} partes)"
            listbox.insert(tk.END, display_text)
        
        # Seleccionar primera por defecto
        listbox.selection_set(0)
        
        # Frame de botones
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        selected_session = [None]
        
        def on_replace():
            idx = listbox.curselection()
            if idx:
                selected_session[0] = sessions[idx[0]]
                dialog.destroy()
                self._recover_text_session(selected_session[0], replace=True)
        
        def on_add():
            idx = listbox.curselection()
            if idx:
                selected_session[0] = sessions[idx[0]]
                dialog.destroy()
                self._recover_text_session(selected_session[0], replace=False)
        
        def on_cancel():
            dialog.destroy()
        
        def on_delete():
            idx = listbox.curselection()
            if idx:
                if messagebox.askyesno("Confirmar", "¿Eliminar esta sesión de texto guardada?"):
                    sessions.pop(idx[0])
                    with open(TEXT_SESSIONS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(sessions, f, ensure_ascii=False, indent=2)
                    listbox.delete(idx[0])
                    if not sessions:
                        dialog.destroy()
                        messagebox.showinfo("Info", "No quedan sesiones guardadas.")
        
        ttk.Button(btn_frame, text="🔄 Reemplazar", command=on_replace).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="➕ Añadir", command=on_add).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="🗑 Eliminar", command=on_delete).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="❌ Cancelar", command=on_cancel).pack(side="right", padx=5)
        
        # Info de la sesión seleccionada
        info_frame = ttk.LabelFrame(dialog, text="Detalles de la sesión")
        info_frame.pack(fill="x", padx=10, pady=5)
        
        info_label = ttk.Label(info_frame, text="", wraplength=450)
        info_label.pack(padx=5, pady=5)
        
        def on_select(event):
            idx = listbox.curselection()
            if idx:
                session = sessions[idx[0]]
                sections_info = []
                for s in session.get("sections", []):
                    title = s.get("title", "?")
                    text_len = len(s.get("text", ""))
                    sections_info.append(f"• {title} ({text_len:,} caracteres)")
                info_label.config(text="\n".join(sections_info[:5]) + 
                                 ("\n..." if len(sections_info) > 5 else ""))
        
        listbox.bind("<<ListboxSelect>>", on_select)
        on_select(None)
    
    def _recover_text_session(self, session_data: dict, replace: bool):
        """Recupera una sesión de texto guardada."""
        # --- NUEVO: Inicializar la ruta de la sesión al inicio para evitar que auto-guardado lo ponga a null ---
        fc_path = session_data.get("flashcard_session_path", "")
        if not fc_path:
            # Fallback de resolución de ruta por timestamp para sesiones antiguas
            ggp = session_data.get("great_grandparent", "").strip()
            gp = session_data.get("grandparent", "").strip() or "General"
            if ggp:
                base_dir = os.path.join(MASTER_FOLDER, ggp, gp)
            else:
                base_dir = os.path.join(MASTER_FOLDER, gp)
            ts = session_data.get("timestamp", "")
            if ts and len(ts) >= 16:
                try:
                    clean_ts = ts.replace("-", "").replace(" ", "_").replace(":", "")[:13]
                    if os.path.exists(base_dir):
                        for item in os.listdir(base_dir):
                            if item.startswith(f"Session_{clean_ts}"):
                                fc_path = os.path.join(base_dir, item)
                                break
                except Exception:
                    pass
        
        if fc_path:
            self.current_text_session = fc_path

        # Restaurar configuración de jerarquía si existe
        if "great_grandparent" in session_data:
            self.great_grandparent_deck.set(session_data["great_grandparent"])
        if "grandparent" in session_data:
            self.grandparent_deck.set(session_data["grandparent"])
        if "father_prefix" in session_data:
            self.parent_prefix.set(session_data["father_prefix"])
            
        if replace:
            # Limpiar secciones actuales
            for section_id, widgets in list(self.text_section_widgets.items()):
                widgets["frame"].destroy()
            self.text_section_widgets.clear()
            self.text_sections.clear()
            self.text_section_counter = 0
            self.hierarchy_counter = 0
            
            # Limpiar cola de pendientes al recuperar sesión de texto
            self.pending_flashcard_imports = []
            self._save_pending_queue()
            self._update_pending_button()
            self.text_log("🗑️ Sala de espera limpiada al recuperar una sesión de texto.")
        
        # Recuperar secciones
        recovered_count = 0
        
        for section_info in session_data.get("sections", []):
            title = section_info.get("title", f"Sección {self.text_section_counter + 1}")
            content = section_info.get("text", "")
            
            # Crear nueva sección
            self.text_section_counter += 1
            self.hierarchy_counter += 1
            section = TextSection(self.text_section_counter)
            section.title = title
            section.set_text(content)
            self.text_sections.append(section)
            self._create_text_section_widget(section)
            
            # Cargar el texto en el widget
            widgets = self.text_section_widgets.get(section.section_id)
            if widgets:
                text_widget = widgets["text_widget"]
                text_widget.insert("1.0", content)
                widgets["info_label"].config(text=f"{len(content):,} caracteres")
                # Actualizar título si fue personalizado
                widgets["title_label"].config(text=title)
                widgets["title_var"].set(title)
            
            recovered_count += 1
        
        # Mostrar resumen
        action = "Reemplazadas" if replace else "Añadidas"
        self.text_log(f"\n📂 {action} {recovered_count} secciones de texto desde sesión guardada")
        
        # --- NUEVO: Recargar flashcards generadas en la Sala de Espera ---
        if fc_path:
            self._load_flashcards_from_session(fc_path, session_data)
            self._save_pending_queue()
            self._update_pending_button()
    
    def show_recover_video_session_dialog(self):
        """Muestra el diálogo para recuperar una sesión de video."""
        temp_dir = getattr(self.video_processor, "TEMP_DIR", "temp_videos")
        
        sessions = []
        if os.path.exists(temp_dir):
            for d in sorted(os.listdir(temp_dir), reverse=True):
                if d.startswith("session_"):
                    meta_path = os.path.join(temp_dir, d, "metadata.json")
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, 'r', encoding='utf-8') as f:
                                meta = json.load(f)
                                meta["session_folder"] = os.path.join(temp_dir, d)
                                
                                # Leer vínculo de sesión jerárquica si existe
                                link_path = os.path.join(temp_dir, d, "session_link.json")
                                if os.path.exists(link_path):
                                    try:
                                        with open(link_path, 'r', encoding='utf-8') as lf:
                                            link_data = json.load(lf)
                                            meta["flashcard_session_path"] = link_data.get("flashcard_session_path", "")
                                            meta["great_grandparent"] = link_data.get("great_grandparent", meta.get("great_grandparent", ""))
                                            meta["grandparent"] = link_data.get("grandparent", meta.get("grandparent", ""))
                                            meta["father_prefix"] = link_data.get("father_prefix", meta.get("father_prefix", ""))
                                    except Exception:
                                        pass
                                sessions.append(meta)
                        except Exception as e:
                            self.video_log(f"⚠️ Error leyendo metadata de {d}: {e}")
        
        # Sort by creation date descending
        sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        if not sessions:
            messagebox.showinfo("Sin sesiones", "No hay sesiones de video guardadas para recuperar.")
            return
            
        # Crear ventana de diálogo
        dialog = tk.Toplevel(self.root)
        dialog.title("Recuperar Sesión de Video")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centrar ventana
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 600) // 2
        y = (dialog.winfo_screenheight() - 400) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Título
        ttk.Label(dialog, text="Selecciona una sesión de video para recuperar:", 
                  font=("Segoe UI", 11, "bold")).pack(pady=10)
        
        # Lista de sesiones
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        listbox = tk.Listbox(list_frame, font=("Segoe UI", 10), 
                            yscrollcommand=scrollbar.set, height=12)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Poblar lista
        for session in sessions:
            created_at = session.get("created_at", "?")
            ggp = session.get("great_grandparent", "N/A")
            gp = session.get("grandparent", "N/A")
            prefix = session.get("father_prefix", "N/A")
            num_segments = session.get("total_segments", 0)
            
            display_text = f"[{created_at}] {ggp} > {gp} > {prefix} ({num_segments} partes)"
            listbox.insert(tk.END, display_text)
            
        listbox.selection_set(0)
        
        # Frame de botones
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        def on_recover():
            idx = listbox.curselection()
            if idx:
                session = sessions[idx[0]]
                dialog.destroy()
                self._recover_video_session(session)
                
        def on_cancel():
            dialog.destroy()
            
        def on_delete():
            idx = listbox.curselection()
            if idx:
                if messagebox.askyesno("Confirmar", "¿Eliminar esta sesión guardada? Esto borrará videos y transcripciones."):
                    session = sessions[idx[0]]
                    folder = session.get("session_folder")
                    if folder and os.path.exists(folder):
                        try:
                            import shutil
                            shutil.rmtree(folder)
                            sessions.pop(idx[0])
                            listbox.delete(idx[0])
                            self.video_log(f"🗑️ Sesión de video eliminada: {os.path.basename(folder)}")
                            if not sessions:
                                dialog.destroy()
                                messagebox.showinfo("Info", "No quedan sesiones guardadas.")
                        except Exception as e:
                            messagebox.showerror("Error", f"No se pudo eliminar la sesión: {e}")
                            
        ttk.Button(btn_frame, text="✅ Recuperar", command=on_recover).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="🗑 Eliminar", command=on_delete).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="❌ Cancelar", command=on_cancel).pack(side="right", padx=5)
        
        # Info de la sesión seleccionada
        info_frame = ttk.LabelFrame(dialog, text="Detalles de la sesión")
        info_frame.pack(fill="x", padx=10, pady=5)
        
        info_label = ttk.Label(info_frame, text="", wraplength=550)
        info_label.pack(padx=5, pady=5)
        
        def on_select(event):
            idx = listbox.curselection()
            if idx:
                session = sessions[idx[0]]
                d = session.get("duration", 0)
                dur_str = f"{int(d//60)}:{int(d%60):02d}"
                
                # Verificar si la sesión jerárquica tiene transcripciones guardadas
                fc_path = session.get("flashcard_session_path", "")
                has_chunks = False
                chunks_count = 0
                if fc_path and os.path.isdir(os.path.join(fc_path, "chunks")):
                    chunks_dir = os.path.join(fc_path, "chunks")
                    chunks_count = len([f for f in os.listdir(chunks_dir) if f.endswith('.txt')])
                    has_chunks = chunks_count > 0
                
                recovery_status = f"✅ {chunks_count} transcripciones listas (no re-procesará el video)" if has_chunks else "⚠️ Sin transcripciones jerárquicas previas"
                
                info = (f"Video: {session.get('original_video', 'N/A')}\n"
                        f"Ruta: {session.get('video_path', 'N/A')}\n"
                        f"Duración: {dur_str} | Segmentos: {session.get('total_segments', 0)}\n"
                        f"Sesión flashcards: {fc_path or 'No vinculada'}\n"
                        f"Estado: {recovery_status}")
                info_label.config(text=info)
                
        listbox.bind("<<ListboxSelect>>", on_select)
        on_select(None)
        
    def _recover_video_session(self, session_data: dict):
        """Recupera la sesión de video cargando sus segmentos."""
        # Limpiar cola de pendientes al recuperar sesión de video
        self.pending_flashcard_imports = []
        self._save_pending_queue()
        self._update_pending_button()
        self.video_log("🗑️ Sala de espera limpiada al recuperar una sesión de video.")

        # Restaurar configuración de jerarquía si existe
        if "great_grandparent" in session_data:
            self.great_grandparent_deck.set(session_data["great_grandparent"])
        if "grandparent" in session_data:
            self.grandparent_deck.set(session_data["grandparent"])
        if "father_prefix" in session_data:
            self.parent_prefix.set(session_data["father_prefix"])
            
        self.clear_video_mode()
        
        self.current_video_path = session_data.get("video_path")
        self.video_info_label.config(text=f"Recuperado: {session_data.get('original_video', 'Video')}")
        
        self.current_video_segments = []
        folder = session_data.get("session_folder")
        
        # Preferir la sesión jerárquica si existe (contiene chunks ya guardados)
        fc_session = session_data.get("flashcard_session_path", "")
        if fc_session and os.path.isdir(fc_session):
            self.current_video_session = fc_session
            self.video_log(f"   🔗 Sesión jerárquica vinculada: {fc_session}")
        else:
            self.current_video_session = folder
        
        for seg_data in session_data.get("segments", []):
            seg = VideoSegment(
                start_time=seg_data.get("start", 0),
                end_time=seg_data.get("end", 0),
                segment_id=seg_data.get("id", 0)
            )
            
            # Reconstruir rutas completas
            rel_audio = seg_data.get("audio_file")
            if rel_audio:
                audio_path = os.path.join(folder, "video_chunks", rel_audio)
                if os.path.exists(audio_path):
                    seg.audio_path = audio_path
            
            # Intentar cargar transcripción desde sesión jerárquica (chunks/) primero
            loaded_transcription = False
            if fc_session and os.path.isdir(fc_session):
                chunks_dir = os.path.join(fc_session, "chunks")
                chunk_file = os.path.join(chunks_dir, f"segment_{seg_data.get('id', 0):03d}.txt")
                if os.path.exists(chunk_file):
                    try:
                        with open(chunk_file, 'r', encoding='utf-8') as f:
                            text = f.read().strip()
                            seg.transcription_text = text
                            seg.char_count = len(text)
                            seg.transcription_path = chunk_file
                            loaded_transcription = True
                    except Exception:
                        pass
            
            # Fallback: transcripciones en carpeta temporal del video_processor
            if not loaded_transcription:
                rel_trans = seg_data.get("transcription_file")
                if rel_trans:
                    trans_path = os.path.join(folder, "transcriptions", rel_trans)
                    if os.path.exists(trans_path):
                        seg.transcription_path = trans_path
                        try:
                            with open(trans_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                lines = [line for line in content.split('\n') if not line.startswith('#')]
                                text = '\n'.join(lines).strip()
                                seg.transcription_text = text
                                seg.char_count = len(text)
                        except Exception:
                            seg.char_count = seg_data.get("char_count", 0)
            
            self.current_video_segments.append(seg)
            
        self._display_video_segments()
        
        # Habilitar botones adicionales
        self.create_sections_btn.config(state="normal")
        self.view_segments_btn.config(state="normal")
        self.show_segments_window()
        
        recovered_with_trans = sum(1 for s in self.current_video_segments if s.transcription_text)
        self.video_log(f"📁 Sesión de video recuperada: {len(self.current_video_segments)} segmentos, {recovered_with_trans} con transcripción.")
        if recovered_with_trans > 0:
            self.video_log(f"   ✅ Puedes crear secciones directamente — las transcripciones están listas.")
        
        # --- NUEVO: Recargar flashcards generadas en la Sala de Espera ---
        fc_path = session_data.get("flashcard_session_path", "") or folder
        self._load_flashcards_from_session(fc_path, session_data)
        self._save_pending_queue()
        self._update_pending_button()

    def _load_flashcards_from_session(self, session_path: str, session_data: dict):
        """
        Escanea la carpeta flashcards/ de una sesión recuperada y carga las tarjetas
        en self.pending_flashcard_imports para poder importarlas sin regenerar.
        """
        # Mapas para reconstruir card_type y label desde el sufijo del nombre de archivo
        type_labels = {
            "basic": "Basic",
            "multiple_choice": "Multiple Choice",
            "cloze": "Cloze",
            "vocabulary": "Vocabulary",
            "level_1_cloze": "Nivel 1 - Cloze",
            "level_2_relations": "Nivel 2 - Relaciones",
            "level_3_application": "Nivel 3 - Aplicación",
            "level_4_analysis": "Nivel 4 - Análisis",
            "atomic_extraction": "Extracción Atómica",
            "exam_pareto": "Examen Pareto",
            "exam_faithful": "Examen Fiel",
        }
        # Invertir para buscar por sufijo de archivo
        suffix_to_type = {v.lower().replace(" ", "_"): k for k, v in type_labels.items()}
        # También mapear directamente el nombre del tipo como sufijo
        for k in list(type_labels.keys()):
            suffix_to_type[k] = k

        flashcards_dir = os.path.join(session_path, "flashcards")
        if not os.path.isdir(flashcards_dir):
            self._mode_log(f"   ℹ️ No hay flashcards guardadas en esta sesión.")
            return

        # Reconstruir jerarquía de deck
        ggp = session_data.get("great_grandparent", self.great_grandparent_deck.get()).strip()
        gp  = session_data.get("grandparent", self.grandparent_deck.get()).strip()
        prefix = session_data.get("father_prefix", self.parent_prefix.get()).strip()

        loaded_count = 0
        loaded_files = 0

        for fname in sorted(os.listdir(flashcards_dir)):
            if not fname.endswith(".txt"):
                continue

            fpath = os.path.join(flashcards_dir, fname)
            # Nombre esperado: "PARTE X_card_type.txt"  o  "PARTE X_card_type_multimodal.txt"
            name_no_ext = fname[:-4]  # quitar .txt
            
            # Buscar el tipo de tarjeta buscando coincidencias al final del nombre
            card_type = None
            section_part = name_no_ext
            
            # Buscar primero con _multimodal
            is_multimodal = False
            temp_name = name_no_ext
            if temp_name.endswith("_multimodal"):
                is_multimodal = True
                temp_name = temp_name[:-11]  # quitar _multimodal
                
            # Buscar la llave de type_labels que coincide al final
            for possible_type in sorted(type_labels.keys(), key=len, reverse=True):
                suffix = f"_{possible_type}"
                if temp_name.endswith(suffix):
                    card_type = possible_type
                    section_part = temp_name[:-len(suffix)]
                    break
            
            if not card_type:
                # Fallback por si acaso
                parts = name_no_ext.split("_", 1)
                if len(parts) >= 2:
                    section_part = parts[0].strip()
                    type_suffix = parts[1].strip().replace("_multimodal", "")
                    card_type = suffix_to_type.get(type_suffix, type_suffix)
                else:
                    continue
            
            label = type_labels.get(card_type, card_type.replace("_", " ").title())
            
            # Construir deck destino
            deck_name = ""
            if ggp: deck_name += f"{ggp}::"
            if gp:  deck_name += f"{gp}::"
            deck_name += f"{section_part}::{label}"

            # Leer y parsear el TSV
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                if not content:
                    continue

                flashcards = []
                for line in content.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    if '\t' in line:
                        front, back = line.split('\t', 1)
                        flashcards.append({"front": front.strip(), "back": back.strip()})

                if flashcards:
                    self.pending_flashcard_imports.append({
                        "deck_name": deck_name,
                        "card_type": card_type,
                        "flashcards": flashcards
                    })
                    loaded_count += len(flashcards)
                    loaded_files += 1
                    
                    # Actualizar indicador visual de estado en la interfaz si aplica
                    if self.current_mode == "automatic_text":
                        sec_title_clean = section_part.lower().strip()
                        for section in self.text_sections:
                            safe_sec_title = "".join(c for c in section.title if c.isalnum() or c in " -_").strip().lower()
                            if safe_sec_title == sec_title_clean:
                                self.root.after(0, lambda sid=section.section_id, ct=card_type, c=len(flashcards): 
                                              self._update_text_section_status(sid, ct, True, c))
                                break
                    elif self.current_mode == "automatic_videos":
                        sec_title_clean = section_part.lower().strip()
                        for section in self.video_sections:
                            safe_sec_title = "".join(c for c in section.title if c.isalnum() or c in " -_").strip().lower()
                            if safe_sec_title == sec_title_clean:
                                self.root.after(0, lambda sid=section.section_id, ct=card_type, c=len(flashcards): 
                                              self._update_video_section_status(sid, ct, True, c))
                                break

            except Exception as e:
                self._mode_log(f"   ⚠️ Error leyendo {fname}: {e}")

        if loaded_files > 0:
            self._mode_log(f"   📋 {loaded_count} flashcards de sesión anterior cargadas en Sala de Espera ({loaded_files} archivos).")
            self._mode_log(f"   → Usa '🧠 Filtrar Interferencia (IA)' o '✅ Ejecutar Sincronización' directamente.")
        else:
            self._mode_log(f"   ℹ️ No se encontraron flashcards guardadas en la sesión.")

    def _recover_session(self, session_data: dict, replace: bool):
        """Recupera una sesión guardada."""
        # Restaurar configuración de jerarquía si existe
        if "great_grandparent" in session_data:
            self.great_grandparent_deck.set(session_data["great_grandparent"])
        if "grandparent" in session_data:
            self.grandparent_deck.set(session_data["grandparent"])
        if "father_prefix" in session_data:
            self.parent_prefix.set(session_data["father_prefix"])
            
        if replace:
            # Limpiar secciones actuales
            for section_id, widgets in list(self.section_widgets.items()):
                widgets["frame"].destroy()
            self.section_widgets.clear()
            self.thumbnail_refs.clear()
            self.sections.clear()
            self.section_counter = 0
            
            # Limpiar cola de pendientes al recuperar sesión de imágenes
            self.pending_flashcard_imports = []
            self._save_pending_queue()
            self._update_pending_button()
            self.auto_log("🗑️ Sala de espera limpiada al recuperar una sesión de imágenes.")
        
        # Recuperar secciones
        recovered_count = 0
        missing_images = []
        
        for section_info in session_data.get("sections", []):
            title = section_info.get("title", f"Sección {self.section_counter + 1}")
            image_paths = section_info.get("images", [])
            
            # Crear nueva sección
            self.section_counter += 1
            section = ImageSection(self.section_counter)
            section.title = title
            self.sections.append(section)
            self._create_section_widget(section)
            
            # Añadir imágenes
            for img_path in image_paths:
                if os.path.exists(img_path):
                    result = section.add_image(img_path)
                    if "error" not in result:
                        self._update_section_thumbnails(section)
                        self.auto_log(f"✅ Imagen recuperada: {os.path.basename(img_path)}")
                else:
                    missing_images.append(img_path)
            
            recovered_count += 1
        
        # Mostrar resumen
        action = "Reemplazadas" if replace else "Añadidas"
        self.auto_log(f"\n📂 {action} {recovered_count} secciones desde sesión guardada")
        
        if missing_images:
            self.auto_log(f"⚠️ {len(missing_images)} imágenes no encontradas (movidas o eliminadas)")
            for path in missing_images[:3]:
                self.auto_log(f"   • {os.path.basename(path)}")
            if len(missing_images) > 3:
                self.auto_log(f"   ... y {len(missing_images) - 3} más")

    def show_book_recovery_dialog(self):
        """Muestra el diálogo para recuperar una sesión de libro."""
        if not os.path.exists(BOOK_SESSIONS_FILE):
            messagebox.showinfo("Sin sesiones", "No hay sesiones de libro guardadas.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Recuperar Sesión de Libro")
        dialog.geometry("600x500")
        dialog.grab_set()

        ttk.Label(dialog, text="Selecciona una sesión de libro para recuperar:", 
                 font=("Segoe UI", 10, "bold")).pack(pady=10)

        # Frame principal con scroll
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        try:
            with open(BOOK_SESSIONS_FILE, 'r', encoding='utf-8') as f:
                sessions = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar las sesiones: {e}")
            dialog.destroy()
            return

        def select_session(idx):
            session = sessions[idx]
            self.recover_book_session(session)
            dialog.destroy()

        def delete_session(idx):
            if messagebox.askyesno("Confirmar", "¿Eliminar esta sesión de libro?"):
                sessions.pop(idx)
                with open(BOOK_SESSIONS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(sessions, f, ensure_ascii=False, indent=2)
                dialog.destroy()
                self.show_book_recovery_dialog()

        for i, session in enumerate(sessions):
            frame = ttk.Frame(scrollable_frame, relief="groove", padding=5)
            frame.pack(fill="x", pady=2, padx=2)
            
            info = f"{session['timestamp']} - {os.path.basename(session.get('book_path', 'Libro'))}\n"
            info += f"({session['num_sections']} secciones)"
            
            ttk.Label(frame, text=info, font=("Segoe UI", 9)).pack(side="left", padx=5)
            
            ttk.Button(frame, text="🗑", width=3, command=lambda idx=i: delete_session(idx)).pack(side="right", padx=2)
            ttk.Button(frame, text="Recuperar", command=lambda idx=i: select_session(idx)).pack(side="right", padx=5)

    def recover_book_session(self, session_data):
        """Recupera la sesión de libro cargando sus secciones."""
        self.clear_all_book_sections()
        
        # Limpiar cola de pendientes al recuperar sesión de libro
        self.pending_flashcard_imports = []
        self._save_pending_queue()
        self._update_pending_button()
        self.book_log("🗑️ Sala de espera limpiada al recuperar una sesión de libro.")
        
        self.great_grandparent_deck.set(session_data.get("great_grandparent", ""))
        self.grandparent_deck.set(session_data.get("grandparent", ""))
        self.parent_prefix.set(session_data.get("father_prefix", "Sección"))
        self.book_path_var.set(session_data.get("book_path", ""))
        
        recovered_count = 0
        for sec_data in session_data.get("sections", []):
            # Usar ImageSection ya que el sistema lo maneja igual para previsualizaciones
            section = ImageSection(sec_data["section_id"])
            section.title = sec_data["title"]
            section.pdf_segment_path = sec_data.get("pdf_segment_path")
            section.text = sec_data.get("text")
            
            # Recuperar imágenes (thumbnails)
            for img_path in sec_data.get("images", []):
                if os.path.exists(img_path):
                    section.add_image(img_path)
            
            self.book_sections.append(section)
            self._create_book_section_widget(section)
            self._update_book_section_info(section)
            recovered_count += 1
            
        self.book_log(f"📂 Recuperada sesión con {recovered_count} secciones.")
        # Actualizar canvas
        self.book_sections_canvas.configure(scrollregion=self.book_sections_canvas.bbox("all"))

    # ==================== FLASHCARDS PENDIENTES ====================
    
    def _check_and_confirm_clear_pending_queue(self, mode: str = "auto") -> bool:
        """
        Verifica si hay flashcards pendientes en la sala de espera (QYI).
        Pregunta al usuario si desea acumularlas o limpiarlas.
        Retorna True si el proceso puede continuar (limpiando o acumulando),
        o False si el usuario cancela la operación.
        """
        if not self.pending_flashcard_imports:
            return True
            
        count = len(self.pending_flashcard_imports)
        msg = f"Tienes {count} lote(s) de tarjetas pendientes en la Sala de Espera (QYI).\n\n"
        msg += "¿Deseas CONSERVAR las tarjetas existentes en la sala de espera y acumular las nuevas?\n\n"
        msg += "• Selecciona 'Sí' para conservar y acumular.\n"
        msg += "• Selecciona 'No' para LIMPIAR la Sala de Espera antes de empezar.\n"
        msg += "• Selecciona 'Cancelar' para no iniciar la generación."
        
        answer = messagebox.askyesnocancel("Tarjetas Pendientes detectadas", msg)
        
        # Obtener la función de log adecuada para el modo
        log_func = self.auto_log
        if mode == "book":
            log_func = self.book_log
        elif mode == "text":
            log_func = self.text_log
        elif mode == "video":
            log_func = self.video_log
        elif mode == "audio":
            log_func = self.audio_log
            
        if answer is None:
            # Seleccionó Cancelar
            log_func("🚫 Generación cancelada por el usuario debido a tarjetas pendientes en sala de espera.")
            return False
        elif answer is False:
            # Seleccionó No (Limpiar sala de espera)
            self.pending_flashcard_imports = []
            self._save_pending_queue()
            self._update_pending_button()
            log_func("🗑️ Sala de espera limpiada antes de iniciar la nueva generación.")
        else:
            # Seleccionó Sí (Conservar)
            log_func("📋 Conservando tarjetas pendientes en la sala de espera para acumular las nuevas.")
            
        return True

    def _save_pending_queue(self):
        """Guarda la cola de flashcards pendientes en un archivo JSON en disco."""
        try:
            queue_file = os.path.join(MASTER_FOLDER, "pending_queue.json")
            if not self.pending_flashcard_imports:
                if os.path.exists(queue_file):
                    os.remove(queue_file)
                return
            os.makedirs(MASTER_FOLDER, exist_ok=True)
            with open(queue_file, "w", encoding="utf-8") as f:
                json.dump(self.pending_flashcard_imports, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.auto_log(f"⚠️ Error al guardar cola de pendientes: {e}")

    def _load_pending_queue(self):
        """Carga la cola de flashcards pendientes desde el disco si existe."""
        try:
            queue_file = os.path.join(MASTER_FOLDER, "pending_queue.json")
            if os.path.exists(queue_file):
                with open(queue_file, "r", encoding="utf-8") as f:
                    self.pending_flashcard_imports = json.load(f)
                self.auto_log(f"📂 Sala de espera recuperada: {len(self.pending_flashcard_imports)} lotes de flashcards cargados desde pending_queue.json")
                self._update_pending_button()
        except Exception as e:
            self.auto_log(f"⚠️ Error al cargar cola de pendientes: {e}")

    def _update_pending_button(self):
        """Actualiza el texto del botón de pendientes con la cantidad."""
        try:
            count = len(self.pending_flashcard_imports)
            
            # Update all pending buttons that might exist in different tabs
            pending_buttons = []
            if hasattr(self, "pending_btn") and self.pending_btn:
                pending_buttons.append(self.pending_btn)
            if hasattr(self, "pending_text_btn") and self.pending_text_btn:
                pending_buttons.append(self.pending_text_btn)
            if hasattr(self, "pending_video_btn") and self.pending_video_btn:
                pending_buttons.append(self.pending_video_btn)
            if hasattr(self, "pending_audio_btn") and self.pending_audio_btn:
                pending_buttons.append(self.pending_audio_btn)
                
            for btn in pending_buttons:
                if count > 0:
                    btn.config(text=f"📋 Importar Pendientes ({count})")
                else:
                    btn.config(text="📋 Importar Pendientes")
        except Exception as e:
            self.auto_log(f"⚠️ Error al actualizar botón de pendientes: {e}")
    
    def import_pending_flashcards(self):
        """Importa las flashcards pendientes."""
        count = len(self.pending_flashcard_imports)
        
        if count == 0:
            messagebox.showinfo("Sin pendientes", "No hay flashcards pendientes de importar.")
            return
        
        msg = f"Hay {count} lote(s) de flashcards en la sala de espera pendientes de importar.\n\n"
        msg += "Asegúrate de que Anki esté abierto antes de continuar.\n\n"
        msg += "¿Deseas importarlas ahora?"
        
        if not messagebox.askyesno("Importar Pendientes", msg):
            return
        
        # Importar en thread
        def do_import():
            self.execute_deduplicated_import()
            self.root.after(0, self._update_pending_button)
            self.root.after(0, self._reset_all_status_indicators)
        
        thread = threading.Thread(target=do_import, daemon=True)
        thread.start()

    # ==================== CONFIGURACIÓN ====================
    
    def show_config_dialog(self):
        """Muestra la ventana de configuración de sets con widgets dinámicos."""
        # Bloquear si está procesando
        if self.is_processing:
            messagebox.showwarning(
                "Procesamiento en curso",
                "No se puede abrir la configuración mientras se están procesando secciones.\n\n"
                "Espera a que termine el procesamiento actual."
            )
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("⚙️ Configuración de Sets")
        dialog.geometry("800x650")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centrar ventana
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 800) // 2
        y = (dialog.winfo_screenheight() - 650) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Variables globales del diálogo
        current_set_var = tk.StringVar(value=self.config_manager.active_set_name)
        name_var = tk.StringVar()
        model_var = tk.StringVar()
        wait_var = tk.IntVar(value=80)
        replace_var = tk.BooleanVar(value=False)
        
        # Diccionarios para widgets dinámicos
        type_vars = {}  # {card_type: BooleanVar}
        type_checkbuttons = {}  # {card_type: Checkbutton widget}
        prompt_texts = {}  # {card_type: Text widget}
        prompt_tabs = {}  # {card_type: Frame widget}
        
        # Todos los tipos disponibles
        all_type_labels = {
            "basic": "📝 Basic (Anverso/Reverso)",
            "multiple_choice": "🔘 Multiple Choice",
            "cloze": "🔲 Cloze (Respuesta Anidada)",
            "vocabulary": "🔤 Vocabulary",
            "level_1_cloze": "1️⃣ Nivel 1 - Cloze (Recordar)",
            "level_2_relations": "2️⃣ Nivel 2 - Relaciones (Entender)",
            "level_3_application": "3️⃣ Nivel 3 - Aplicación (Aplicar)",
            "level_4_analysis": "4️⃣ Nivel 4 - Análisis (Analizar)",
            "atomic_extraction": "⚛️ Extracción Atómica (P/R Atómico)",
            "high_performance_architect": "⚡ Alto Rendimiento (Arquitecto)",
            "exam_pareto": "🎯 Examen Pareto (Q&A Pareto)",
            "exam_faithful": "📖 Examen Fiel (Q&A Ideas Principales)",
        }
        
        # Frame superior: Selector de set
        top_frame = ttk.Frame(dialog)
        top_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(top_frame, text="Set activo:", font=("Segoe UI", 10, "bold")).pack(side="left")
        
        set_combo = ttk.Combobox(top_frame, textvariable=current_set_var, 
                                  values=self.config_manager.get_set_names(), width=30)
        set_combo.pack(side="left", padx=10)
        
        # Notebook con tabs
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Tab 1: General
        general_frame = ttk.Frame(notebook, padding=10)
        notebook.add(general_frame, text="General")
        
        # Nombre del set
        ttk.Label(general_frame, text="Nombre del set:").grid(row=0, column=0, sticky="w", pady=5)
        name_entry = ttk.Entry(general_frame, textvariable=name_var, width=40)
        name_entry.grid(row=0, column=1, sticky="w", pady=5)
        
        # Modelo
        ttk.Label(general_frame, text="Modelo Gemini:").grid(row=1, column=0, sticky="w", pady=5)
        model_entry = ttk.Entry(general_frame, textvariable=model_var, width=40)
        model_entry.grid(row=1, column=1, sticky="w", pady=5)
        
        # Tiempo de espera
        ttk.Label(general_frame, text="Tiempo espera (seg):").grid(row=2, column=0, sticky="w", pady=5)
        wait_spin = ttk.Spinbox(general_frame, from_=10, to=300, textvariable=wait_var, width=10)
        wait_spin.grid(row=2, column=1, sticky="w", pady=5)
        
        # Modo reemplazar/acumular
        ttk.Label(general_frame, text="Modo de importación:").grid(row=3, column=0, sticky="w", pady=5)
        mode_frame = ttk.Frame(general_frame)
        mode_frame.grid(row=3, column=1, sticky="w", pady=5)
        ttk.Radiobutton(mode_frame, text="Acumular flashcards", variable=replace_var, 
                       value=False).pack(side="left")
        ttk.Radiobutton(mode_frame, text="Reemplazar mazo", variable=replace_var, 
                       value=True).pack(side="left", padx=10)
        
        # Tipos activos (contenedor dinámico)
        ttk.Label(general_frame, text="Tipos de flashcards:").grid(row=4, column=0, sticky="nw", pady=5)
        types_container = ttk.Frame(general_frame)
        types_container.grid(row=4, column=1, sticky="w", pady=5)
        
        # Tab 2: Prompts (contenedor dinámico)
        prompts_frame = ttk.Frame(notebook, padding=10)
        notebook.add(prompts_frame, text="Prompts")
        
        prompts_notebook = ttk.Notebook(prompts_frame)
        prompts_notebook.pack(fill="both", expand=True)
        
        # Tab 3: Importar/Exportar
        io_frame = ttk.Frame(notebook, padding=10)
        notebook.add(io_frame, text="Importar/Exportar")
        
        ttk.Label(io_frame, text="Exportar set actual como JSON:", 
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        
        export_text = tk.Text(io_frame, height=8, wrap="word", font=("Consolas", 9))
        export_text.pack(fill="x", pady=5)
        
        def do_export():
            json_str = self.config_manager.export_set(current_set_var.get())
            if json_str:
                export_text.delete("1.0", "end")
                export_text.insert("1.0", json_str)
        
        ttk.Button(io_frame, text="📤 Exportar a texto", command=do_export).pack(anchor="w", pady=5)
        
        ttk.Separator(io_frame, orient="horizontal").pack(fill="x", pady=10)
        
        ttk.Label(io_frame, text="Importar set desde JSON:", 
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        
        import_text = tk.Text(io_frame, height=8, wrap="word", font=("Consolas", 9))
        import_text.pack(fill="x", pady=5)
        
        def do_import():
            json_str = import_text.get("1.0", "end-1c").strip()
            if not json_str:
                messagebox.showwarning("Vacío", "Pega el JSON del set a importar")
                return
            success, msg = self.config_manager.import_set(json_str)
            if success:
                messagebox.showinfo("Éxito", msg)
                set_combo['values'] = self.config_manager.get_set_names()
                import_text.delete("1.0", "end")
            else:
                messagebox.showerror("Error", msg)
        
        ttk.Button(io_frame, text="📥 Importar desde texto", command=do_import).pack(anchor="w", pady=5)
        
        # Funciones auxiliares
        def highlight_variables(text_widget):
            """Resalta las variables {texto_ocr} en el prompt."""
            text_widget.tag_remove("variable", "1.0", "end")
            content = text_widget.get("1.0", "end")
            import re
            for match in re.finditer(r'\{texto_ocr\}', content):
                start = f"1.0+{match.start()}c"
                end = f"1.0+{match.end()}c"
                text_widget.tag_add("variable", start, end)
        
        def restore_default_prompt(type_key):
            """Restaura el prompt por defecto de un tipo."""
            if messagebox.askyesno("Confirmar", f"¿Restaurar prompt de {type_key} al valor por defecto?"):
                default = self.config_manager.get_default_prompt(type_key)
                if type_key in prompt_texts:
                    prompt_texts[type_key].delete("1.0", "end")
                    prompt_texts[type_key].insert("1.0", default)
                    highlight_variables(prompt_texts[type_key])
        
        def rebuild_type_widgets(set_name):
            """Reconstruye los widgets de tipos y prompts según el set."""
            config = self.config_manager.config_sets.get(set_name, {})
            active_types = config.get("active_types", {})
            prompts = config.get("prompts", {})
            
            # Determinar qué tipos mostrar: usar directamente las claves de active_types del set.
            # Si el set tiene tipos propios, usarlos; si no, los 4 básicos por defecto.
            if active_types:
                type_keys = list(active_types.keys())
            else:
                type_keys = ["basic", "multiple_choice", "cloze", "vocabulary"]
            
            # Limpiar widgets existentes
            for widget in types_container.winfo_children():
                widget.destroy()
            
            # Limpiar tabs de prompts
            for tab_id in prompts_notebook.tabs():
                prompts_notebook.forget(tab_id)
            
            type_vars.clear()
            type_checkbuttons.clear()
            prompt_texts.clear()
            prompt_tabs.clear()
            
            # Crear nuevos checkbuttons de tipos
            for idx, type_key in enumerate(type_keys):
                var = tk.BooleanVar(value=active_types.get(type_key, True))
                type_vars[type_key] = var
                
                cb = ttk.Checkbutton(types_container, text=all_type_labels.get(type_key, type_key), 
                                    variable=var)
                cb.grid(row=idx, column=0, sticky="w")
                type_checkbuttons[type_key] = cb
            
            # Crear nuevas tabs de prompts
            for type_key in type_keys:
                prompt_frame = ttk.Frame(prompts_notebook, padding=5)
                label_parts = all_type_labels.get(type_key, type_key).split()
                tab_label = f"{label_parts[0]} {label_parts[1]}" if len(label_parts) > 1 else label_parts[0]
                prompts_notebook.add(prompt_frame, text=tab_label)
                prompt_tabs[type_key] = prompt_frame
                
                # Botón restaurar
                btn_frame = ttk.Frame(prompt_frame)
                btn_frame.pack(fill="x")
                ttk.Button(btn_frame, text="🔄 Restaurar por defecto",
                          command=lambda t=type_key: restore_default_prompt(t)).pack(side="right")
                
                # Text widget para el prompt
                text_frame = ttk.Frame(prompt_frame)
                text_frame.pack(fill="both", expand=True, pady=5)
                
                scrollbar = ttk.Scrollbar(text_frame)
                scrollbar.pack(side="right", fill="y")
                
                text_widget = tk.Text(text_frame, wrap="word", height=15, 
                                     yscrollcommand=scrollbar.set, font=("Consolas", 9))
                text_widget.pack(side="left", fill="both", expand=True)
                scrollbar.config(command=text_widget.yview)
                
                # Configurar tag para variables
                text_widget.tag_configure("variable", background="#ffffcc", foreground="#0066cc")
                
                # Insertar prompt
                prompt_content = prompts.get(type_key, "")
                text_widget.insert("1.0", prompt_content)
                highlight_variables(text_widget)
                
                prompt_texts[type_key] = text_widget
        
        def load_set_to_ui(set_name):
            """Carga un set en la UI."""
            config = self.config_manager.config_sets.get(set_name, {})
            name_var.set(config.get("name", set_name))
            model_var.set(config.get("model", "gemini-3-flash-preview"))
            wait_var.set(config.get("wait_time", 80))
            replace_var.set(config.get("replace_mode", False))
            
            # Reconstruir widgets dinámicos
            rebuild_type_widgets(set_name)
        
        def on_set_change(event=None):
            """Maneja el cambio de set."""
            new_set = current_set_var.get()
            load_set_to_ui(new_set)
        
        set_combo.bind("<<ComboboxSelected>>", on_set_change)
        
        # Botones de gestión de sets
        ttk.Button(top_frame, text="➕ Nuevo", 
                  command=lambda: create_new_set()).pack(side="left", padx=2)
        ttk.Button(top_frame, text="🗑 Eliminar", 
                  command=lambda: delete_current_set()).pack(side="left", padx=2)
        
        def save_current_set():
            """Guarda el set actual."""
            set_name = current_set_var.get()
            new_name = name_var.get().strip()
            
            # Si cambió el nombre, crear nuevo set
            if new_name and new_name != set_name:
                if new_name in self.config_manager.get_set_names():
                    messagebox.showerror("Error", f"Ya existe un set con el nombre '{new_name}'")
                    return
                # Renombrar (crear nuevo y eliminar viejo si no es el default)
                self.config_manager.create_set(new_name, set_name)
                if set_name != "Por Defecto" and set_name != "Niveles Bloom":
                    self.config_manager.delete_set(set_name)
                set_name = new_name
                current_set_var.set(new_name)
                set_combo['values'] = self.config_manager.get_set_names()
            
            # Recopilar datos
            updates = {
                "name": new_name or set_name,
                "model": model_var.get(),
                "wait_time": wait_var.get(),
                "replace_mode": replace_var.get(),
                "active_types": {k: v.get() for k, v in type_vars.items()},
                "prompts": {k: v.get("1.0", "end-1c") for k, v in prompt_texts.items()}
            }
            
            self.config_manager.update_set(set_name, updates)
            self.config_manager.set_active_set(set_name)
            
            # Actualizar todos los labels de set dinámicamente
            set_text = f"Set: {set_name}"
            if hasattr(self, 'active_set_label'): self.active_set_label.config(text=set_text)
            if hasattr(self, 'text_set_label'): self.text_set_label.config(text=set_text)
            if hasattr(self, 'book_set_label'): self.book_set_label.config(text=set_text)
            if hasattr(self, 'audio_set_label'): self.audio_set_label.config(text=set_text)
            if hasattr(self, 'video_set_label'): self.video_set_label.config(text=set_text)
            self.refresh_all_section_indicators()
            messagebox.showinfo("Guardado", f"Set '{set_name}' guardado correctamente")
        
        def create_new_set():
            """Crea un nuevo set."""
            name = simpledialog.askstring("Nuevo Set", "Nombre del nuevo set:", parent=dialog)
            if name:
                if self.config_manager.create_set(name, current_set_var.get()):
                    set_combo['values'] = self.config_manager.get_set_names()
                    current_set_var.set(name)
                    load_set_to_ui(name)
                else:
                    messagebox.showerror("Error", f"No se pudo crear el set '{name}'")
        
        def delete_current_set():
            """Elimina el set actual."""
            set_name = current_set_var.get()
            if set_name in ["Por Defecto", "Niveles Bloom"]:
                messagebox.showwarning("No permitido", "No se pueden eliminar los sets predefinidos")
                return
            if messagebox.askyesno("Confirmar", f"¿Eliminar el set '{set_name}'?"):
                self.config_manager.delete_set(set_name)
                set_combo['values'] = self.config_manager.get_set_names()
                current_set_var.set("Por Defecto")
                load_set_to_ui("Por Defecto")
        
        def apply_and_close():
            """Aplica cambios y cierra."""
            save_current_set()
            dialog.destroy()
        
        # Frame inferior: Botones de acción
        bottom_frame = ttk.Frame(dialog)
        bottom_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(bottom_frame, text="💾 Guardar", command=save_current_set).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="✅ Aplicar y Cerrar", command=apply_and_close).pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="❌ Cancelar", command=dialog.destroy).pack(side="right", padx=5)
        
        # Cargar set actual
        load_set_to_ui(current_set_var.get())

    def _on_audio_drop(self, event):
        """Manejador para el evento drop de audios."""
        file_path = event.data
        if file_path.startswith('{') and file_path.endswith('}'):
            file_path = file_path[1:-1]
        self.upload_audio_for_processing(file_path=file_path)

    def download_youtube_audio(self):
        """Descarga un audio de YouTube a través de una URL."""
        url = self.youtube_url_var.get().strip()
        if not url:
            messagebox.showwarning("URL vacía", "Por favor ingresa una URL de YouTube.")
            return
            
        self.audio_yt_download_btn.config(state="disabled", text="⏳ Descargando...")
        self.audio_log(f"🎧 Iniciando descarga de YouTube: {url}")
        
        def run_download():
            path = self.youtube_downloader.download_video(url, self.audio_log)
            
            def on_complete():
                self.audio_yt_download_btn.config(state="normal", text="📥 Descargar")
                if path and os.path.exists(path):
                    self.audio_log(f"✅ Audio de YouTube descargado: {path}")
                    self.upload_audio_for_processing(file_path=path)
                else:
                    messagebox.showerror("Error", "No se pudo descargar el audio.")
            
            self.root.after(0, on_complete)
            
        threading.Thread(target=run_download, daemon=True).start()

    def upload_audio_for_processing(self, file_path: str = None):
        """Abre diálogo para seleccionar un audio."""
        if not file_path:
            filetypes = [
                ("Audios", "*.mp3 *.wav *.aac *.flac *.m4a *.ogg *.opus"),
                ("Todos los archivos", "*.*")
            ]
            file_path = filedialog.askopenfilename(title="Seleccionar audio", filetypes=filetypes)
        
        if not file_path:
            return
        
        valid, msg = self.video_processor.validate_video(file_path) # Reusamos validador
        
        if not valid:
            self.audio_log(f"❌ {msg}")
            messagebox.showerror("Audio inválido", msg)
            return
        
        self.audio_log(f"✅ {msg}")
        self.audio_log(f"📁 Audio cargado: {os.path.basename(file_path)}")
        
        self.current_audio_path = file_path
        self.audio_info_label.config(text=f"🎧 {os.path.basename(file_path)}")
        
        if hasattr(self, 'audio_drop_frame'):
            self.audio_drop_frame.grid_forget()
        if hasattr(self, 'change_audio_btn'):
            self.change_audio_btn.pack(side="left", padx=5)
            
        self.process_audio_btn.config(state="normal")
    
    def process_audio_complete(self):
        """Procesa el audio completo: segmenta y transcribe."""
        if not self.current_audio_path:
            messagebox.showwarning("Sin audio", "No hay audio cargado.")
            return
        
        if self.is_processing:
            messagebox.showwarning("En proceso", "Ya hay un procesamiento en curso.")
            return
        
        msg = f"¿Procesar el audio?\n\n"
        msg += "Esto realizará:\n"
        msg += "1. Segmentación del audio\n"
        msg += "2. Transcripción Multimodal Inteligente con Gemini AI (Optimizado para audio)\n\n"
        msg += "Nota: Este proceso puede tomar varios minutos."
        
        if not messagebox.askyesno("Confirmar procesamiento", msg):
            return
        
        self.is_processing = True
        self.process_audio_btn.config(state="disabled", text="⏳ Procesando...")
        
        thread = threading.Thread(target=self._process_audio_thread, daemon=True)
        thread.start()
    
    def _process_audio_thread(self):
        """Thread de procesamiento del audio."""
        try:
            segment_duration = self.audio_segment_duration_var.get() * 60
            overlap = self.audio_overlap_var.get()
            language = self.audio_language_var.get()
            
            self.audio_log(f"\n{'='*60}")
            self.audio_log(f"🎧 PROCESANDO AUDIO (Motor: Gemini Multimodal Audio)")
            self.audio_log(f"{'='*60}")
            
            bisabuelo = self.great_grandparent_deck.get().strip()
            grandparent = self.grandparent_deck.get().strip() or "General"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if bisabuelo:
                self.current_audio_session = os.path.join(MASTER_FOLDER, bisabuelo, grandparent, f"Audio_Session_{timestamp}")
            else:
                self.current_audio_session = os.path.join(MASTER_FOLDER, grandparent, f"Audio_Session_{timestamp}")
            
            if not hasattr(self, 'flashcard_generator') or not self.flashcard_generator:
                active_config = self.config_manager.get_active_set()
                self.flashcard_generator = GeminiFlashcardGenerator(log_callback=self.audio_log, config_set=active_config)
            
            saved_count = [0]
            
            def on_segment_complete(segment):
                if segment.transcription_text:
                    self.flashcard_generator._save_ocr_transcript(
                        segment.transcription_text, self.current_audio_session, 
                        f"segment_{segment.segment_id:03d}", 
                        subfolder="chunks"
                    )
                    saved_count[0] += 1
                    self.audio_log(f"   💾 Segmento {segment.segment_id} guardado incrementalmente ({saved_count[0]} guardados)")
            
            # Redirigir logs del VideoProcessor al panel de audio
            original_log_callback = self.video_processor.log_callback
            self.video_processor.log_callback = self.audio_log
            
            # --- NUEVA LÓGICA DE SEGMENTACIÓN (Estándar vs Semántico) ---
            mode_type = getattr(self, "audio_segmentation_mode_var", None)
            segmentation_mode = mode_type.get() if mode_type else "standard"
            
            explicit_timestamps = None
            if segmentation_mode == "semantic":
                self.audio_log("🧠 Iniciando Diarización Semántica con PyAnnote...")
                chunker = self.chunking_factory.get_chunker(self.current_audio_path, mode="semantic")
                chunk_result = chunker.process_and_chunk(self.current_audio_path)
                
                if chunk_result.get("success"):
                    explicit_timestamps = chunk_result.get("explicit_timestamps")
                    self.audio_log(chunk_result.get("message", ""))
                else:
                    self.audio_log(f"⚠️ Error en Diarización Semántica: {chunk_result.get('error')}")
                    self.audio_log("Fallback: Usando segmentación estándar.")
                    
            # Reusamos process_video porque Gemini maneja audio igual que video (multimodal)
            result = self.video_processor.process_video(
                video_path=self.current_audio_path,
                segment_duration=segment_duration,
                overlap=overlap,
                use_silence_detection=False,
                use_transcription_analysis=False,
                language=language,
                on_segment_complete=on_segment_complete,
                great_grandparent=self.great_grandparent_deck.get(),
                grandparent=self.grandparent_deck.get(),
                father_prefix=self.parent_prefix.get(),
                explicit_timestamps=explicit_timestamps
            )
            
            if not result.get("success"):
                self.audio_log(f"❌ Error procesando audio: {result.get('error')}")
                self.root.after(0, lambda: messagebox.showerror("Error", f"Error procesando audio:\n{result.get('error')}"))
                return
            
            self.current_audio_segments = result.get("segments", [])
            
            # Guardar la transcripción completa
            try:
                full_transcription = "\n\n".join([
                    f"--- Segmento {s.segment_id} ({s.start_time} - {s.end_time}) ---\n{s.transcription_text}"
                    for s in self.current_audio_segments
                ])
                self.flashcard_generator._save_ocr_transcript(full_transcription, self.current_audio_session, "original_full_transcription", subfolder="original_text")
            except Exception as save_err:
                self.audio_log(f"   ⚠️ Error guardando transcripción: {save_err}")
            
            self.audio_log(f"\n✅ Audio procesado exitosamente")
            self.audio_log(f"   📊 {len(self.current_audio_segments)} segmentos creados")
            
            self.root.after(0, self._display_audio_segments)
            self.root.after(0, lambda: self.create_audio_sections_btn.config(state="normal"))
            self.root.after(0, lambda: self.view_audio_segments_btn.config(state="normal"))
            
        except Exception as e:
            self.audio_log(f"\n❌ ERROR CRÍTICO: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error: {e}"))
        finally:
            # Restaurar log callback original del VideoProcessor
            self.video_processor.log_callback = self.video_log
            self.is_processing = False
            self.root.after(0, lambda: self.process_audio_btn.config(state="normal", text="🚀 Procesar Audio"))

    def _display_audio_segments(self):
        """Muestra los segmentos de audio procesados."""
        for widget in self.audio_segments_inner_frame.winfo_children():
            widget.destroy()
        self.audio_segment_widgets.clear()
        
        for segment in self.current_audio_segments:
            seg_frame = ttk.Frame(self.audio_segments_inner_frame, padding="5")
            seg_frame.pack(fill="x", pady=2)
            seg_frame.columnconfigure(1, weight=1)
            
            check_var = tk.BooleanVar(value=True)
            check = ttk.Checkbutton(seg_frame, variable=check_var)
            check.grid(row=0, column=0, rowspan=2)
            
            title = f"Segmento {segment.segment_id} ({segment.start_time}-{segment.end_time})"
            ttk.Label(seg_frame, text=title, font=("Arial", 9, "bold")).grid(row=0, column=1, sticky="w")
            
            text_preview = (segment.transcription_text[:150] + "...") if len(segment.transcription_text) > 150 else segment.transcription_text
            content_label = ttk.Label(seg_frame, text=text_preview, foreground="gray", font=("Arial", 8))
            content_label.grid(row=1, column=1, sticky="w")
            
            self.audio_segment_widgets[segment.segment_id] = {
                "frame": seg_frame,
                "check_var": check_var
            }
        self.show_audio_segments_window()

    def create_audio_sections_from_segments(self):
        """Agrupa segmentos de audio en secciones."""
        selected_segments = []
        for segment in self.current_audio_segments:
            if self.audio_segment_widgets[segment.segment_id]["check_var"].get():
                selected_segments.append(segment)
        
        if not selected_segments:
            messagebox.showwarning("Sin selección", "No hay segmentos seleccionados.")
            return
            
        self.clear_audio_mode(only_sections=True)
        
        group_size = self.audio_segments_per_section_var.get()
        for i in range(0, len(selected_segments), group_size):
            group = selected_segments[i:i + group_size]
            self.audio_section_counter += 1
            self.hierarchy_counter += 1
            
            from video_processor import VideoSection
            section = VideoSection(self.audio_section_counter)
            section.segments = group
            
            prefix = self.parent_prefix.get().strip()
            section.title = f"{prefix} {self.hierarchy_counter}" if prefix else f"Sección Audio {self.audio_section_counter}"
            
            self.audio_sections.append(section)
            self._create_audio_section_widget(section)
            
        self.audio_log(f"✅ Creadas {len(self.audio_sections)} secciones de audio")
        self.process_audio_sections_btn.config(state="normal")
        self.hide_audio_segments_window()

    def _create_audio_section_widget(self, section):
        """Crea widget visual para sección de audio."""
        section_frame = ttk.LabelFrame(self.audio_sections_inner_frame, padding="10")
        section_frame.grid(row=len(self.audio_sections)-1, column=0, sticky="ew", pady=5, padx=5)
        section_frame.columnconfigure(0, weight=1)
        
        header_frame = ttk.Frame(section_frame)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(1, weight=1)
        
        title_label = ttk.Label(header_frame, text=section.title, font=("Arial", 11, "bold"))
        title_label.grid(row=0, column=0, sticky="w")
        
        ttk.Label(header_frame, text=f"({len(section.segments)} segmentos)", foreground="gray").grid(row=0, column=1, sticky="w", padx=10)
        
        status_frame = ttk.Frame(section_frame)
        status_frame.grid(row=1, column=0, sticky="w", pady=(5, 0))
        
        active_config = self.config_manager.get_active_set()
        active_types = active_config.get("active_types", {})
        status_labels = {}
        
        card_types = [
            ("basic", "📝", "Basic"),
            ("multiple_choice", "🔘", "Multiple"),
            ("cloze", "🔲", "Cloze"),
            ("vocabulary", "🔤", "Vocab")
        ]
        
        for idx, (ctype, icon, label) in enumerate(card_types):
            if not active_types.get(ctype): continue
            tf = ttk.Frame(status_frame)
            tf.grid(row=0, column=idx, padx=(0, 15))
            ttk.Label(tf, text=icon).grid(row=0, column=0)
            sl = tk.Label(tf, text="⬜", fg="gray")
            sl.grid(row=0, column=1, padx=2)
            cl = ttk.Label(tf, text="")
            cl.grid(row=0, column=2)
            status_labels[ctype] = {"state": sl, "count": cl}
            
        self.audio_section_widgets[section.section_id] = {
            "frame": section_frame, 
            "title_label": title_label,
            "status_labels": status_labels
        }

    def process_audio_sections(self):
        """Procesa secciones de audio para generar flashcards."""
        if not self.audio_sections: return
        
        if self.is_processing:
            messagebox.showwarning("En proceso", "Ya hay un procesamiento en curso.")
            return

        if not self._check_and_confirm_clear_pending_queue(mode="audio"):
            return
            
        self.is_processing = True
        self.process_audio_sections_btn.config(state="disabled", text="⏳ Procesando...")
        
        bisabuelo = self.great_grandparent_deck.get().strip()
        grandparent = self.grandparent_deck.get().strip()
        
        thread = threading.Thread(target=self._process_audio_sections_thread, args=(bisabuelo, grandparent), daemon=True)
        thread.start()

    def _process_audio_sections_thread(self, bisabuelo, grandparent):
        """Thread para procesar secciones de audio."""
        try:
            active_config = self.config_manager.get_active_set()
            if not self.flashcard_generator:
                self.flashcard_generator = GeminiFlashcardGenerator(log_callback=self.audio_log, config_set=active_config)
            else:
                self.flashcard_generator.update_config(active_config)

            total_flashcards = 0
            processing_results = []

            for idx, section in enumerate(self.audio_sections, 1):
                content = "\n\n".join([
                    f"--- Fragmento {s.segment_id} ---\n{s.transcription_text}"
                    for s in section.segments
                ])
                if not content.strip():
                    continue

                self.audio_log(f"\n{'='*60}")
                self.audio_log(f"📁 SECCIÓN {idx}/{len(self.audio_sections)}: {section.title}")
                self.audio_log(f"{'='*60}")

                results = self.flashcard_generator.generate_all_flashcards_sequential(content)
                
                # Capturar métricas QYI
                qyi_metrics = getattr(self.flashcard_generator, 'last_evaluation_metrics', {})
                
                section_results = {
                    "section": section.title,
                    "success": True,
                    "qyi_metrics": qyi_metrics,
                    "results": {}
                }

                for card_type, result in results.items():
                    if result.get("success"):
                        fc_content = result.get("content", "")
                        flashcards = self.converter.convert(fc_content, card_type)
                        if flashcards:
                            flashcard_list = []
                            for line in flashcards.strip().split('\n'):
                                if '\t' in line:
                                    front, back = line.split('\t', 1)
                                    flashcard_list.append({"front": front.strip(), "back": back.strip()})

                            if flashcard_list:
                                deck_name = ""
                                if bisabuelo: deck_name += f"{bisabuelo}::"
                                if grandparent: deck_name += f"{grandparent}::"
                                deck_name += f"{section.title}"
                                deck_path = self._get_deck_with_type_label(deck_name, card_type)

                                count = len(flashcard_list)
                                section_results["results"][card_type] = {
                                    "success": True,
                                    "count": count,
                                    "flashcards": flashcard_list,
                                    "deck": deck_name
                                }
                                total_flashcards += count
                                
                                self.audio_log(f"   ✅ {card_type}: {count} flashcards en espera → {deck_name}")
                                self.root.after(0, lambda sid=section.section_id, ct=card_type, c=count:
                                              self._update_audio_section_status(sid, ct, True, c))
                            else:
                                self.audio_log(f"   ⚠️ No se pudieron estructurar tarjetas para '{card_type}'")
                                self.root.after(0, lambda sid=section.section_id, ct=card_type:
                                              self._update_audio_section_status(sid, ct, False, 0))
                                section_results["results"][card_type] = {
                                    "success": False,
                                    "error": "No flashcards parsed"
                                }
                        else:
                            self.audio_log(f"   ⚠️ No se pudieron estructurar tarjetas para '{card_type}'")
                            self.root.after(0, lambda sid=section.section_id, ct=card_type:
                                          self._update_audio_section_status(sid, ct, False, 0))
                            section_results["results"][card_type] = {
                                "success": False,
                                "error": "No flashcards parsed"
                            }
                    else:
                        error_msg = result.get("error", "Error desconocido")
                        self.audio_log(f"   ❌ Error al generar tipo '{card_type}': {error_msg}")
                        self.root.after(0, lambda sid=section.section_id, ct=card_type:
                                      self._update_audio_section_status(sid, ct, False, 0))
                        section_results["results"][card_type] = {
                            "success": False,
                            "error": error_msg
                        }
                
                processing_results.append(section_results)

            self.audio_log(f"\n{'='*60}")
            self.audio_log(f"✅ COMPLETADO - Total flashcards: {total_flashcards}")
            self.audio_log(f"{'='*60}")
            
            # Mostrar resumen final con QYI
            self.root.after(0, lambda: self._show_processing_summary(processing_results))
            
        except Exception as e:
            self.audio_log(f"❌ Error: {e}")
        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.process_audio_sections_btn.config(state="normal", text="🚀 Procesar Secciones"))




    def clear_audio_mode(self, only_sections=False):
        """Limpia la pantalla de audio."""
        for widgets in self.audio_section_widgets.values():
            widgets["frame"].destroy()
        self.audio_section_widgets.clear()
        self.audio_sections.clear()
        if not only_sections:
            for widget in self.audio_segments_inner_frame.winfo_children():
                widget.destroy()
            self.audio_segment_widgets.clear()
            self.current_audio_segments.clear()
            self.current_audio_path = None
            self.audio_info_label.config(text="")
            if hasattr(self, 'audio_drop_frame'):
                self.audio_drop_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(15, 15))
            if hasattr(self, 'change_audio_btn'):
                self.change_audio_btn.pack_forget()
            self.process_audio_btn.config(state="disabled")

    def show_recover_audio_session_dialog(self):
        """Recupera sesión de audio buscando en las carpetas de sesiones guardadas."""
        # Buscar sesiones de audio en MASTER_FOLDER
        sessions = []
        if os.path.exists(MASTER_FOLDER):
            for root_dir, dirs, files in os.walk(MASTER_FOLDER):
                if os.path.basename(root_dir).startswith("Audio_Session_"):
                    chunks_dir = os.path.join(root_dir, "chunks")
                    if os.path.exists(chunks_dir):
                        chunk_files = sorted([f for f in os.listdir(chunks_dir) if f.endswith(('.txt', '.md'))])
                        if chunk_files:
                            sessions.append({
                                "folder": root_dir,
                                "name": os.path.basename(root_dir),
                                "chunks_dir": chunks_dir,
                                "chunk_files": chunk_files,
                                "num_chunks": len(chunk_files)
                            })
        
        if not sessions:
            messagebox.showinfo("Sin sesiones", "No hay sesiones de audio guardadas para recuperar.")
            return
        
        sessions.sort(key=lambda x: x["name"], reverse=True)
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Recuperar Sesión de Audio")
        dialog.geometry("600x350")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Selecciona una sesión de audio:", font=("Segoe UI", 11, "bold")).pack(pady=10)
        
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        listbox = tk.Listbox(list_frame, font=("Segoe UI", 10), yscrollcommand=scrollbar.set, height=10)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        
        for s in sessions:
            listbox.insert(tk.END, f"{s['name']} ({s['num_chunks']} segmentos)")
        listbox.selection_set(0)
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        def on_recover():
            idx = listbox.curselection()
            if not idx: return
            session = sessions[idx[0]]
            dialog.destroy()
            self._recover_audio_session(session)
        
        ttk.Button(btn_frame, text="✅ Recuperar", command=on_recover).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="❌ Cancelar", command=dialog.destroy).pack(side="right", padx=5)

    def _recover_audio_session(self, session):
        """Recupera segmentos de audio desde archivos de transcripción guardados."""
        from video_processor import VideoSegment
        
        self.audio_log(f"\n📂 Recuperando sesión: {session['name']}")
        self.current_audio_session = session["folder"]
        self.current_audio_segments = []
        
        # Limpiar cola de pendientes al recuperar sesión de audio
        self.pending_flashcard_imports = []
        self._save_pending_queue()
        self._update_pending_button()
        self.audio_log("🗑️ Sala de espera limpiada al recuperar una sesión de audio.")
        
        for idx, chunk_file in enumerate(session["chunk_files"], 1):
            chunk_path = os.path.join(session["chunks_dir"], chunk_file)
            try:
                with open(chunk_path, 'r', encoding='utf-8') as f:
                    text = f.read().strip()
                seg = VideoSegment(start_time=0, end_time=0, segment_id=idx)
                seg.transcription_text = text
                seg.char_count = len(text)
                self.current_audio_segments.append(seg)
                self.audio_log(f"   ✅ Segmento {idx}: {len(text):,} caracteres")
            except Exception as e:
                self.audio_log(f"   ❌ Error leyendo {chunk_file}: {e}")
        
        self.audio_log(f"✅ {len(self.current_audio_segments)} segmentos recuperados")
        self._display_audio_segments()
        self.create_audio_sections_btn.config(state="normal")
        self.view_audio_segments_btn.config(state="normal")

    def audio_log(self, message: str):
        """Añade un mensaje al log del modo de audio."""
        self.ui_queue.put({"type": "log", "target": "audio", "message": message})

    def _update_audio_section_status(self, section_id, card_type, success, count):
        """Actualiza el indicador de estado de una sección de audio."""
        widgets = self.audio_section_widgets.get(section_id)
        if not widgets or "status_labels" not in widgets: return
        sl = widgets["status_labels"].get(card_type)
        if sl:
            sl["state"].config(text="✅" if success else "❌", fg="green" if success else "red")
            sl["count"].config(text=str(count))




    # ==================== DEDUPLICACIÓN SEMÁNTICA ====================
    def open_deduplication_window(self):
        """Abre la ventana de deduplicación con las flashcards en espera."""
        if not self.pending_flashcard_imports:
            messagebox.showinfo("Deduplicación", "No hay tarjetas generadas en la sala de espera para filtrar.")
            return
            
        def on_dedup_complete(filtered_imports):
            self.pending_flashcard_imports = filtered_imports
            self.auto_log("✅ Proceso de filtrado semántico finalizado en memoria.")
            self._save_pending_queue()
            self._update_pending_button()
            
        DeduplicationUI(self.root, self.pending_flashcard_imports, on_dedup_complete, engine=self.dedup_engine)

    def open_evaluation_window(self):
        """Abre la ventana de evaluación didáctica y topológica con las flashcards en espera."""
        if not self.pending_flashcard_imports:
            messagebox.showinfo("Evaluación", "No hay tarjetas generadas en la sala de espera para evaluar.")
            return
            
        # Asegurar que el generador esté inicializado
        if not self.flashcard_generator:
            active_config = self.config_manager.get_active_set()
            self.flashcard_generator = GeminiFlashcardGenerator(
                log_callback=self._mode_log,
                config_set=active_config
            )
            
        def on_eval_complete(filtered_imports):
            self.pending_flashcard_imports = filtered_imports
            self._mode_log("✅ Proceso de evaluación y filtrado didáctico finalizado en memoria.")
            self._save_pending_queue()
            self._update_pending_button()
            
        EvaluationUI(self.root, self.pending_flashcard_imports, on_eval_complete, generator=self.flashcard_generator, app=self)

    def execute_deduplicated_import(self):
        """Sincroniza la sala de espera filtrada a Anki."""
        if not self.pending_flashcard_imports:
            messagebox.showinfo("Importación", "No hay tarjetas en espera para importar a Anki.")
            return
            
        total_imported = 0
        self.auto_log(f"\n{'='*60}")
        self.auto_log("📤 INICIANDO IMPORTACIÓN SINCRONIZADA A ANKI")
        self.auto_log(f"{'='*60}")
        
        failed_groups = []
        for group in self.pending_flashcard_imports:
            deck_name = group['deck_name']
            card_type = group['card_type']
            flashcards = group['flashcards']
            
            if not flashcards:
                continue
                
            success, msg, count = self.anki_manager.sync_flashcards_to_anki(
                deck_name=deck_name,
                flashcards_data=flashcards,
                card_type=card_type
            )
            
            if success:
                self.auto_log(f"   ✅ {count} tarjetas importadas a {deck_name}")
                total_imported += count
            else:
                self.auto_log(f"   ❌ Error importando a {deck_name}: {msg}")
                failed_groups.append(group)
                
        self.auto_log(f"\n✅ Proceso completado: {total_imported} tarjetas importadas a Anki.")
        
        if failed_groups:
            self.auto_log(f"   ⚠️ {len(failed_groups)} lote(s) no pudieron ser importados y se conservan en la sala de espera.")
            messagebox.showwarning(
                "Importación Parcial o Fallida",
                f"Se han importado {total_imported} flashcards.\n\n"
                f"{len(failed_groups)} lote(s) fallaron y permanecen en la sala de espera.\n\n"
                "Asegúrate de que:\n"
                "1. Anki esté abierto.\n"
                "2. Hayas seleccionado un perfil en Anki (no te quedes en la pantalla de selección de perfil).\n"
                "3. El complemento AnkiConnect esté instalado y configurado correctamente."
            )
        else:
            messagebox.showinfo("Importación Completada", f"Se han importado {total_imported} flashcards a Anki correctamente respetando los mazos hijos.")
            
        # Conservar solo los grupos fallidos en la sala de espera
        self.pending_flashcard_imports = failed_groups
        self._save_pending_queue()
        self._update_pending_button()

def main():
    """Inicia la aplicación."""
    # Intentar usar TkinterDnD para drag & drop si está disponible
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        print("✅ TkinterDnD habilitado - Drag & drop disponible")
    except (ImportError, RuntimeError, Exception) as e:
        import tkinter as tk
        root = tk.Tk()
        print(f"⚠️ TkinterDnD no disponible o incompatible ({type(e).__name__}) - Usa botones para añadir imágenes")
        print("   Nota: Drag & drop deshabilitado para evitar errores de Tcl/Tk.")
    
    app = AnkiImportInterface(root)
    root.mainloop()




if __name__ == "__main__":
    main()
