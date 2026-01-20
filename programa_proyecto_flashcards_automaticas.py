
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import importlib
import os
import queue
from typing import List, Dict, Any
import io
import contextlib
import re
import inspect

# Import new UI components
from input_banner import InputBanner
from chat_interface import ChatInterface
from input_method_controller import InputMethodController, InputMode, string_to_input_mode

# Import unified content processing pipeline
from unified_content_processor import ProcessingPipelineIntegration, ProcessingState, ProcessingResult

# Import configuration management
from config_manager import get_config_manager, ConfigurationManager
from settings_dialog import SettingsDialog

# Import Anki sync components
from anki_sync_interface import AnkiSyncInterface

# ---------------- CONFIGURACIÓN (ajusta aquí si cambia la organización de archivos) ----------------
MODULE_ACUMULAR = "acumular_flaschards"        # módulo que contiene 'acumular_total_flashacards'
MODULE_PROCESAR = "automatizar_importacion"   # módulo que contiene 'procesar_importacion_automática'

FUNC_ACUMULAR = "acumular_total_flashacards"
FUNC_PROCESAR = "procesar_importacion_automática"

# Si quieres forzar pasar el modo siempre (True) o solo cuando la función lo soporte (False).
TRY_PASS_MODO_PARAM = False
# --------------------------------------------------------------------------------------------------

def import_function(module_name: str, func_name: str):
    """Importa dinámicamente y devuelve la función. Lanza ImportError/AttributeError si falla."""
    try:
        mod = importlib.import_module(module_name)
    except Exception as e:
        raise ImportError(f"No se pudo importar módulo '{module_name}': {e}")
    try:
        func = getattr(mod, func_name)
    except AttributeError:
        raise AttributeError(f"'{func_name}' no encontrada en módulo '{module_name}'")
    return func

class FlashcardsGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Flashcards automáticas")
        self.geometry("1200x800")
        self.minsize(1000, 600)

        # Configuration management
        self.config_manager = get_config_manager()
        self.config = self.config_manager.get_config()

        # Data storage
        self.files: List[str] = []
        self.file_meta: Dict[str, Dict[str, Any]] = {}
        self.q = queue.Queue()

        # UI Components
        self.input_banner = None
        self.chat_interface = None
        self.input_controller = None
        
        # Dynamic content areas
        self.content_areas = {}
        self.active_content_area = None

        # Unified processing pipeline
        self.processing_integration = ProcessingPipelineIntegration()
        self.current_processing_thread = None

        # Initialize components
        self._setup_input_controller()
        self._create_widgets()
        self._load_backend_functions()
        self._apply_configuration_settings()
        self.after(200, self._process_queue)

    def _create_widgets(self):
        """Create the main widget layout with responsive design."""
        # Main container
        main_container = ttk.Frame(self, padding=8)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Create input banner at the top
        self._create_input_banner(main_container)
        
        # Create main content area with left and right panels
        content_container = ttk.Frame(main_container)
        content_container.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Left panel for dynamic content areas
        self.left_panel = ttk.Frame(content_container)
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        
        # Right panel for controls and logs
        self.right_panel = ttk.Frame(content_container, width=350)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_panel.pack_propagate(False)
        
        # Create dynamic content areas
        self._create_content_areas()
        
        # Create right panel controls
        self._create_right_panel()
        
        # Set initial active content area based on configuration
        default_mode = self.config_manager.get_default_input_method()
        self._switch_content_area(default_mode)
        
        # Set initial input mode in controller
        self.input_controller.switch_input_mode(default_mode)

    def _setup_input_controller(self):
        """Initialize the input method controller and register callbacks."""
        self.input_controller = InputMethodController()
        
        # Register mode change callback
        self.input_controller.register_mode_change_callback(
            "main_gui", self._on_input_mode_changed
        )
        
        # Register validation callback
        self.input_controller.register_validation_callback(
            "main_gui", self._validate_mode_transition
        )
        
        # Register configuration change callback
        self.config_manager.register_change_callback(self._on_configuration_changed)
    
    def _create_input_banner(self, parent):
        """Create the input method selection banner."""
        self.input_banner = InputBanner(parent, self._on_banner_mode_selected)
        self.input_banner.pack(fill=tk.X, pady=(0, 10))
        
        # Register with controller
        self.input_controller.register_ui_component("input_banner", self.input_banner)
    
    def _create_content_areas(self):
        """Create dynamic content areas for different input methods."""
        # PDF Annotations content area (existing functionality)
        self._create_pdf_annotations_area()
        
        # PDF Full Text content area
        self._create_pdf_fulltext_area()
        
        # Direct Text Input content area
        self._create_direct_text_area()
        
        # Anki Sync content area
        self._create_anki_sync_area()
    
    def _create_pdf_annotations_area(self):
        """Create content area for PDF annotations input method."""
        area_frame = ttk.LabelFrame(self.left_panel, text="PDF Files with Annotations", padding=6)
        
        # File drop area
        drop_frame = ttk.Frame(area_frame, height=120, relief=tk.RIDGE)
        drop_frame.pack(fill=tk.X, padx=6, pady=6)
        drop_frame.pack_propagate(False)
        
        label = ttk.Label(drop_frame, text="Drag PDF files here or use 'Browse Files' ↓", anchor="center")
        label.place(relx=0.5, rely=0.4, anchor="center")
        
        btn_browse = ttk.Button(drop_frame, text="Browse Files", command=self._on_browse)
        btn_browse.place(relx=0.5, rely=0.7, anchor="center")
        
        info_lbl = ttk.Label(drop_frame, text="(Accepts: .pdf files with highlights/annotations)", font=("TkDefaultFont", 8))
        info_lbl.place(relx=0.98, rely=0.95, anchor="se")
        
        # File list
        self._create_file_list(area_frame)
        
        # Store references
        self.content_areas[InputMode.PDF_ANNOTATIONS] = area_frame
        self.drop_frame = drop_frame  # Keep for compatibility
    
    def _create_pdf_fulltext_area(self):
        """Create content area for PDF full text input method."""
        area_frame = ttk.LabelFrame(self.left_panel, text="PDF Files - Full Text Extraction", padding=6)
        
        # File drop area
        drop_frame = ttk.Frame(area_frame, height=120, relief=tk.RIDGE)
        drop_frame.pack(fill=tk.X, padx=6, pady=6)
        drop_frame.pack_propagate(False)
        
        label = ttk.Label(drop_frame, text="Drag PDF files here or use 'Browse Files' ↓", anchor="center")
        label.place(relx=0.5, rely=0.4, anchor="center")
        
        btn_browse = ttk.Button(drop_frame, text="Browse Files", command=self._on_browse)
        btn_browse.place(relx=0.5, rely=0.7, anchor="center")
        
        info_lbl = ttk.Label(drop_frame, text="(Extracts all text content from PDF files)", font=("TkDefaultFont", 8))
        info_lbl.place(relx=0.98, rely=0.95, anchor="se")
        
        # File list (shared with annotations mode)
        self._create_file_list(area_frame)
        
        self.content_areas[InputMode.PDF_FULLTEXT] = area_frame
    
    def _create_direct_text_area(self):
        """Create content area for direct text input method."""
        area_frame = ttk.Frame(self.left_panel)
        
        # Create chat interface
        self.chat_interface = ChatInterface(area_frame, self._validate_chat_input)
        self.chat_interface.pack(fill=tk.BOTH, expand=True)
        
        # Register with controller
        self.input_controller.register_ui_component("chat_interface", self.chat_interface)
        
        self.content_areas[InputMode.DIRECT_TEXT] = area_frame
    
    def _create_anki_sync_area(self):
        """Create content area for Anki sync method."""
        area_frame = ttk.Frame(self.left_panel)
        
        # Create Anki sync interface
        self.anki_sync_interface = AnkiSyncInterface(area_frame, self._on_anki_sync_complete)
        self.anki_sync_interface.pack(fill=tk.BOTH, expand=True)
        
        # Register with controller
        self.input_controller.register_ui_component("anki_sync_interface", self.anki_sync_interface)
        
        self.content_areas[InputMode.ANKI_SYNC] = area_frame
    
    def _create_file_list(self, parent):
        """Create the file list treeview (shared between PDF modes)."""
        cols = ("tipo", "nombre", "estado", "n_flashcards", "tiempo_s")
        self.tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("tipo", text="Type")
        self.tree.heading("nombre", text="File Name")
        self.tree.heading("estado", text="Status")
        self.tree.heading("n_flashcards", text="Cards")
        self.tree.heading("tiempo_s", text="Time (s)")
        self.tree.column("tipo", width=60, anchor="center")
        self.tree.column("nombre", width=420)
        self.tree.column("estado", width=120, anchor="center")
        self.tree.column("n_flashcards", width=80, anchor="center")
        self.tree.column("tiempo_s", width=80, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        
        # File management buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Button(btn_frame, text="Remove Selected", command=self._remove_selected).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Clear List", command=self._clear_list).pack(side=tk.LEFT, padx=(6, 0))
        
        # Register with controller
        self.input_controller.register_ui_component("file_list", self.tree)
    
    def _create_right_panel(self):
        """Create the right panel with controls and logs."""
        # Processing options (only for PDF modes)
        self.options_frame = ttk.LabelFrame(self.right_panel, text="Processing Options", padding=6)
        self.options_frame.pack(fill=tk.X, padx=6, pady=(6, 0))
        
        # Initialize annotation mode from configuration
        default_annotation_mode = self.config.pdf_processing.default_annotation_mode
        self.anot_var = tk.StringVar(value=default_annotation_mode)
        ttk.Radiobutton(self.options_frame, text="With annotations", variable=self.anot_var, value="con").pack(anchor="w", pady=2)
        ttk.Radiobutton(self.options_frame, text="Without annotations", variable=self.anot_var, value="sin").pack(anchor="w", pady=2)
        
        # Settings button
        settings_btn = ttk.Button(self.options_frame, text="Settings...", command=self._open_settings_dialog)
        settings_btn.pack(anchor="w", pady=(6, 0))
        
        # Process button
        proc_frame = ttk.Frame(self.right_panel)
        proc_frame.pack(fill=tk.X, padx=6, pady=12)
        self.btn_process = ttk.Button(proc_frame, text="Process Content", command=self._on_start_process)
        self.btn_process.pack(fill=tk.X)
        
        # Register with controller
        self.input_controller.register_ui_component("process_button", self.btn_process)
        self.input_controller.register_ui_component("file_controls", self.options_frame)
        
        # Logs section
        log_frame = ttk.LabelFrame(self.right_panel, text="Logs / Messages", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(8, 6))
        self.log_text = tk.Text(log_frame, height=16, wrap="word", state="disabled")
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def _switch_content_area(self, mode: InputMode):
        """Switch the active content area based on input mode."""
        # Hide current active area
        if self.active_content_area and self.active_content_area in self.content_areas.values():
            self.active_content_area.pack_forget()
        
        # Show new active area
        if mode in self.content_areas:
            self.active_content_area = self.content_areas[mode]
            self.active_content_area.pack(fill=tk.BOTH, expand=True)
            
            # Update right panel visibility based on mode
            self._update_right_panel_for_mode(mode)
    
    def _update_right_panel_for_mode(self, mode: InputMode):
        """Update right panel controls based on active mode."""
        if mode in [InputMode.PDF_ANNOTATIONS, InputMode.PDF_FULLTEXT]:
            # Show processing options for PDF modes
            self.options_frame.pack(fill=tk.X, padx=6, pady=(6, 0))
            
            # Update button text
            if mode == InputMode.PDF_ANNOTATIONS:
                self.btn_process.configure(text="Process PDF Annotations")
            else:
                self.btn_process.configure(text="Process PDF Full Text")
        elif mode == InputMode.ANKI_SYNC:
            # Hide processing options for Anki sync mode
            self.options_frame.pack_forget()
            self.btn_process.configure(text="Sync to Anki")
        else:
            # Hide processing options for direct text mode
            self.options_frame.pack_forget()
            self.btn_process.configure(text="Process Text Input")
    
    def _on_banner_mode_selected(self, mode_string: str):
        """Handle input method selection from banner."""
        try:
            mode = string_to_input_mode(mode_string)
            self.input_controller.switch_input_mode(mode)
        except ValueError as e:
            self._log(f"Invalid input mode selected: {e}")
    
    def _on_input_mode_changed(self, old_mode: InputMode, new_mode: InputMode):
        """Handle input mode change events."""
        self._log(f"Switched input method: {old_mode.value} → {new_mode.value}")
        self._switch_content_area(new_mode)
        
        # Save as last used method if preference is enabled
        if self.config.user_preferences.remember_last_input_method:
            self.config_manager.set_last_used_input_method(new_mode)
    
    def _validate_mode_transition(self, old_mode: InputMode, new_mode: InputMode) -> bool:
        """Validate input mode transitions."""
        # Check if there's unsaved content in chat interface
        if old_mode == InputMode.DIRECT_TEXT and self.chat_interface:
            if self.chat_interface.get_text().strip() and not self.chat_interface.is_placeholder_active:
                result = messagebox.askyesno(
                    "Unsaved Content",
                    "You have unsaved text content. Do you want to switch input methods anyway?"
                )
                if not result:
                    return False
        
        return True
    
    def _validate_chat_input(self, text: str) -> bool:
        """Validate chat interface input."""
        # Basic validation - ensure text is not empty and has reasonable content
        if not text or len(text.strip()) < 10:
            return False
        
        # Check for reasonable content (not just repeated characters)
        unique_chars = len(set(text.lower().replace(' ', '')))
        if unique_chars < 5:  # Too few unique characters
            return False
        
        return True

    def _log(self, message: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{time.strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _on_browse(self):
        paths = filedialog.askopenfilenames(title="Seleccionar archivos", filetypes=[("Documentos","*.pdf *.txt"),("Todos","*.*")])
        if paths:
            self._add_files(list(paths))

    def _add_files(self, paths: List[str]):
        for p in paths:
            p = os.path.abspath(p)
            if p in self.files:
                self._log(f"Archivo ya en lista: {os.path.basename(p)}")
                continue
            if not os.path.exists(p):
                self._log(f"No existe: {p}")
                continue
            ext = os.path.splitext(p)[1].lower()
            tipo = "PDF" if ext==".pdf" else ("TXT" if ext==".txt" else "OTRO")
            self.files.append(p)
            self.file_meta[p] = {"tipo": tipo, "estado":"Pendiente", "n_flashcards":"-", "tiempo_s":"-"}
            self.tree.insert("", "end", iid=p, values=(tipo, os.path.basename(p), "Pendiente","-","-"))
            self._log(f"Agregado: {os.path.basename(p)}")

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        for iid in sel:
            if iid in self.files:
                self.files.remove(iid)
                self.file_meta.pop(iid, None)
            self.tree.delete(iid)
            self._log(f"Removido: {os.path.basename(iid)}")

    def _clear_list(self):
        for p in list(self.files):
            self.tree.delete(p)
        self.files.clear()
        self.file_meta.clear()
        self._log("Lista limpiada")

    def _load_backend_functions(self):
        """Carga las funciones desde los módulos configurados y las asigna a self.f_acum, self.f_proc"""
        try:
            self.f_acum = import_function(MODULE_ACUMULAR, FUNC_ACUMULAR)
            self._log(f"Cargado {FUNC_ACUMULAR} desde {MODULE_ACUMULAR}")
        except Exception as e:
            self.f_acum = None
            self._log(f"Error cargando {FUNC_ACUMULAR}: {e}")

        try:
            self.f_proc = import_function(MODULE_PROCESAR, FUNC_PROCESAR)
            self._log(f"Cargado {FUNC_PROCESAR} desde {MODULE_PROCESAR}")
        except Exception as e:
            self.f_proc = None
            self._log(f"Error cargando {FUNC_PROCESAR}: {e}")

    def _on_start_process(self):
        """Handle process button click using unified content processing pipeline."""
        current_mode = self.input_controller.get_current_mode()
        
        # Handle Anki sync mode separately
        if current_mode == InputMode.ANKI_SYNC:
            # Anki sync is handled by the AnkiSyncInterface itself
            self._log("Anki sync mode - use the interface controls to manage synchronization")
            return
        
        # Prepare source data based on input mode
        if current_mode == InputMode.DIRECT_TEXT:
            # Validate direct text input
            if not self.chat_interface or not self.chat_interface.validate_input():
                messagebox.showwarning("Invalid Input", "Please enter valid text content to process.")
                return
            
            source = self.chat_interface.get_text()
            
            # Check if confirmation is required
            if self.config.user_preferences.confirm_before_processing:
                if not messagebox.askokcancel("Confirm", f"Process {len(source)} characters of text content?"):
                    return
        
        else:
            # Validate PDF files
            if not self.files:
                messagebox.showwarning("No Files", "No files in the list to process.")
                return
            
            source = self.files.copy()  # Use list of files
            mode_text = self._get_mode_description(current_mode)
            
            # Check if confirmation is required
            if self.config.user_preferences.confirm_before_processing:
                if not messagebox.askokcancel("Confirm", f"Process {len(self.files)} file(s) in mode: {mode_text}?"):
                    return
        
        # Validate input using unified processor
        is_valid, error_msg = self.processing_integration.validate_input_for_mode(current_mode, source)
        if not is_valid:
            messagebox.showerror("Invalid Input", f"Cannot process input: {error_msg}")
            return
        
        # Start unified processing
        self._start_unified_processing(current_mode, source)
    
    def _get_mode_description(self, mode: InputMode) -> str:
        """Get human-readable description of processing mode."""
        if mode == InputMode.PDF_ANNOTATIONS:
            return "PDF with Annotations"
        elif mode == InputMode.PDF_FULLTEXT:
            return "PDF Full Text"
        elif mode == InputMode.DIRECT_TEXT:
            return "Direct Text Input"
        else:
            return "Unknown Mode"
    
    def _start_unified_processing(self, input_mode: InputMode, source: Any):
        """
        Start unified content processing in background thread.
        
        Args:
            input_mode: Type of input being processed
            source: Content source (text or file list)
        """
        # Disable UI during processing
        self.btn_process.config(state="disabled")
        self.input_controller.set_processing_state(True)
        if self.chat_interface:
            self.chat_interface.set_processing_state(True)
        
        # Start processing thread
        self.current_processing_thread = threading.Thread(
            target=self._unified_processing_thread,
            args=(input_mode, source),
            daemon=True
        )
        self.current_processing_thread.start()
    
    def _unified_processing_thread(self, input_mode: InputMode, source: Any):
        """
        Background thread for unified content processing.
        
        Args:
            input_mode: Type of input being processed
            source: Content source
        """
        try:
            # Process with progress reporting
            result = self.processing_integration.process_with_progress_reporting(
                input_mode=input_mode,
                source=source,
                progress_callback=self._on_processing_progress,
                options=self._get_processing_options()
            )
            
            # Queue result for main thread
            self.q.put(("unified_processing_complete", result))
            
        except Exception as e:
            # Queue error for main thread
            error_result = ProcessingResult(
                success=False,
                input_mode=input_mode,
                source_info={"source": str(source)},
                flashcard_count=0,
                segment_count=0,
                processing_time=0,
                error=str(e)
            )
            self.q.put(("unified_processing_complete", error_result))
        
        finally:
            # Re-enable UI
            self.q.put(("enable_button", None))
    
    def _on_processing_progress(self, state: ProcessingState):
        """
        Handle processing progress updates from unified processor.
        
        Args:
            state: Current processing state
        """
        # Queue progress update for main thread
        self.q.put(("processing_progress", state))
    
    def _get_processing_options(self) -> Dict[str, Any]:
        """
        Get current processing options from UI.
        
        Returns:
            Dictionary of processing options
        """
        options = {}
        
        # Add annotation mode for PDF processing
        if hasattr(self, 'anot_var'):
            options['annotation_mode'] = self.anot_var.get()
        
        # Add configuration-based options
        config = self.config_manager.get_config()
        options.update({
            'pdf_processing': config.pdf_processing.to_dict(),
            'text_validation': config.text_validation.to_dict(),
            'processing_settings': config.processing.to_dict()
        })
        
        return options
    
    def _apply_configuration_settings(self):
        """Apply configuration settings to the application."""
        config = self.config_manager.get_config()
        
        # Apply user preferences
        prefs = config.user_preferences
        
        # Set default input method (already handled in _create_widgets)
        
        # Apply processing settings to unified processor
        if hasattr(self.processing_integration, 'processor'):
            processor = self.processing_integration.processor
            proc_settings = config.processing
            
            processor.api_delay = proc_settings.api_delay_seconds
            processor.max_retries = proc_settings.max_retries
            processor.timeout = proc_settings.timeout_seconds
            
            # Update logging level if debug is enabled
            if proc_settings.enable_debug_logging:
                import logging
                logging.getLogger().setLevel(logging.DEBUG)
        
        # Apply text validation settings to chat interface
        if self.chat_interface:
            text_val = config.text_validation
            self.chat_interface.update_validation_settings(
                min_chars=text_val.min_text_length,
                max_chars=text_val.max_text_length,
                min_unique_chars=text_val.min_unique_characters,
                require_alphabetic=text_val.require_alphabetic_content,
                max_repetition_ratio=text_val.max_repetition_ratio
            )
    
    def _on_configuration_changed(self, new_config):
        """Handle configuration changes."""
        self.config = new_config
        self._apply_configuration_settings()
        self._log("Configuration updated")
    
    def _open_settings_dialog(self):
        """Open the settings configuration dialog."""
        try:
            dialog = SettingsDialog(self, self.config_manager)
            dialog.wait_window()  # Wait for dialog to close
        except Exception as e:
            self._log(f"Error opening settings dialog: {e}")
            messagebox.showerror("Settings Error", f"Could not open settings dialog:\n{e}")
    
    def _save_current_input_method(self):
        """Save the current input method as last used."""
        current_mode = self.input_controller.get_current_mode()
        self.config_manager.set_last_used_input_method(current_mode)
    
    # Legacy processing methods - kept for backward compatibility but deprecated
    def _process_direct_text(self, text_content: str):
        """Legacy method - use _start_unified_processing instead."""
        self._log("Warning: Using legacy direct text processing method")
        self._start_unified_processing(InputMode.DIRECT_TEXT, text_content)

    # Legacy processing methods - kept for backward compatibility
    def _call_with_optional_modo(self, func, *args):
        """Legacy method for calling functions with optional modo parameter."""
        try:
            return func(*args)
        except TypeError as e1:
            modo_value = self.anot_var.get()
            sig = None
            try:
                sig = inspect.signature(func)
            except Exception:
                sig = None
            params = []
            if sig:
                params = [p.name for p in sig.parameters.values()]
            for name in ("modo", "modo_anotaciones", "mode"):
                if name in params or TRY_PASS_MODO_PARAM:
                    try:
                        return func(*args, **{name: modo_value})
                    except TypeError:
                        continue
            raise e1

    def _process_all_files(self):
        """Legacy method - use _start_unified_processing instead."""
        self._log("Warning: Using legacy file processing method")
        current_mode = self.input_controller.get_current_mode()
        self._start_unified_processing(current_mode, self.files.copy())

    def _update_tree(self, path, estado=None, n_flashcards=None, tiempo_s=None):
        try:
            vals = list(self.tree.item(path, "values"))
            if estado is not None:
                vals[2] = estado
            if n_flashcards is not None:
                vals[3] = n_flashcards
            if tiempo_s is not None:
                vals[4] = tiempo_s
            self.tree.item(path, values=vals)
        except Exception:
            pass

    def _process_queue(self):
        while not self.q.empty():
            msg = self.q.get_nowait()
            if msg[0] == "resumen":
                resumen, total_elapsed = msg[1], msg[2]
                self._show_summary_popup(resumen, total_elapsed)
            elif msg[0] == "text_processed":
                result = msg[1]
                self._handle_text_processing_success(result)
            elif msg[0] == "text_error":
                error_info = msg[1]
                self._handle_text_processing_error(error_info)
            elif msg[0] == "unified_processing_complete":
                result = msg[1]
                self._handle_unified_processing_complete(result)
            elif msg[0] == "processing_progress":
                state = msg[1]
                self._handle_processing_progress(state)
            elif msg[0] == "enable_button":
                self.btn_process.config(state="normal")
                self.input_controller.set_processing_state(False)
                if self.chat_interface:
                    self.chat_interface.set_processing_state(False)
        self.after(200, self._process_queue)
    
    def _handle_unified_processing_complete(self, result: ProcessingResult):
        """
        Handle completion of unified processing.
        
        Args:
            result: ProcessingResult from unified processor
        """
        if result.success:
            self._log(f"Processing completed successfully!")
            self._log(f"Generated {result.flashcard_count} flashcards in {result.processing_time:.1f}s")
            
            # Update file list for PDF modes
            if result.input_mode in [InputMode.PDF_ANNOTATIONS, InputMode.PDF_FULLTEXT]:
                self._update_files_after_processing(result)
            
            # Show success popup
            self._show_unified_success_popup(result)
            
            # Clear chat interface for direct text mode based on configuration
            if result.input_mode == InputMode.DIRECT_TEXT and self.chat_interface:
                if self.config.user_preferences.auto_clear_chat_after_processing:
                    self.chat_interface.clear_text()
                else:
                    if messagebox.askyesno("Clear Text", "Processing complete. Clear text area for new input?"):
                        self.chat_interface.clear_text()
        
        else:
            self._log(f"Processing failed: {result.error}")
            messagebox.showerror("Processing Failed", f"Processing failed:\n\n{result.error}")
        
        # Log any warnings
        if result.warnings:
            for warning in result.warnings:
                self._log(f"Warning: {warning}")
    
    def _handle_processing_progress(self, state: ProcessingState):
        """
        Handle processing progress updates.
        
        Args:
            state: Current processing state
        """
        # Log progress updates
        progress_percent = int(state.progress * 100)
        stage_name = state.stage.value.replace('_', ' ').title()
        
        if state.current_item:
            self._log(f"{stage_name} ({progress_percent}%): {state.current_item}")
        else:
            self._log(f"{stage_name}: {progress_percent}%")
        
        # Log any errors
        if state.error:
            self._log(f"Error in {stage_name}: {state.error}")
    
    def _update_files_after_processing(self, result: ProcessingResult):
        """
        Update file list UI after successful processing.
        
        Args:
            result: ProcessingResult with processing information
        """
        # For multiple files, update each file's status
        if result.source_info.get("type") == "multiple_files":
            file_paths = result.source_info.get("file_paths", [])
            for file_path in file_paths:
                if file_path in self.files:
                    self._update_tree(
                        file_path,
                        estado="Completado",
                        n_flashcards=str(result.flashcard_count // len(file_paths)),  # Approximate
                        tiempo_s=f"{result.processing_time:.1f}"
                    )
        
        # For single file
        elif result.source_info.get("type") == "single_file":
            file_path = result.source_info.get("file_path")
            if file_path and file_path in self.files:
                self._update_tree(
                    file_path,
                    estado="Completado",
                    n_flashcards=str(result.flashcard_count),
                    tiempo_s=f"{result.processing_time:.1f}"
                )
    
    def _show_unified_success_popup(self, result: ProcessingResult):
        """
        Show success popup for unified processing results.
        
        Args:
            result: ProcessingResult with success information
        """
        mode_desc = self._get_mode_description(result.input_mode)
        
        summary_lines = [
            f"Processing Complete - {mode_desc}",
            "",
            f"Flashcards Generated: {result.flashcard_count}",
            f"Text Segments: {result.segment_count}",
            f"Processing Time: {result.processing_time:.1f} seconds"
        ]
        
        if result.deck_name:
            summary_lines.append(f"Anki Deck: {result.deck_name}")
        
        if result.source_info.get("type") == "multiple_files":
            file_count = result.source_info.get("file_count", 0)
            processed_count = result.source_info.get("processed_files", 0)
            summary_lines.append(f"Files Processed: {processed_count}/{file_count}")
        
        if result.warnings:
            summary_lines.extend(["", "Warnings:"])
            for warning in result.warnings[:3]:  # Show first 3 warnings
                summary_lines.append(f"• {warning}")
            if len(result.warnings) > 3:
                summary_lines.append(f"• ... and {len(result.warnings) - 3} more")
        
        summary_text = "\n".join(summary_lines)
        PopupSummary(self, summary_text)
    
    def _handle_text_processing_success(self, result):
        """Handle successful text processing."""
        deck_name = result.get("deck_name", "Unknown")
        n_cards = result.get("n_cards", "Unknown")
        tiempo_s = result.get("tiempo_s", 0)
        stdout = result.get("stdout", "")
        
        self._log(f"Text processing completed in {tiempo_s}s")
        self._log(f"Generated {n_cards} flashcards in deck '{deck_name}'")
        
        if stdout:
            self._log(f"Backend output: {stdout[:200]}...")
        
        # Show success popup
        success_text = f"Text Processing Complete\n\n"
        success_text += f"Deck: {deck_name}\n"
        success_text += f"Flashcards: {n_cards}\n"
        success_text += f"Processing time: {tiempo_s}s"
        
        PopupSummary(self, success_text)
    
    def _handle_text_processing_error(self, error_info):
        """Handle text processing errors."""
        error = error_info.get("error", "Unknown error")
        tiempo_s = error_info.get("tiempo_s", 0)
        
        self._log(f"Text processing failed after {tiempo_s}s: {error}")
        messagebox.showerror("Processing Error", f"Failed to process text content:\n\n{error}")
    
    def _on_anki_sync_complete(self, total_cards: int, errors: list):
        """Handle completion of Anki synchronization."""
        if errors:
            self._log(f"Anki sync completed with {len(errors)} error(s)")
            for error in errors:
                self._log(f"  - {error}")
        else:
            self._log(f"Anki sync completed successfully! {total_cards} cards synced.")

    def _show_summary_popup(self, resumen: List[Dict[str,Any]], total_elapsed_s: float):
        lines = []
        total_cards_known = 0
        for r in resumen:
            nombre = os.path.basename(r["archivo"])
            if r.get("error"):
                lines.append(f"{nombre}: ERROR -> {r['error']} (t={r.get('tiempo_s')} s)")
            else:
                deck = r.get("deck_name") or "—"
                nc = r.get("n_cards")
                nc_str = str(nc) if nc is not None else "—"
                lines.append(f"{nombre}: OK, deck='{deck}', cartas={nc_str}, t={r.get('tiempo_s')} s")
                if isinstance(nc, int):
                    total_cards_known += nc
        lines.append("")
        lines.append(f"Tiempo total acumulado: {total_elapsed_s} s")
        if total_cards_known:
            lines.append(f"Total cartas (solo cuentas conocidas): {total_cards_known}")
        text = "\n".join(lines)
        PopupSummary(self, text)

class PopupSummary(tk.Toplevel):
    def __init__(self, parent, text):
        super().__init__(parent)
        self.title("Resumen de procesamiento")
        self.geometry("640x360")
        self.transient(parent)
        self.grab_set()
        f = ttk.Frame(self, padding=8)
        f.pack(fill=tk.BOTH, expand=True)
        txt = tk.Text(f, wrap="word")
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert("1.0", text)
        txt.config(state="disabled")
        ttk.Button(f, text="Cerrar", command=self.destroy).pack(pady=6)

def main():
    app = FlashcardsGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
