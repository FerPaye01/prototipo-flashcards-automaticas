"""
Interfaz simplificada para importar flashcards a Anki.
4 cajitas de texto, una para cada estilo de flashcard.
+ Modo Automático con secciones dinámicas para imágenes.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import os
import json
from datetime import datetime
from PIL import Image, ImageTk
import io
from flashcards_converter import FlashcardsConverter
from anki_sync_manager import AnkiSyncManager
from gemini_flashcard_generator import GeminiFlashcardGenerator
from config_sets_manager import ConfigSetsManager
from video_processor import VideoProcessor

# Archivo para guardar sesiones
SESSIONS_FILE = "flashcard_sessions.json"


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
        
        self.converter = FlashcardsConverter()
        self.anki_manager = AnkiSyncManager()
        self.flashcard_generator = None  # Se inicializa bajo demanda
        self.config_manager = ConfigSetsManager()  # Gestor de configuraciones
        self.video_processor = VideoProcessor(log_callback=self.auto_log)  # Procesador de videos
        
        # Modo actual: "normal", "automatic_images", "automatic_videos"
        self.current_mode = "normal"
        
        # Secciones para modo automático (imágenes)
        self.sections = []
        self.section_counter = 0
        self.section_widgets = {}  # section_id -> widgets dict
        self.thumbnail_refs = {}  # Mantener referencias a thumbnails
        
        # Videos para modo automático (videos)
        self.video_sessions = []  # Lista de sesiones de video procesadas
        
        # Estado de procesamiento
        self.is_processing = False
        
        # Frames principales
        self.normal_frame = None
        self.automatic_images_frame = None
        self.automatic_videos_frame = None
        
        self.setup_ui()
        self.check_anki_status()

    def setup_ui(self):
        """Configura la interfaz gráfica."""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Crear los tres frames
        self.setup_normal_mode()
        self.setup_automatic_images_mode()
        self.setup_automatic_videos_mode()
        
        # Mostrar modo normal por defecto
        self.show_normal_mode()
    
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
        
        self.auto_videos_btn = ttk.Button(header_frame, text="🎥 Modo Videos",
                                          command=self.show_automatic_videos_mode)
        self.auto_videos_btn.grid(row=0, column=2, sticky="e", padx=5)
        
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
        self.automatic_images_frame.rowconfigure(1, weight=1)
        
        # Header con botón de retroceso
        header_frame = ttk.Frame(self.automatic_images_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)
        
        back_btn = ttk.Button(header_frame, text="← Volver", command=self.show_normal_mode)
        back_btn.grid(row=0, column=0, sticky="w")
        
        title_label = ttk.Label(header_frame, text="🤖 Modo Automático - Secciones de Imágenes",
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=1, sticky="w", padx=20)
        
        # Panel izquierdo: Secciones (scrollable)
        left_container = ttk.Frame(self.automatic_images_frame)
        left_container.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
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
        right_frame.grid(row=1, column=1, sticky="nsew")
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
        bottom_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        add_section_btn = ttk.Button(bottom_frame, text="+ Añadir Sección", 
                                     command=self.add_section)
        add_section_btn.pack(side="left", padx=5)
        
        check_status_btn = ttk.Button(bottom_frame, text="✓ Chequear Estado",
                                      command=self.check_sections_status)
        check_status_btn.pack(side="left", padx=5)
        
        clear_all_sections_btn = ttk.Button(bottom_frame, text="🗑 Limpiar Todo",
                                            command=self.clear_all_sections)
        clear_all_sections_btn.pack(side="left", padx=5)
        
        check_api_btn = ttk.Button(bottom_frame, text="🔌 Chequear API",
                                   command=self.check_gemini_api)
        check_api_btn.pack(side="left", padx=5)
        
        # Botón principal de procesamiento
        self.process_sections_btn = ttk.Button(bottom_frame, text="🚀 Procesar Secciones",
                                               command=self.process_all_sections_auto)
        self.process_sections_btn.pack(side="left", padx=15)
        
        # Botón de recuperación de sesiones
        recover_btn = ttk.Button(bottom_frame, text="📂 Recuperar Sesión",
                                 command=self.show_recover_session_dialog)
        recover_btn.pack(side="left", padx=5)
        
        # Botón de importar pendientes
        self.pending_btn = ttk.Button(bottom_frame, text="📋 Importar Pendientes",
                                      command=self.import_pending_flashcards)
        self.pending_btn.pack(side="left", padx=5)
        self._update_pending_button()
        
        # Botón de configuración
        config_btn = ttk.Button(bottom_frame, text="⚙️ Configuración",
                               command=self.show_config_dialog)
        config_btn.pack(side="left", padx=5)
        
        # Label del set activo
        self.active_set_label = ttk.Label(bottom_frame, text=f"Set: {self.config_manager.active_set_name}",
                                          font=("Segoe UI", 9), foreground="blue")
        self.active_set_label.pack(side="right", padx=10)
    
    def setup_automatic_videos_mode(self):
        """Configura la vista del modo automático para videos."""
        self.automatic_videos_frame = ttk.Frame(self.root, padding="10")
        self.automatic_videos_frame.columnconfigure(0, weight=3)
        self.automatic_videos_frame.columnconfigure(1, weight=1)
        self.automatic_videos_frame.rowconfigure(1, weight=1)
        
        # Header con botón de retroceso
        header_frame = ttk.Frame(self.automatic_videos_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)
        
        back_btn = ttk.Button(header_frame, text="← Volver", command=self.show_normal_mode)
        back_btn.grid(row=0, column=0, sticky="w")
        
        title_label = ttk.Label(header_frame, text="🎬 Modo Automático - Procesamiento de Videos",
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=1, sticky="w", padx=20)
        
        # Panel izquierdo: Configuración y videos
        left_container = ttk.Frame(self.automatic_videos_frame)
        left_container.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        left_container.columnconfigure(0, weight=1)
        left_container.rowconfigure(1, weight=1)
        
        # Frame de configuración
        config_frame = ttk.LabelFrame(left_container, text="⚙️ Configuración de Segmentación", padding="10")
        config_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        config_frame.columnconfigure(1, weight=1)
        
        # Duración de segmento
        ttk.Label(config_frame, text="Duración de segmento (min):").grid(row=0, column=0, sticky="w", pady=5)
        self.segment_duration_var = tk.DoubleVar(value=3.0)
        segment_scale = ttk.Scale(config_frame, from_=1, to=10, variable=self.segment_duration_var, 
                                 orient="horizontal")
        segment_scale.grid(row=0, column=1, sticky="ew", padx=5)
        self.segment_duration_label = ttk.Label(config_frame, text="3.0 min")
        self.segment_duration_label.grid(row=0, column=2, sticky="w")
        
        def update_segment_label(*args):
            self.segment_duration_label.config(text=f"{self.segment_duration_var.get():.1f} min")
        self.segment_duration_var.trace_add("write", update_segment_label)
        
        # Overlap
        ttk.Label(config_frame, text="Overlap (seg):").grid(row=1, column=0, sticky="w", pady=5)
        self.overlap_var = tk.IntVar(value=30)
        overlap_scale = ttk.Scale(config_frame, from_=0, to=120, variable=self.overlap_var, 
                                 orient="horizontal")
        overlap_scale.grid(row=1, column=1, sticky="ew", padx=5)
        self.overlap_label = ttk.Label(config_frame, text="30 seg")
        self.overlap_label.grid(row=1, column=2, sticky="w")
        
        def update_overlap_label(*args):
            self.overlap_label.config(text=f"{self.overlap_var.get()} seg")
        self.overlap_var.trace_add("write", update_overlap_label)
        
        # Opciones de segmentación
        ttk.Label(config_frame, text="Métodos de segmentación:").grid(row=2, column=0, sticky="nw", pady=5)
        methods_frame = ttk.Frame(config_frame)
        methods_frame.grid(row=2, column=1, columnspan=2, sticky="w", pady=5)
        
        self.use_silence_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(methods_frame, text="Detección de silencios", 
                       variable=self.use_silence_var).pack(anchor="w")
        
        self.use_transcription_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(methods_frame, text="Análisis de transcripción (Whisper)", 
                       variable=self.use_transcription_var).pack(anchor="w")
        
        # Idioma
        ttk.Label(config_frame, text="Idioma del video:").grid(row=3, column=0, sticky="w", pady=5)
        self.language_var = tk.StringVar(value="es")
        language_combo = ttk.Combobox(config_frame, textvariable=self.language_var, 
                                     values=["es", "en", "fr", "de", "it", "pt"], 
                                     state="readonly", width=10)
        language_combo.grid(row=3, column=1, sticky="w", padx=5)
        
        # Frame de videos (scrollable)
        videos_frame = ttk.LabelFrame(left_container, text="📹 Videos Cargados", padding="5")
        videos_frame.grid(row=1, column=0, sticky="nsew")
        videos_frame.columnconfigure(0, weight=1)
        videos_frame.rowconfigure(0, weight=1)
        
        # Canvas con scrollbar para videos
        self.videos_canvas = tk.Canvas(videos_frame, highlightthickness=0)
        videos_scrollbar = ttk.Scrollbar(videos_frame, orient="vertical", 
                                        command=self.videos_canvas.yview)
        
        self.videos_inner_frame = ttk.Frame(self.videos_canvas)
        self.videos_inner_frame.columnconfigure(0, weight=1)
        
        self.videos_canvas.create_window((0, 0), window=self.videos_inner_frame, 
                                        anchor="nw", tags="inner")
        self.videos_canvas.configure(yscrollcommand=videos_scrollbar.set)
        
        self.videos_canvas.grid(row=0, column=0, sticky="nsew")
        videos_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Bind para actualizar scroll region
        self.videos_inner_frame.bind("<Configure>", 
                                     lambda e: self.videos_canvas.configure(
                                         scrollregion=self.videos_canvas.bbox("all")))
        self.videos_canvas.bind("<Configure>", 
                               lambda e: self.videos_canvas.itemconfig("inner", width=e.width))
        
        # Panel derecho: Logs
        right_frame = ttk.LabelFrame(self.automatic_videos_frame, text="Logs de Videos", padding="5")
        right_frame.grid(row=1, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        
        self.video_logs_text = tk.Text(right_frame, width=40, wrap="word")
        self.video_logs_text.grid(row=0, column=0, sticky="nsew")
        
        video_logs_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", 
                                            command=self.video_logs_text.yview)
        video_logs_scrollbar.grid(row=0, column=1, sticky="ns")
        self.video_logs_text.config(yscrollcommand=video_logs_scrollbar.set)
        
        # Panel inferior: Botones
        bottom_frame = ttk.Frame(self.automatic_videos_frame)
        bottom_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        upload_video_btn = ttk.Button(bottom_frame, text="📁 Cargar Video", 
                                      command=self.upload_video)
        upload_video_btn.pack(side="left", padx=5)
        
        clear_videos_btn = ttk.Button(bottom_frame, text="🗑 Limpiar Videos",
                                      command=self.clear_videos)
        clear_videos_btn.pack(side="left", padx=5)
        
        # Botón principal de procesamiento
        self.process_videos_btn = ttk.Button(bottom_frame, text="🚀 Procesar Videos",
                                            command=self.process_videos)
        self.process_videos_btn.pack(side="left", padx=15)
        
        # Botón de configuración
        config_btn = ttk.Button(bottom_frame, text="⚙️ Configuración",
                               command=self.show_config_dialog)
        config_btn.pack(side="left", padx=5)
        
        # Label del set activo
        self.video_set_label = ttk.Label(bottom_frame, text=f"Set: {self.config_manager.active_set_name}",
                                         font=("Segoe UI", 9), foreground="blue")
        self.video_set_label.pack(side="right", padx=10)
    
    def _on_sections_configure(self, event):
        """Actualiza el scroll region cuando cambia el contenido."""
        self.sections_canvas.configure(scrollregion=self.sections_canvas.bbox("all"))
    
    def _on_canvas_configure(self, event):
        """Ajusta el ancho del frame interno al canvas."""
        self.sections_canvas.itemconfig("inner", width=event.width)

    def show_normal_mode(self):
        """Muestra el modo normal."""
        self.automatic_images_frame.grid_forget()
        if self.automatic_videos_frame:
            self.automatic_videos_frame.grid_forget()
        self.normal_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "normal"
    
    def show_automatic_images_mode(self):
        """Muestra el modo automático de imágenes."""
        self.normal_frame.grid_forget()
        if self.automatic_videos_frame:
            self.automatic_videos_frame.grid_forget()
        self.automatic_images_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "automatic_images"
        
        # Añadir una sección inicial si no hay ninguna
        if not self.sections:
            self.add_section()
    
    def show_automatic_videos_mode(self):
        """Muestra el modo automático de videos."""
        self.normal_frame.grid_forget()
        self.automatic_images_frame.grid_forget()
        if self.automatic_videos_frame:
            self.automatic_videos_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "automatic_videos"
    
    def add_section(self):
        """Añade una nueva sección de imágenes."""
        self.section_counter += 1
        section = ImageSection(self.section_counter)
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
            "level_4_analysis": ("4️⃣", "L4-Anal")
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
        
        # Área de drop para imágenes
        drop_frame = tk.Frame(section_frame, bg="#e0e0e0", height=120, relief="groove", bd=2)
        drop_frame.grid(row=2, column=0, sticky="ew", pady=10)
        drop_frame.grid_propagate(False)
        
        drop_label = tk.Label(drop_frame, text="🖼 Arrastra imágenes aquí\no haz clic para seleccionar",
                             bg="#e0e0e0", fg="#666666", font=("Arial", 10))
        drop_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Bind click para seleccionar archivos
        drop_frame.bind("<Button-1>", lambda e, s=section: self.browse_images(s))
        drop_label.bind("<Button-1>", lambda e, s=section: self.browse_images(s))

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
            "thumbnails_frame": thumbnails_frame,
            "info_label": info_label,
            "status_labels": status_labels
        }
        
        # Configurar drag and drop (usando tkinterdnd2 si está disponible, sino solo click)
        self._setup_drop_bindings(drop_frame, section)
    
    def _setup_drop_bindings(self, drop_frame, section):
        """Configura los bindings para drag and drop."""
        # Intentar usar tkinterdnd2 para drag and drop real
        try:
            drop_frame.drop_target_register('DND_Files')
            drop_frame.dnd_bind('<<Drop>>', lambda e, s=section: self._on_drop(e, s))
            drop_frame.dnd_bind('<<DragEnter>>', lambda e: drop_frame.config(bg="#c0e0c0"))
            drop_frame.dnd_bind('<<DragLeave>>', lambda e: drop_frame.config(bg="#e0e0e0"))
        except:
            # Si no está disponible tkinterdnd2, solo usar click
            pass
    
    def _on_drop(self, event, section):
        """Maneja el evento de drop de archivos."""
        files = self.root.tk.splitlist(event.data)
        for file_path in files:
            if file_path.lower().endswith(self.SUPPORTED_FORMATS):
                self._add_image_to_section(section, file_path)
        
        # Restaurar color
        widgets = self.section_widgets.get(section.section_id)
        if widgets:
            widgets["drop_frame"].config(bg="#e0e0e0")

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
            import tempfile
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
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar {section.title} y todas sus imágenes?"):
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
        for idx, section in enumerate(self.sections):
            widgets = self.section_widgets.get(section.section_id)
            if widgets:
                widgets["frame"].grid(row=idx, column=0, sticky="ew", pady=5, padx=5)

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
        
        # Confirmar
        total_images = sum(len(s.images) for s in sections_with_images)
        msg = f"¿Procesar {len(sections_with_images)} sección(es) con {total_images} imagen(es)?\n\n"
        msg += "Esto realizará:\n"
        msg += "1. Extracción OCR de cada sección\n"
        msg += "2. Generación de 4 tipos de flashcards con Gemini\n"
        msg += "3. Importación automática a Anki\n\n"
        msg += "Nota: Hay 60 segundos de espera entre secciones."
        
        if not messagebox.askyesno("Confirmar procesamiento", msg):
            return
        
        # Guardar sesión automáticamente antes de procesar
        self._save_current_session()
        
        # Resetear indicadores de estado
        self._reset_all_status_indicators()
        
        # Iniciar procesamiento en thread
        self.is_processing = True
        self.process_sections_btn.config(state="disabled", text="⏳ Procesando...")
        
        thread = threading.Thread(target=self._process_sections_thread, daemon=True)
        thread.start()
    
    def _process_sections_thread(self):
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
            
            # Procesar todas las secciones
            results = self.flashcard_generator.process_all_sections(
                sections=sections_data,
                converter=self.converter,
                anki_manager=self.anki_manager,
                progress_callback=self._on_section_progress
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
    
    def _show_processing_summary(self, results: list):
        """Muestra resumen del procesamiento y actualiza indicadores visuales."""
        self.auto_log("\n" + "="*60)
        self.auto_log("📊 RESUMEN FINAL DE PROCESAMIENTO")
        self.auto_log("="*60)
        
        total_flashcards = 0
        successful_sections = 0
        
        for result in results:
            section_title = result.get("section", "Unknown")
            self.auto_log(f"\n📁 {section_title}:")
            
            # Buscar la sección correspondiente para actualizar sus indicadores
            section_id = None
            for s in self.sections:
                if s.title == section_title:
                    section_id = s.section_id
                    break
            
            if result.get("success"):
                successful_sections += 1
                for card_type, type_result in result.get("results", {}).items():
                    if type_result.get("success"):
                        count = type_result.get("count", 0)
                        deck = type_result.get("deck", "")
                        total_flashcards += count
                        self.auto_log(f"   ✅ {card_type}: {count} flashcards → {deck}")
                        # Actualizar indicador visual
                        if section_id:
                            self.root.after(0, lambda sid=section_id, ct=card_type, c=count: 
                                          self._update_section_status(sid, ct, True, c))
                    else:
                        self.auto_log(f"   ❌ {card_type}: {type_result.get('error', 'Error')}")
                        # Actualizar indicador visual como fallido
                        if section_id:
                            self.root.after(0, lambda sid=section_id, ct=card_type: 
                                          self._update_section_status(sid, ct, False, 0))
            else:
                self.auto_log(f"   ❌ Error: {result.get('error', 'Unknown error')}")
                # Marcar todos los tipos como fallidos
                if section_id:
                    for card_type in ["basic", "multiple_choice", "cloze", "vocabulary"]:
                        self.root.after(0, lambda sid=section_id, ct=card_type: 
                                      self._update_section_status(sid, ct, False, 0))
        
        self.auto_log(f"\n{'='*60}")
        self.auto_log(f"✅ PROCESAMIENTO COMPLETADO")
        self.auto_log(f"   • Secciones procesadas: {successful_sections}/{len(results)}")
        self.auto_log(f"   • Total flashcards importadas: {total_flashcards}")
        self.auto_log("="*60 + "\n")
        
        # Actualizar botón de pendientes
        self.root.after(0, self._update_pending_button)
        
        # Mostrar popup
        self.root.after(0, lambda: messagebox.showinfo(
            "Procesamiento completado",
            f"Secciones procesadas: {successful_sections}/{len(results)}\n"
            f"Total flashcards importadas: {total_flashcards}"
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
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.auto_logs_text.insert("end", f"[{timestamp}] {message}\n")
        self.auto_logs_text.see("end")
        self.root.update()
    
    def video_log(self, message: str):
        """Añade un mensaje al log del modo de videos."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.video_logs_text.insert("end", f"[{timestamp}] {message}\n")
        self.video_logs_text.see("end")
        self.root.update()
    
    # ==================== MÉTODOS DE VIDEOS ====================
    
    def upload_video(self):
        """Abre diálogo para seleccionar un video."""
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
        
        # Añadir a la lista de videos
        self._add_video_to_list(file_path)
    
    def _add_video_to_list(self, video_path: str):
        """Añade un video a la lista visual."""
        video_name = os.path.basename(video_path)
        video_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
        
        # Crear widget para el video
        video_frame = ttk.Frame(self.videos_inner_frame, relief="groove", borderwidth=2)
        video_frame.grid(row=len(self.video_sessions), column=0, sticky="ew", pady=5, padx=5)
        video_frame.columnconfigure(1, weight=1)
        
        # Icono y nombre
        ttk.Label(video_frame, text="🎬", font=("Segoe UI", 16)).grid(row=0, column=0, padx=5, pady=5)
        
        info_frame = ttk.Frame(video_frame)
        info_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        
        ttk.Label(info_frame, text=video_name, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(info_frame, text=f"Tamaño: {video_size:.1f} MB", 
                 font=("Segoe UI", 9), foreground="gray").pack(anchor="w")
        
        # Botón eliminar
        delete_btn = ttk.Button(video_frame, text="🗑", width=3,
                               command=lambda: self._remove_video(video_path, video_frame))
        delete_btn.grid(row=0, column=2, padx=5)
        
        # Guardar referencia
        self.video_sessions.append({
            "path": video_path,
            "name": video_name,
            "frame": video_frame,
            "processed": False
        })
    
    def _remove_video(self, video_path: str, frame: ttk.Frame):
        """Elimina un video de la lista."""
        # Eliminar widget
        frame.destroy()
        
        # Eliminar de la lista
        self.video_sessions = [v for v in self.video_sessions if v["path"] != video_path]
        
        self.video_log(f"🗑 Video eliminado: {os.path.basename(video_path)}")
        
        # Reorganizar grid
        for idx, video_data in enumerate(self.video_sessions):
            video_data["frame"].grid(row=idx, column=0, sticky="ew", pady=5, padx=5)
    
    def clear_videos(self):
        """Limpia todos los videos."""
        if not self.video_sessions:
            return
        
        if messagebox.askyesno("Confirmar", "¿Eliminar todos los videos cargados?"):
            for video_data in self.video_sessions:
                video_data["frame"].destroy()
            
            self.video_sessions.clear()
            self.video_log("🗑 Todos los videos eliminados")
    
    def process_videos(self):
        """Procesa todos los videos cargados."""
        if not self.video_sessions:
            messagebox.showwarning("Sin videos", "No hay videos cargados para procesar.")
            return
        
        if self.is_processing:
            messagebox.showwarning("En proceso", "Ya hay un procesamiento en curso.")
            return
        
        # Confirmar
        msg = f"¿Procesar {len(self.video_sessions)} video(s)?\n\n"
        msg += "Esto realizará:\n"
        msg += "1. Transcripción con Whisper (si está habilitado)\n"
        msg += "2. Segmentación inteligente del video\n"
        msg += "3. Extracción de contenido de cada segmento\n"
        msg += "4. Generación de flashcards con Gemini\n"
        msg += "5. Importación automática a Anki\n\n"
        msg += "Nota: Este proceso puede tomar varios minutos por video."
        
        if not messagebox.askyesno("Confirmar procesamiento", msg):
            return
        
        # Iniciar procesamiento en thread
        self.is_processing = True
        self.process_videos_btn.config(state="disabled", text="⏳ Procesando...")
        
        thread = threading.Thread(target=self._process_videos_thread, daemon=True)
        thread.start()
    
    def _process_videos_thread(self):
        """Thread de procesamiento de videos."""
        try:
            # Obtener configuración
            segment_duration = self.segment_duration_var.get() * 60  # Convertir a segundos
            overlap = self.overlap_var.get()
            use_silence = self.use_silence_var.get()
            use_transcription = self.use_transcription_var.get()
            language = self.language_var.get()
            
            # Obtener configuración activa de flashcards
            active_config = self.config_manager.get_active_set()
            
            # Inicializar o actualizar generador con la configuración
            if not self.flashcard_generator:
                self.flashcard_generator = GeminiFlashcardGenerator(
                    log_callback=self.video_log,
                    config_set=active_config
                )
            else:
                self.flashcard_generator.update_config(active_config)
            
            self.video_log(f"📋 Usando configuración: {active_config.get('name', 'Por Defecto')}")
            self.video_log(f"   Modelo: {self.flashcard_generator.model_name}")
            
            total_flashcards = 0
            
            # Procesar cada video
            for idx, video_data in enumerate(self.video_sessions, 1):
                video_path = video_data["path"]
                video_name = video_data["name"]
                
                self.video_log(f"\n{'='*60}")
                self.video_log(f"🎬 PROCESANDO VIDEO {idx}/{len(self.video_sessions)}: {video_name}")
                self.video_log(f"{'='*60}")
                
                # Procesar video con video_processor
                result = self.video_processor.process_video(
                    video_path=video_path,
                    segment_duration=segment_duration,
                    overlap=overlap,
                    use_silence_detection=use_silence,
                    use_transcription_analysis=use_transcription,
                    language=language
                )
                
                if not result.get("success"):
                    self.video_log(f"❌ Error procesando video: {result.get('error')}")
                    continue
                
                segments = result.get("segments", [])
                self.video_log(f"✅ Video segmentado en {len(segments)} partes")
                
                # Procesar cada segmento
                for seg_idx, segment in enumerate(segments, 1):
                    self.video_log(f"\n📊 Segmento {seg_idx}/{len(segments)}")
                    
                    if not segment.file_path or not os.path.exists(segment.file_path):
                        self.video_log(f"⚠️ Archivo de segmento no encontrado")
                        continue
                    
                    # Extraer frames del segmento (tomar 3 frames distribuidos)
                    # Por ahora, usar el segmento completo como "imagen"
                    # TODO: Implementar extracción de frames clave
                    
                    # Por ahora, procesar el video completo como si fuera una imagen
                    # En el futuro, extraer frames y procesarlos
                    self.video_log(f"⚠️ Procesamiento de segmentos de video aún no implementado completamente")
                    self.video_log(f"   Se requiere extracción de frames clave del segmento")
                
                # Marcar como procesado
                video_data["processed"] = True
                
                # Limpiar sesión temporal
                session_dir = result.get("session_dir")
                if session_dir:
                    self.video_processor.cleanup_session(session_dir)
            
            self.video_log(f"\n{'='*60}")
            self.video_log(f"✅ PROCESAMIENTO COMPLETADO")
            self.video_log(f"   • Videos procesados: {len(self.video_sessions)}")
            self.video_log(f"   • Total flashcards: {total_flashcards}")
            self.video_log(f"{'='*60}\n")
            
            # Mostrar popup
            self.root.after(0, lambda: messagebox.showinfo(
                "Procesamiento completado",
                f"Videos procesados: {len(self.video_sessions)}\n"
                f"Total flashcards: {total_flashcards}\n\n"
                f"Nota: La extracción de frames y generación de flashcards\n"
                f"desde segmentos de video está en desarrollo."
            ))
            
        except Exception as e:
            error_msg = str(e)
            self.video_log(f"\n❌ ERROR CRÍTICO: {error_msg}")
            self.root.after(0, lambda msg=error_msg: messagebox.showerror(
                "Error", f"Error durante el procesamiento:\n{msg}"))
        
        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.process_videos_btn.config(
                state="normal", text="🚀 Procesar Videos"
            ))
    
    def log(self, message: str):
        """Añade un mensaje al log del modo normal."""
        self.logs_text.insert("end", f"{message}\n")
        self.logs_text.see("end")
        self.root.update()

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
                    
                    # Importar a Anki
                    prefix = self.prefix_var.get().strip() or "Flashcards"
                    deck_name = f"{prefix} - {card_label}"
                    
                    success, msg, count = self.anki_manager.sync_flashcards_to_anki(
                        deck_name, flashcards, card_type
                    )
                    
                    if success:
                        self.log(f"✓ {msg}")
                        total_imported += count
                    else:
                        self.log(f"✗ {msg}")
                
                self.log(f"\n{'='*50}")
                self.log(f"✓ Total imported: {total_imported} flashcards")
                messagebox.showinfo("Success", f"Imported {total_imported} flashcards to Anki!")
                
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
                "first_section": first_section_title,
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
    
    def _load_sessions(self) -> list:
        """Carga las sesiones guardadas."""
        try:
            if os.path.exists(SESSIONS_FILE):
                with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
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
            first_section = session.get("first_section", "Sin título")
            num_sections = len(session.get("sections", []))
            total_images = sum(len(s.get("images", [])) for s in session.get("sections", []))
            
            display_text = f"{timestamp} - {first_section[:30]}... ({num_sections} secciones, {total_images} imgs)"
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
    
    def _recover_session(self, session_data: dict, replace: bool):
        """Recupera una sesión guardada."""
        if replace:
            # Limpiar secciones actuales
            for section_id, widgets in list(self.section_widgets.items()):
                widgets["frame"].destroy()
            self.section_widgets.clear()
            self.thumbnail_refs.clear()
            self.sections.clear()
            self.section_counter = 0
        
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

    # ==================== FLASHCARDS PENDIENTES ====================
    
    def _update_pending_button(self):
        """Actualiza el texto del botón de pendientes con la cantidad."""
        try:
            if not self.flashcard_generator:
                self.flashcard_generator = GeminiFlashcardGenerator(log_callback=self.auto_log)
            
            count = self.flashcard_generator.get_pending_count()
            if count > 0:
                self.pending_btn.config(text=f"📋 Importar Pendientes ({count})")
            else:
                self.pending_btn.config(text="📋 Importar Pendientes")
        except:
            pass
    
    def import_pending_flashcards(self):
        """Importa las flashcards pendientes."""
        if not self.flashcard_generator:
            self.flashcard_generator = GeminiFlashcardGenerator(log_callback=self.auto_log)
        
        count = self.flashcard_generator.get_pending_count()
        
        if count == 0:
            messagebox.showinfo("Sin pendientes", "No hay flashcards pendientes de importar.")
            return
        
        msg = f"Hay {count} lote(s) de flashcards pendientes de importar.\n\n"
        msg += "Asegúrate de que Anki esté abierto antes de continuar.\n\n"
        msg += "¿Deseas importarlas ahora?"
        
        if not messagebox.askyesno("Importar Pendientes", msg):
            return
        
        # Importar en thread
        def do_import():
            self.auto_log("\n" + "="*50)
            self.auto_log("📋 IMPORTANDO FLASHCARDS PENDIENTES...")
            self.auto_log("="*50)
            
            result = self.flashcard_generator.import_pending_flashcards(self.anki_manager)
            
            self.auto_log("="*50 + "\n")
            
            # Actualizar botón
            self.root.after(0, self._update_pending_button)
            
            # Si se importaron exitosamente, resetear indicadores visuales
            if result.get("imported", 0) > 0:
                self.root.after(0, self._reset_all_status_indicators)
                self.root.after(0, lambda: messagebox.showinfo(
                    "✅ Importación completada",
                    f"Se importaron {result['imported']} flashcards exitosamente.\n\n"
                    f"Pendientes restantes: {result.get('still_pending', 0)}\n\n"
                    f"Los indicadores visuales se han reseteado."
                ))
            elif result.get("still_pending", 0) > 0:
                self.root.after(0, lambda: messagebox.showwarning(
                    "⚠️ Importación fallida",
                    f"No se pudieron importar las flashcards.\n\n"
                    f"Verifica que Anki esté abierto y AnkiConnect instalado.\n\n"
                    f"Pendientes: {result.get('still_pending', 0)}"
                ))
        
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
            "level_4_analysis": "4️⃣ Nivel 4 - Análisis (Analizar)"
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
            
            # Determinar qué tipos mostrar
            if any(k.startswith("level_") for k in active_types.keys()):
                type_keys = ["level_1_cloze", "level_2_relations", "level_3_application", "level_4_analysis"]
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
            self.active_set_label.config(text=f"Set: {set_name}")
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


def main():
    """Inicia la aplicación."""
    root = tk.Tk()
    app = AnkiImportInterface(root)
    root.mainloop()


if __name__ == "__main__":
    main()
