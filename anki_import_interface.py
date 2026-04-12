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
import math
from flashcards_converter import FlashcardsConverter
from document_processor import DocumentProcessor
from anki_sync_manager import AnkiSyncManager
from config_sets_manager import ConfigSetsManager
from video_processor import VideoProcessor, VideoSection, VideoSegment
import tempfile
from gemini_flashcard_generator import GeminiFlashcardGenerator


# Carpeta maestra para archivos generados
MASTER_FOLDER = "Flashcards Programa"

# Asegurar que la carpeta maestra exista
if not os.path.exists(MASTER_FOLDER):
    os.makedirs(MASTER_FOLDER, exist_ok=True)

# Archivo para guardar sesiones
SESSIONS_FILE = os.path.join(MASTER_FOLDER, "flashcard_sessions.json")
TEXT_SESSIONS_FILE = os.path.join(MASTER_FOLDER, "flashcard_text_sessions.json")


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
        
        self.converter = FlashcardsConverter()
        self.anki_manager = AnkiSyncManager()
        self.flashcard_generator = None  # Se inicializa bajo demanda
        self.config_manager = ConfigSetsManager()  # Gestor de configuraciones
        self.video_processor = VideoProcessor(log_callback=self.video_log)  # Procesador de videos
        
        # Modo actual: "normal", "automatic_images", "automatic_videos", "automatic_text", "automatic_books"
        self.current_mode = "normal"
        
        self.document_processor = DocumentProcessor(log_callback=self.text_log)  # Para PDF/Word
        
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
        
        # Videos para modo automático (videos)
        self.video_sessions = []  # Lista de sesiones de video procesadas
        self.current_video_path = None  # Video actualmente cargado
        self.current_video_segments = []  # Lista de VideoSegment del video actual
        self.video_sections = []  # Lista de VideoSection para agrupar segmentos
        self.video_section_counter = 0
        self.video_segment_widgets = {}  # segment_id -> widgets dict
        self.video_section_widgets = {}  # section_id -> widgets dict
        self.current_playing_audio = None  # Referencia al audio en reproducción
        
        # Estado de procesamiento
        self.is_processing = False
        
        # Frames principales
        self.normal_frame = None
        self.automatic_images_frame = None
        self.automatic_text_frame = None
        self.automatic_videos_frame = None
        self.automatic_books_frame = None
        
        self.setup_ui()
        self.check_anki_status()

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
        self.automatic_books_frame.columnconfigure(0, weight=1)
        
        # Header con botón de retroceso
        header_frame = ttk.Frame(self.automatic_books_frame)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.columnconfigure(1, weight=1)
        
        back_btn = ttk.Button(header_frame, text="← Volver", command=self.show_normal_mode)
        back_btn.grid(row=0, column=0, sticky="w")
        
        title_label = ttk.Label(header_frame, text="📚 Modo Libros - PDF y Word completo",
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=1, sticky="w", padx=20)
        
        # Frame de configuración y carga
        config_frame = ttk.LabelFrame(self.automatic_books_frame, text="⚙️ Carga y Segmentación", padding="20")
        config_frame.grid(row=1, column=0, sticky="ew", pady=(10, 20), padx=5)
        config_frame.columnconfigure(1, weight=1)
        
        # Archivo
        ttk.Label(config_frame, text="Archivo (PDF/Word):").grid(row=0, column=0, sticky="w", pady=5)
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
        
        # Segmentación
        ttk.Label(config_frame, text="Páginas por Sección:").grid(row=1, column=0, sticky="w", pady=5)
        self.pages_per_section_var = tk.IntVar(value=10)
        pages_spin = ttk.Spinbox(config_frame, from_=1, to=100, textvariable=self.pages_per_section_var, width=10)
        pages_spin.grid(row=1, column=1, sticky="w", padx=5)
        
        ttk.Label(config_frame, text="Solape de Páginas:").grid(row=2, column=0, sticky="w", pady=5)
        self.pages_overlap_var = tk.IntVar(value=1)
        overlap_spin = ttk.Spinbox(config_frame, from_=0, to=10, textvariable=self.pages_overlap_var, width=10)
        overlap_spin.grid(row=2, column=1, sticky="w", padx=5)
        
        # Botón de acción
        segment_btn = ttk.Button(config_frame, text="📑 Segmentar y Crear Secciones", 
                                command=self.process_book_to_sections)
        segment_btn.grid(row=3, column=0, columnspan=3, pady=20)

    def process_book_to_sections(self):
        """Procesa el PDF/Word y crea las secciones de texto."""
        path = self.book_path_var.get().strip()
        if not path or not os.path.exists(path):
            messagebox.showwarning("Archivo no encontrado", "Por favor selecciona un archivo PDF o Word válido.")
            return
            
        pages_per_section = self.pages_per_section_var.get()
        overlap = self.pages_overlap_var.get()
        
        self.text_log(f"📑 Procesando libro: {os.path.basename(path)}...")
        
        pages_content = []
        if path.lower().endswith('.pdf'):
            pages_content = self.document_processor.extract_text_from_pdf(path)
        elif path.lower().endswith('.docx'):
            pages_content = self.document_processor.extract_text_from_docx(path)
            
        if not pages_content:
            messagebox.showerror("Error", "No se pudo extraer texto del documento.")
            return
            
        sections = self.document_processor.segment_pages(pages_content, pages_per_section, overlap)
        
        # Convertir a secciones de texto
        self.show_automatic_text_mode()
        self.clear_all_text_sections()
        
        for sec_data in sections:
            self.add_text_section()
            last_section = self.text_sections[-1]
            last_section.title = sec_data["title"]
            last_section.text = sec_data["content"]
            
            # Actualizar widget
            widgets = self.text_section_widgets.get(last_section.section_id)
            if widgets:
                widgets["title_var"].set(sec_data["title"])
                widgets["title_label"].config(text=sec_data["title"])
                widgets["text_widget"].delete("1.0", tk.END)
                widgets["text_widget"].insert("1.0", sec_data["content"])
                
        messagebox.showinfo("Procesamiento Completo", f"Se han creado {len(sections)} secciones de texto.")

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

    def _hide_all_frames(self):
        if self.normal_frame: self.normal_frame.grid_forget()
        if self.automatic_images_frame: self.automatic_images_frame.grid_forget()
        if self.automatic_text_frame: self.automatic_text_frame.grid_forget()
        if self.automatic_videos_frame: self.automatic_videos_frame.grid_forget()
        if self.automatic_books_frame: self.automatic_books_frame.grid_forget()
    
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
        
        # Duración de segmento
        ttk.Label(config_frame, text="Duración de segmento (min):").grid(row=0, column=0, sticky="w", pady=5)
        self.segment_duration_var = tk.DoubleVar(value=3.0)
        segment_spinbox = ttk.Spinbox(config_frame, from_=0.1, to=999.0, increment=0.5, 
                                      textvariable=self.segment_duration_var, width=10)
        segment_spinbox.grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(config_frame, text="minutos").grid(row=0, column=2, sticky="w")
        
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
        
        # Calidad de transcripción (Modelo de Whisper)
        ttk.Label(config_frame, text="Calidad de Transcripción (Modelo):").grid(row=2, column=0, sticky="w", pady=5)
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
        model_combo.grid(row=2, column=1, sticky="w", padx=5)

        # Idioma
        ttk.Label(config_frame, text="Idioma del video:").grid(row=3, column=0, sticky="w", pady=5)
        self.language_var = tk.StringVar(value="es")
        language_combo = ttk.Combobox(config_frame, textvariable=self.language_var, 
                                     values=["es", "en", "fr", "de", "it", "pt"], 
                                     state="readonly", width=10)
        language_combo.grid(row=3, column=1, sticky="w", padx=5)
        
        # --- NUEVO: Descarga de YouTube ---
        ttk.Label(config_frame, text="📺 Descargar de YouTube (URL):").grid(row=4, column=0, sticky="w", pady=5)
        self.yt_url_entry = ttk.Entry(config_frame, textvariable=self.youtube_url_var, width=50)
        self.yt_url_entry.grid(row=4, column=1, sticky="w", padx=5)
        
        self.yt_download_btn = ttk.Button(config_frame, text="📥 Descargar", command=self.download_youtube_video)
        self.yt_download_btn.grid(row=4, column=2, sticky="w")
        
        # ----- Área de Drop de Video -----
        drop_frame = tk.Frame(config_frame, bg="#e0e0e0", height=80, relief="groove", bd=2)
        drop_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(15, 15))
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
        
        # Botones de control y status
        buttons_frame = ttk.Frame(config_frame)
        buttons_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 5))
        
        # Separador visual
        ttk.Separator(config_frame, orient="horizontal").grid(row=5, column=0, columnspan=3, sticky="ew", pady=(30, 0))
        
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
        
        self.create_sections_btn = ttk.Button(grouping_frame, text="✨ Crear Secciones",
                                             command=self.create_video_sections_from_segments,
                                             state="disabled")
        self.create_sections_btn.grid(row=0, column=2, padx=5)
        
        self.view_segments_btn = ttk.Button(grouping_frame, text="👁️ Ver Segmentos Procesados",
                                            command=self.show_segments_window,
                                            state="disabled")
        self.view_segments_btn.grid(row=1, column=0, columnspan=3, pady=(10, 0), sticky="ew")

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

    def show_normal_mode(self):
        """Muestra el modo normal."""
        self.automatic_images_frame.grid_forget()
        if self.automatic_text_frame:
            self.automatic_text_frame.grid_forget()
        if self.automatic_videos_frame:
            self.automatic_videos_frame.grid_forget()
        self.normal_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "normal"
    
    def show_automatic_images_mode(self):
        """Muestra el modo automático de imágenes."""
        self.normal_frame.grid_forget()
        if self.automatic_text_frame:
            self.automatic_text_frame.grid_forget()
        if self.automatic_videos_frame:
            self.automatic_videos_frame.grid_forget()
        self.automatic_images_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "automatic_images"
        
        # Añadir una sección inicial si no hay ninguna
        if not self.sections:
            self.add_section()
    
    def show_automatic_text_mode(self):
        """Muestra el modo automático de texto."""
        self.normal_frame.grid_forget()
        self.automatic_images_frame.grid_forget()
        if self.automatic_videos_frame:
            self.automatic_videos_frame.grid_forget()
        if self.automatic_text_frame:
            self.automatic_text_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "automatic_text"
        
        # Añadir una sección inicial si no hay ninguna
        if not self.text_sections:
            self.add_text_section()
    
    def show_automatic_videos_mode(self):
        """Muestra el modo automático de videos."""
        self.normal_frame.grid_forget()
        self.automatic_images_frame.grid_forget()
        if self.automatic_text_frame:
            self.automatic_text_frame.grid_forget()
        if self.automatic_videos_frame:
            self.automatic_videos_frame.grid(row=0, column=0, sticky="nsew")
        self.current_mode = "automatic_videos"
    
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
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar {section.title}?\n\nAl eliminar, las secciones siguientes se re-enumerarán dinámicamente según el prefijo configurado."):
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
            
            # Renombrado dinámico
            self.apply_hierarchy_names()
    
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
    
    def text_log(self, message: str):
        """Añade un mensaje al log del modo de texto."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text_logs_text.insert("end", f"[{timestamp}] {message}\n")
        self.text_logs_text.see("end")
        self.root.update()
    
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
        
        if messagebox.askyesno("Confirmar", f"¿Eliminar {section.title}?\n\nAl eliminar, las secciones siguientes se re-enumerarán dinámicamente según el prefijo configurado."):
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
            
            # Renombrado dinámico
            self.apply_hierarchy_names()
    
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
        
        # Confirmar
        total_chars = sum(len(s.get_text()) for s in sections_with_text)
        msg = f"¿Procesar {len(sections_with_text)} sección(es) con {total_chars:,} caracteres?\n\n"
        msg += "Esto realizará:\n"
        msg += "1. Generación SECUENCIAL de flashcards con Gemini\n"
        msg += "2. Importación automática a Anki\n\n"
        msg += "Nota: El procesamiento es secuencial (API1→API2→API3→API4)."
        
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
                self.flashcard_generator.update_config(active_config)
            
            self.text_log(f"📋 Usando configuración: {active_config.get('name', 'Por Defecto')}")
            self.text_log(f"   Modelo: {self.flashcard_generator.model_name}")
            self.text_log(f"   Tipos activos: {[k for k, v in self.flashcard_generator.active_types.items() if v]}")
            self.text_log(f"   Modo: SECUENCIAL (API1→API2→API3→API4)")
            
            total_flashcards = 0
            
            # Procesar cada sección
            for idx, section in enumerate(self.text_sections, 1):
                texto = section.get_text().strip()
                if not texto:
                    continue
                
                self.text_log(f"\n{'='*60}")
                self.text_log(f"📁 PROCESANDO SECCIÓN {idx}/{len(self.text_sections)}: {section.title}")
                self.text_log(f"{'='*60}")
                self.text_log(f"   📝 Caracteres: {len(texto):,}")
                
                # Paso 1: Estructuración con IA (Opcional)
                texto_para_tarjetas = texto
                if self.use_ai_structuring_text.get():
                    self.text_log(f"\n✨ PASO 1: ESTRUCTURACIÓN CON IA (Estudiante Experto)")
                    # Usamos extract_text_from_files (que usa el OCR_PROMPT mejorado) 
                    # pasando el texto en un archivo temporal
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', encoding='utf-8', delete=False) as tf:
                        tf.write(texto)
                        temp_path = tf.name
                    
                    try:
                        structured_text = self.flashcard_generator.extract_text_from_files([temp_path])
                        if structured_text.strip():
                            texto_para_tarjetas = structured_text
                            self.text_log(f"   ✅ Estructuración completada ({len(texto_para_tarjetas)} caracteres)")
                            
                            # Guardar la versión estructurada (Expert Notes)
                            if hasattr(self.flashcard_generator, '_save_ocr_transcript'):
                                save_deck = grandparent_str
                                if hasattr(self, 'current_text_session') and self.current_text_session:
                                    save_deck = self.current_text_session
                                
                                self.flashcard_generator._save_ocr_transcript(
                                    texto_para_tarjetas, 
                                    save_deck, 
                                    f"{section.title}_Expert_Notes",
                                    subfolder="expert_notes",
                                    extension="md"
                                )
                        else:
                            self.text_log(f"   ⚠️ Falló la estructuración, se usará el texto original.")
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                # Paso 2: Generar flashcards SECUENCIALMENTE
                self.text_log(f"\n🤖 PASO 2: GENERACIÓN SECUENCIAL DE FLASHCARDS")
                results = self.flashcard_generator.generate_all_flashcards_sequential(texto_para_tarjetas)
                
                # Procesar resultados
                for card_type, result in results.items():
                    if result.get("success"):
                        content = result.get("content", "")
                        
                        # Convertir a flashcards
                        flashcards = self.converter.convert(content, card_type)
                        
                        if flashcards:
                            # Parsear TSV a lista de flashcards
                            flashcard_list = []
                            for line in flashcards.strip().split('\n'):
                                if '\t' in line:
                                    front, back = line.split('\t', 1)
                                    flashcard_list.append({"front": front.strip(), "back": back.strip()})
                            
                            if flashcard_list:
                                # Construir nombre de mazo con jerarquía
                                deck_name = ""
                                if bisabuelo_str:
                                    deck_name += f"{bisabuelo_str}::"
                                if grandparent_str:
                                    deck_name += f"{grandparent_str}::"
                                deck_name += f"{section.title}::{card_type}"
                                
                                # Guardar respaldo del flashcard con sufijo de tipo
                                if hasattr(self.flashcard_generator, '_save_ocr_transcript'):
                                    # Determinar carpeta de guardado (preferir sesión actual si existe)
                                    save_deck = grandparent_str
                                    sub_folder = "flashcards"
                                    
                                    # Si estamos en una sesión activa, usar esa ruta
                                    if hasattr(self, 'current_text_session') and self.current_text_session:
                                        save_deck = self.current_text_session
                                    
                                    self.flashcard_generator._save_ocr_transcript(
                                        flashcards, 
                                        save_deck, 
                                        f"{section.title}_{card_type}",
                                        subfolder=sub_folder
                                    )
                                
                                # Importar a Anki
                                success, msg, count = self.anki_manager.sync_flashcards_to_anki(
                                    deck_name, flashcard_list, card_type
                                )
                                
                                if success:
                                    self.text_log(f"   ✅ {card_type}: {count} flashcards → {deck_name}")
                                    total_flashcards += count
                                    # Actualizar indicador visual
                                    self.root.after(0, lambda sid=section.section_id, ct=card_type, c=count: 
                                                  self._update_text_section_status(sid, ct, True, c))
                                else:
                                    self.text_log(f"   ❌ {card_type}: {msg}")
                                    self.root.after(0, lambda sid=section.section_id, ct=card_type: 
                                                  self._update_text_section_status(sid, ct, False, 0))
                            else:
                                self.text_log(f"   ⚠️ {card_type}: No se pudieron parsear flashcards")
                                self.root.after(0, lambda sid=section.section_id, ct=card_type: 
                                              self._update_text_section_status(sid, ct, False, 0))
                        else:
                            self.text_log(f"   ⚠️ {card_type}: No se pudieron parsear flashcards")
                            self.root.after(0, lambda sid=section.section_id, ct=card_type: 
                                          self._update_text_section_status(sid, ct, False, 0))
                    else:
                        self.text_log(f"   ❌ {card_type}: {result.get('error')}")
                        self.root.after(0, lambda sid=section.section_id, ct=card_type: 
                                      self._update_text_section_status(sid, ct, False, 0))
            
            self.text_log(f"\n{'='*60}")
            self.text_log(f"✅ PROCESAMIENTO COMPLETADO")
            self.text_log(f"   • Secciones procesadas: {len([s for s in self.text_sections if s.get_text().strip()])}")
            self.text_log(f"   • Total flashcards importadas: {total_flashcards}")
            self.text_log("="*60 + "\n")
            
            # Mostrar popup
            self.root.after(0, lambda: messagebox.showinfo(
                "Procesamiento completado",
                f"Secciones procesadas: {len([s for s in self.text_sections if s.get_text().strip()])}\n"
                f"Total flashcards importadas: {total_flashcards}"
            ))
            
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
        
        def run_download():
            path = self.youtube_downloader.download_video(url, self.video_log)
            
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
            # Obtener configuración
            segment_duration = self.segment_duration_var.get() * 60  # Convertir a segundos
            overlap = self.overlap_var.get()
            language = self.language_var.get()
            
            # NOTA: model_size se retiene en la UI visualmente pero no se usa para Gemini
            # La rotación de modelos y fallbacks está hardcodeada internamente
            
            self.video_log(f"\n{'='*60}")
            self.video_log(f"🎬 PROCESANDO VIDEO (Motor: Gemini Multimodal & API Rotation)")
            self.video_log(f"{'='*60}")
            
            # 0. Crear sesión para guardado jerárquico
            bisabuelo = self.great_grandparent_deck.get().strip()
            grandparent = self.grandparent_deck.get().strip() or "General"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if bisabuelo:
                self.current_video_session = os.path.join(MASTER_FOLDER, bisabuelo, grandparent, f"Session_{timestamp}")
            else:
                self.current_video_session = os.path.join(MASTER_FOLDER, grandparent, f"Session_{timestamp}")
            
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
                father_prefix=self.parent_prefix.get()
            )
            
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
            "level_4_analysis": ("4️⃣", "L4")
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
        if messagebox.askyesno("Confirmar", f"¿Eliminar {section.title}?\n\nAl eliminar, las secciones siguientes se re-enumerarán dinámicamente según el prefijo configurado."):
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
            
            # Renombrado dinámico
            self.apply_hierarchy_names()
            
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
        
        # Extraer string de tkinter en el hilo principal para evitar vacíos
        bisabuelo_str = self.great_grandparent_deck.get().strip()
        grandparent_str = self.grandparent_deck.get().strip()
        
        thread = threading.Thread(target=self._process_video_sections_thread, args=(bisabuelo_str, grandparent_str), daemon=True)
        thread.start()
    
    def _process_video_sections_thread(self, bisabuelo_str, grandparent_str):
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
                self.flashcard_generator.update_config(active_config)
            
            self.video_log(f"\n📋 Usando configuración: {active_config.get('name', 'Por Defecto')}")
            self.video_log(f"   Modelo: {self.flashcard_generator.model_name}")
            
            total_flashcards = 0
            
            # Procesar cada sección
            for idx, section in enumerate(self.video_sections, 1):
                self.video_log(f"\n{'='*60}")
                self.video_log(f"📁 PROCESANDO SECCIÓN {idx}/{len(self.video_sections)}: {section.title}")
                self.video_log(f"{'='*60}")
                self.video_log(f"   📄 Segmentos: {section.get_segment_count()}")
                self.video_log(f"   📝 Caracteres: {section.get_total_chars():,}")
                
                # Obtener rutas de transcripciones
                transcription_paths = section.get_transcription_paths()
                
                if not transcription_paths:
                    self.video_log(f"⚠️ No hay transcripciones en esta sección")
                    continue
                
                # Construir nombre de mazo con jerarquía
                deck_prefix = ""
                if bisabuelo_str:
                    deck_prefix += f"{bisabuelo_str}::"
                if grandparent_str:
                    deck_prefix += f"{grandparent_str}::"
                deck_prefix += f"{section.title}"
                
                # Procesar sección con Gemini
                result = self.flashcard_generator.process_video_section(
                    section_title=section.title,
                    transcription_paths=transcription_paths,
                    converter=self.converter,
                    anki_manager=self.anki_manager,
                    deck_prefix=deck_prefix,
                    session_path=getattr(self, 'current_video_session', None)
                )
                
                if result.get("success"):
                    self.video_log(f"\n   ✅ RESULTADOS DE LA SECCIÓN:")
                    # Actualizar indicadores visuales y logear detalles
                    import_results = result.get("results", {})
                    for card_type, card_result in import_results.items():
                        if card_result.get("success"):
                            count = card_result.get("count", 0)
                            total_flashcards += count
                            self.video_log(f"      • {card_type}: {count} flashcards importadas")
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
            self.video_log(f"✅ PROCESAMIENTO GLOBAL COMPLETADO")
            self.video_log(f"   • Secciones procesadas: {len(self.video_sections)}")
            self.video_log(f"   • Total flashcards importadas a Anki: {total_flashcards}")
            self.video_log(f"{'='*60}\n")
            
            # Mostrar popup
            self.root.after(0, lambda: messagebox.showinfo(
                "Procesamiento completado",
                f"Secciones procesadas: {len(self.video_sections)}\n"
                f"Total flashcards importadas: {total_flashcards}"
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
            "level_4_analysis": ("4️⃣", "L4")
        }
        
        card_types_icons = [
            (card_type, *type_icons.get(card_type, ("❓", card_type[:6])))
            for card_type, is_active in active_types.items() if is_active
        ]
        
        # Refrescar tanto secciones de video como de imágenes
        for widgets_dict in (self.video_section_widgets, self.section_widgets):
            for section_id, widgets in widgets_dict.items():
                if "status_labels" not in widgets or not widgets["status_labels"]:
                    continue
                    
                first_label_dict = next(iter(widgets["status_labels"].values()))
                if not first_label_dict or "state" not in first_label_dict:
                    continue
                    
                status_frame = first_label_dict["state"].master.master
                
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
    
    def show_recover_video_session_dialog(self):
        """Muestra el diálogo para recuperar una sesión de video."""
        temp_dir = getattr(self.video_processor, "TEMP_DIR", "temp_videos")
        
        sessions = []
        if os.path.exists(temp_dir):
            for d in os.listdir(temp_dir):
                if d.startswith("session_"):
                    meta_path = os.path.join(temp_dir, d, "metadata.json")
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, 'r', encoding='utf-8') as f:
                                meta = json.load(f)
                                meta["session_folder"] = os.path.join(temp_dir, d)
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
                info = (f"Video: {session.get('original_video', 'N/A')}\n"
                        f"Ruta: {session.get('video_path', 'N/A')}\n"
                        f"Duración: {dur_str} | Segmentos: {session.get('total_segments', 0)}")
                info_label.config(text=info)
                
        listbox.bind("<<ListboxSelect>>", on_select)
        on_select(None)
        
    def _recover_video_session(self, session_data: dict):
        """Recupera la sesión de video cargando sus segmentos."""
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
                    
            rel_trans = seg_data.get("transcription_file")
            if rel_trans:
                trans_path = os.path.join(folder, "transcriptions", rel_trans)
                if os.path.exists(trans_path):
                    seg.transcription_path = trans_path
                    # Cargar char count si no está
                    try:
                        with open(trans_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Extraer solo el texto (ignorar comentarios)
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
        self.video_log(f"📁 Sesión de video recuperada con {len(self.current_video_segments)} segmentos.")

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
            if not getattr(self, "flashcard_generator", None):
                self.flashcard_generator = GeminiFlashcardGenerator(log_callback=self.auto_log)
            
            count = self.flashcard_generator.get_pending_count()
            
            # Update all pending buttons that might exist in different tabs
            pending_buttons = []
            if hasattr(self, "pending_btn"):
                pending_buttons.append(self.pending_btn)
            if hasattr(self, "pending_text_btn"):
                pending_buttons.append(self.pending_text_btn)
            if hasattr(self, "pending_video_btn"):
                pending_buttons.append(self.pending_video_btn)
                
            for btn in pending_buttons:
                if count > 0:
                    btn.config(text=f"📋 Importar Pendientes ({count})")
                else:
                    btn.config(text="📋 Importar Pendientes")
        except Exception as e:
            self.auto_log(f"⚠️ Error al actualizar botón de pendientes: {e}")
    
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


def main():
    """Inicia la aplicación."""
    # Intentar usar TkinterDnD para drag & drop si está disponible
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        print("✅ TkinterDnD habilitado - Drag & drop disponible")
    except ImportError:
        root = tk.Tk()
        print("⚠️ TkinterDnD no disponible - Usa botones para añadir imágenes")
        print("   Para habilitar drag & drop, instala: pip install tkinterdnd2")
    
    app = AnkiImportInterface(root)
    root.mainloop()


if __name__ == "__main__":
    main()
