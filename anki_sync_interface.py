"""
Interfaz UI para sincronizar flashcards con Anki.
Permite seleccionar hasta 4 mazos de diferentes tipos de flashcards.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from typing import Callable, Optional, Dict, Any, List
import json
from pathlib import Path

from anki_sync_manager import AnkiSyncManager
from flashcard_parser import FlashcardParser


class AnkiSyncInterface(ttk.Frame):
    """Interfaz para sincronizar flashcards con Anki."""
    
    def __init__(self, parent, on_sync_complete: Optional[Callable] = None):
        """
        Inicializa la interfaz de sincronización.
        
        Args:
            parent: Widget padre
            on_sync_complete: Callback cuando se completa la sincronización
        """
        super().__init__(parent)
        self.on_sync_complete = on_sync_complete
        self.anki_manager = AnkiSyncManager()
        self.sync_thread = None
        self.is_syncing = False
        
        # Almacenamiento de flashcards por tipo
        self.flashcards_by_type = {
            "basic": [],
            "multiple_choice": [],
            "cloze": [],
            "vocabulary": []
        }
        
        self._create_widgets()
        self._check_anki_status()
    
    def _create_widgets(self):
        """Crea los widgets de la interfaz."""
        # Contenedor principal
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        # Sección de estado de Anki
        self._create_anki_status_section(main_frame)
        
        # Sección de mazos
        self._create_decks_section(main_frame)
        
        # Sección de flashcards
        self._create_flashcards_section(main_frame)
        
        # Sección de sincronización
        self._create_sync_section(main_frame)
    
    def _create_anki_status_section(self, parent):
        """Crea la sección de estado de Anki."""
        status_frame = ttk.LabelFrame(parent, text="Anki Status", padding=6)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Status indicator
        status_container = ttk.Frame(status_frame)
        status_container.pack(fill=tk.X)
        
        self.status_indicator = tk.Canvas(status_container, width=12, height=12, bg="white", highlightthickness=0)
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 8))
        
        self.status_label = ttk.Label(status_container, text="Checking Anki status...")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Botones de control
        button_frame = ttk.Frame(status_frame)
        button_frame.pack(fill=tk.X, pady=(8, 0))
        
        self.btn_check_status = ttk.Button(button_frame, text="Check Status", command=self._check_anki_status)
        self.btn_check_status.pack(side=tk.LEFT, padx=(0, 4))
        
        self.btn_start_anki = ttk.Button(button_frame, text="Start Anki", command=self._start_anki)
        self.btn_start_anki.pack(side=tk.LEFT)
    
    def _create_decks_section(self, parent):
        """Crea la sección de configuración de mazos."""
        decks_frame = ttk.LabelFrame(parent, text="Anki Decks (up to 4)", padding=6)
        decks_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Sección de entrada manual (por defecto)
        self._create_manual_input_section(decks_frame)
        
        # Contenedor para los 4 mazos
        self.deck_entries = {}
        self.deck_types = {}
        
        for i in range(4):
            deck_num = i + 1
            self._create_deck_row(decks_frame, deck_num)
    
    def _create_manual_input_section(self, parent):
        """Crea la sección de entrada manual de flashcards."""
        input_frame = ttk.LabelFrame(parent, text="Manual Input (Paste with Ctrl+V)", padding=6)
        input_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Instrucciones
        instructions = ttk.Label(
            input_frame,
            text="Paste flashcards in format: P: question\nR: answer\n\nSupported formats: Basic, Multiple Choice, Cloze, Vocabulary",
            font=("TkDefaultFont", 9),
            foreground="gray"
        )
        instructions.pack(anchor="w", pady=(0, 8))
        
        # Área de texto para entrada manual
        self.manual_input_text = tk.Text(input_frame, height=6, wrap="word")
        self.manual_input_text.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        # Bind Ctrl+V para pegar
        self.manual_input_text.bind("<Control-v>", self._on_paste)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(input_frame, orient="vertical", command=self.manual_input_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.manual_input_text.config(yscrollcommand=scrollbar.set)
        
        # Botones de acción
        button_frame = ttk.Frame(input_frame)
        button_frame.pack(fill=tk.X, pady=(0, 0))
        
        ttk.Button(
            button_frame,
            text="Parse & Auto-Detect",
            command=self._parse_manual_input
        ).pack(side=tk.LEFT, padx=(0, 4))
        
        ttk.Button(
            button_frame,
            text="Clear",
            command=lambda: self.manual_input_text.delete("1.0", tk.END)
        ).pack(side=tk.LEFT)
        
        self.manual_status_label = ttk.Label(button_frame, text="", foreground="gray")
        self.manual_status_label.pack(side=tk.LEFT, padx=(20, 0))
    
    def _on_paste(self, event):
        """Maneja el evento de pegar (Ctrl+V)."""
        # Permitir el comportamiento por defecto de pegar
        return "break"
    
    def _parse_manual_input(self):
        """Parsea la entrada manual y la distribuye entre los mazos."""
        text = self.manual_input_text.get("1.0", tk.END).strip()
        
        if not text:
            messagebox.showwarning("Empty Input", "Please paste flashcards first")
            return
        
        try:
            # Parsear y formatear automáticamente
            formatted_cards, types = FlashcardParser.parse_and_format(text)
            
            if not formatted_cards:
                messagebox.showwarning("Parse Error", "No flashcards found in the text")
                return
            
            # Distribuir entre mazos según tipo
            type_to_deck = {}
            deck_num = 1
            
            for card, card_type in zip(formatted_cards, types):
                if card_type not in type_to_deck:
                    if deck_num <= 4:
                        type_to_deck[card_type] = deck_num
                        deck_num += 1
                    else:
                        messagebox.showwarning(
                            "Too Many Types",
                            "More than 4 different flashcard types detected. "
                            "Please limit to 4 types."
                        )
                        return
            
            # Configurar mazos automáticamente
            for card_type, deck_num in type_to_deck.items():
                # Nombre del mazo
                deck_name = f"{card_type.replace('_', ' ').title()}"
                self.deck_entries[deck_num].delete(0, tk.END)
                self.deck_entries[deck_num].insert(0, deck_name)
                
                # Tipo de flashcard
                self.deck_types[deck_num].set(card_type)
                
                # Guardar flashcards
                cards_of_type = [
                    card for card, ctype in zip(formatted_cards, types)
                    if ctype == card_type
                ]
                self.flashcards_by_type[card_type] = cards_of_type
                
                # Actualizar label de estado
                self.deck_status_labels[deck_num].config(
                    text=f"({len(cards_of_type)} cards auto-detected)",
                    foreground="green"
                )
            
            # Actualizar vista previa
            self._update_preview()
            
            # Mostrar resumen
            self.manual_status_label.config(
                text=f"✓ {len(formatted_cards)} flashcards parsed and distributed",
                foreground="green"
            )
            
            messagebox.showinfo(
                "Success",
                f"Parsed {len(formatted_cards)} flashcards\n"
                f"Distributed across {len(type_to_deck)} decks"
            )
        
        except Exception as e:
            messagebox.showerror("Parse Error", f"Error parsing flashcards:\n{e}")
            self.manual_status_label.config(text=f"✗ Error: {str(e)[:50]}", foreground="red")
    
    def _create_deck_row(self, parent, deck_num: int):
        """Crea una fila para configurar un mazo."""
        row_frame = ttk.Frame(parent)
        row_frame.pack(fill=tk.X, pady=4)
        
        # Número de mazo
        ttk.Label(row_frame, text=f"Deck {deck_num}:", width=8).pack(side=tk.LEFT)
        
        # Nombre del mazo
        deck_entry = ttk.Entry(row_frame, width=25)
        deck_entry.pack(side=tk.LEFT, padx=(0, 8))
        self.deck_entries[deck_num] = deck_entry
        
        # Tipo de flashcard
        type_var = tk.StringVar(value="basic")
        type_combo = ttk.Combobox(
            row_frame,
            textvariable=type_var,
            values=["basic", "multiple_choice", "cloze", "vocabulary"],
            state="readonly",
            width=18
        )
        type_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.deck_types[deck_num] = type_var
        
        # Botón para cargar flashcards
        ttk.Button(
            row_frame,
            text="Load Flashcards",
            command=lambda: self._load_flashcards_for_deck(deck_num)
        ).pack(side=tk.LEFT, padx=(0, 4))
        
        # Label de estado
        status_label = ttk.Label(row_frame, text="(empty)", foreground="gray")
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Guardar referencia al label
        if not hasattr(self, 'deck_status_labels'):
            self.deck_status_labels = {}
        self.deck_status_labels[deck_num] = status_label
    
    def _create_flashcards_section(self, parent):
        """Crea la sección de vista previa de flashcards."""
        preview_frame = ttk.LabelFrame(parent, text="Flashcards Preview", padding=6)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Selector de mazo para vista previa
        selector_frame = ttk.Frame(preview_frame)
        selector_frame.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Label(selector_frame, text="Preview Deck:").pack(side=tk.LEFT, padx=(0, 4))
        
        self.preview_deck_var = tk.StringVar(value="1")
        preview_combo = ttk.Combobox(
            selector_frame,
            textvariable=self.preview_deck_var,
            values=["1", "2", "3", "4"],
            state="readonly",
            width=5
        )
        preview_combo.pack(side=tk.LEFT)
        preview_combo.bind("<<ComboboxSelected>>", lambda e: self._update_preview())
        
        # Área de texto para vista previa
        self.preview_text = tk.Text(preview_frame, height=8, wrap="word", state="disabled")
        self.preview_text.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_text.config(yscrollcommand=scrollbar.set)
    
    def _create_sync_section(self, parent):
        """Crea la sección de sincronización."""
        sync_frame = ttk.LabelFrame(parent, text="Synchronization", padding=6)
        sync_frame.pack(fill=tk.X)
        
        # Botones de sincronización
        button_frame = ttk.Frame(sync_frame)
        button_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.btn_sync = ttk.Button(button_frame, text="Sync to Anki", command=self._start_sync)
        self.btn_sync.pack(side=tk.LEFT, padx=(0, 4))
        
        ttk.Button(button_frame, text="Clear All", command=self._clear_all).pack(side=tk.LEFT)
        
        # Barra de progreso
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            sync_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate"
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 8))
        
        # Label de estado
        self.sync_status_label = ttk.Label(sync_frame, text="Ready to sync", foreground="blue")
        self.sync_status_label.pack(fill=tk.X)
    
    def _check_anki_status(self):
        """Verifica el estado de Anki."""
        def check_status_thread():
            is_running = self.anki_manager._check_anki_status()
            self.after(0, lambda: self._update_anki_status(is_running))
        
        thread = threading.Thread(target=check_status_thread, daemon=True)
        thread.start()
    
    def _update_anki_status(self, is_running: bool):
        """Actualiza la visualización del estado de Anki."""
        if is_running:
            self.status_indicator.delete("all")
            self.status_indicator.create_oval(2, 2, 10, 10, fill="green")
            self.status_label.config(text="Anki is running", foreground="green")
            self.btn_start_anki.config(state="disabled")
        else:
            self.status_indicator.delete("all")
            self.status_indicator.create_oval(2, 2, 10, 10, fill="red")
            self.status_label.config(text="Anki is not running", foreground="red")
            self.btn_start_anki.config(state="normal")
    
    def _start_anki(self):
        """Inicia Anki."""
        self.sync_status_label.config(text="Starting Anki...", foreground="blue")
        
        def start_anki_thread():
            success, msg = self.anki_manager.ensure_anki_running()
            self.after(0, lambda: self._on_anki_start_complete(success, msg))
        
        thread = threading.Thread(target=start_anki_thread, daemon=True)
        thread.start()
    
    def _on_anki_start_complete(self, success: bool, msg: str):
        """Callback cuando se completa el inicio de Anki."""
        if success:
            self.sync_status_label.config(text=msg, foreground="green")
            self._check_anki_status()
        else:
            self.sync_status_label.config(text=f"Error: {msg}", foreground="red")
            messagebox.showerror("Anki Error", msg)
    
    def _load_flashcards_for_deck(self, deck_num: int):
        """Carga flashcards desde un archivo para un mazo."""
        file_path = filedialog.askopenfilename(
            title=f"Load flashcards for Deck {deck_num}",
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.endswith('.json'):
                    data = json.load(f)
                    flashcards = data if isinstance(data, list) else data.get('flashcards', [])
                else:
                    # Asumir formato de texto
                    content = f.read()
                    card_type = self.deck_types[deck_num].get()
                    flashcards = self.anki_manager.parse_flashcards_from_text(content, card_type)
            
            # Guardar flashcards
            card_type = self.deck_types[deck_num].get()
            self.flashcards_by_type[card_type] = flashcards
            
            # Actualizar label de estado
            self.deck_status_labels[deck_num].config(
                text=f"({len(flashcards)} cards loaded)",
                foreground="green"
            )
            
            # Actualizar vista previa
            self._update_preview()
            
            messagebox.showinfo("Success", f"Loaded {len(flashcards)} flashcards for Deck {deck_num}")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load flashcards:\n{e}")
    
    def _update_preview(self):
        """Actualiza la vista previa de flashcards."""
        deck_num = int(self.preview_deck_var.get())
        card_type = self.deck_types[deck_num].get()
        flashcards = self.flashcards_by_type.get(card_type, [])
        
        self.preview_text.config(state="normal")
        self.preview_text.delete("1.0", tk.END)
        
        if not flashcards:
            self.preview_text.insert("1.0", f"No flashcards loaded for Deck {deck_num}")
        else:
            preview_lines = []
            preview_lines.append(f"Deck {deck_num} - Type: {card_type}")
            preview_lines.append(f"Total cards: {len(flashcards)}\n")
            preview_lines.append("=" * 50)
            
            # Mostrar primeros 3 flashcards
            for i, card in enumerate(flashcards[:3], 1):
                preview_lines.append(f"\nCard {i}:")
                if card_type == "basic":
                    preview_lines.append(f"Front: {card.get('front', '')}")
                    preview_lines.append(f"Back: {card.get('back', '')}")
                elif card_type == "multiple_choice":
                    preview_lines.append(f"Question: {card.get('front', '')}")
                    for opt in card.get('options', []):
                        preview_lines.append(f"  {opt}")
                    preview_lines.append(f"Answer: {card.get('back', '')}")
                elif card_type == "cloze":
                    preview_lines.append(f"Text: {card.get('text', '')}")
                    preview_lines.append(f"Extra: {card.get('extra', '')}")
                elif card_type == "vocabulary":
                    preview_lines.append(f"Term: {card.get('term', '')}")
                    preview_lines.append(f"Pronunciation: {card.get('pronunciation', '')}")
                    preview_lines.append(f"Context: {card.get('context', '')}")
            
            if len(flashcards) > 3:
                preview_lines.append(f"\n... and {len(flashcards) - 3} more cards")
            
            self.preview_text.insert("1.0", "\n".join(preview_lines))
        
        self.preview_text.config(state="disabled")
    
    def _start_sync(self):
        """Inicia la sincronización con Anki."""
        if self.is_syncing:
            messagebox.showwarning("Syncing", "Synchronization is already in progress")
            return
        
        # Validar que hay al menos un mazo configurado
        decks_to_sync = []
        for deck_num in range(1, 5):
            deck_name = self.deck_entries[deck_num].get().strip()
            if deck_name:
                card_type = self.deck_types[deck_num].get()
                flashcards = self.flashcards_by_type.get(card_type, [])
                if flashcards:
                    decks_to_sync.append((deck_num, deck_name, card_type, flashcards))
        
        if not decks_to_sync:
            messagebox.showwarning("No Decks", "Please configure and load flashcards for at least one deck")
            return
        
        # Iniciar sincronización en thread
        self.is_syncing = True
        self.btn_sync.config(state="disabled")
        self.sync_status_label.config(text="Syncing...", foreground="blue")
        
        self.sync_thread = threading.Thread(
            target=self._sync_thread,
            args=(decks_to_sync,),
            daemon=True
        )
        self.sync_thread.start()
    
    def _sync_thread(self, decks_to_sync: List[tuple]):
        """Thread para sincronizar flashcards."""
        total_decks = len(decks_to_sync)
        total_cards = 0
        errors = []
        
        for idx, (deck_num, deck_name, card_type, flashcards) in enumerate(decks_to_sync, 1):
            try:
                # Actualizar progreso
                progress = (idx - 1) / total_decks * 100
                self.after(0, lambda p=progress: self.progress_var.set(p))
                
                status_msg = f"Syncing Deck {deck_num}/{total_decks}: {deck_name}..."
                self.after(0, lambda msg=status_msg: self.sync_status_label.config(text=msg, foreground="blue"))
                
                # Sincronizar
                success, msg, count = self.anki_manager.sync_flashcards_to_anki(
                    deck_name,
                    flashcards,
                    card_type
                )
                
                if success:
                    total_cards += count
                else:
                    errors.append(f"Deck {deck_num} ({deck_name}): {msg}")
            
            except Exception as e:
                errors.append(f"Deck {deck_num} ({deck_name}): {str(e)}")
        
        # Actualizar UI con resultados
        self.after(0, lambda: self._on_sync_complete(total_cards, errors))
    
    def _on_sync_complete(self, total_cards: int, errors: List[str]):
        """Callback cuando se completa la sincronización."""
        self.is_syncing = False
        self.btn_sync.config(state="normal")
        self.progress_var.set(100)
        
        if errors:
            error_msg = "\n".join(errors)
            self.sync_status_label.config(
                text=f"Sync completed with {len(errors)} error(s)",
                foreground="orange"
            )
            messagebox.showwarning("Sync Errors", f"Some decks failed to sync:\n\n{error_msg}")
        else:
            self.sync_status_label.config(
                text=f"Successfully synced {total_cards} cards!",
                foreground="green"
            )
            messagebox.showinfo("Success", f"Successfully synced {total_cards} flashcards to Anki!")
        
        # Callback
        if self.on_sync_complete:
            self.on_sync_complete(total_cards, errors)
    
    def _clear_all(self):
        """Limpia todos los datos."""
        if messagebox.askyesno("Clear All", "Clear all decks and flashcards?"):
            for deck_num in range(1, 5):
                self.deck_entries[deck_num].delete(0, tk.END)
                self.deck_status_labels[deck_num].config(text="(empty)", foreground="gray")
            
            self.flashcards_by_type = {
                "basic": [],
                "multiple_choice": [],
                "cloze": [],
                "vocabulary": []
            }
            
            self._update_preview()
            self.progress_var.set(0)
            self.sync_status_label.config(text="Ready to sync", foreground="blue")
