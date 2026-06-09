import tkinter as tk
from tkinter import ttk, messagebox
import threading
import re
import json
import os
import numpy as np
from typing import List, Dict, Any, Callable, Tuple

class EvaluationUI(tk.Toplevel):
    def __init__(self, parent, pending_imports: List[Dict[str, Any]], on_complete: Callable, generator, app=None):
        super().__init__(parent)
        self.title("🎓 Rúbrica Pedagógica e Indicadores QYI (IA)")
        self.geometry("1200x700")
        self.minsize(1000, 550)
        self.grab_set()  # Ventana modal
        
        self.pending_imports = pending_imports
        self.on_complete = on_complete
        self.generator = generator
        self.app = app
        
        # Guardar una copia profunda/segura original en caso de restauración
        self.original_flat_cards = []
        self.flat_flashcards = []
        
        for group in self.pending_imports:
            deck_name = group['deck_name']
            card_type = group['card_type']
            for card in group['flashcards']:
                # Copiar para evitar modificar la referencia directamente antes de confirmar
                c_copy = dict(card)
                c_copy['_group_ref'] = group
                c_copy['_deck_name'] = deck_name
                c_copy['_card_type'] = card_type
                c_copy['_status'] = "Pendiente"  # Pendiente / Evaluada
                c_copy['_calidad'] = 0
                c_copy['_impacto'] = 'N'
                c_copy['_centralidad'] = 0.0
                c_copy['_utilidad'] = 0.0
                c_copy['_explicacion'] = "No evaluada aún."
                
                self.flat_flashcards.append(c_copy)
                self.original_flat_cards.append(dict(c_copy))
        
        self._build_ui()

    def _build_ui(self):
        # Panel principal dividido
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=10)
        
        # --- PANEL IZQUIERDO: Control y Explicaciones ---
        left_panel = ttk.Frame(paned, padding=10)
        paned.add(left_panel, weight=1)
        
        # Sección 1: Explicación de la Rúbrica
        explain_frame = ttk.LabelFrame(left_panel, text="📚 ¿Cómo funciona el filtrado pedagógico?", padding=10)
        explain_frame.pack(fill="x", pady=(0, 10))
        
        explain_text = (
            "Esta herramienta evalúa tus flashcards con Inteligencia Artificial utilizando "
            "tres pilares educativos avanzados:\n\n"
            "1. Calidad Fáctica (Φ_Q): Mide si la tarjeta aísla una única variable conceptual "
            "y respeta el principio de información mínima sin sobrecargar la memoria de trabajo.\n\n"
            "2. Yield Instruccional (Φ_Y): Clasifica si la tarjeta evalúa un punto clave o de alto "
            "impacto para un examen o aplicación real en lugar de trivia superficial.\n\n"
            "3. Cobertura Topológica (Φ_C): Analiza la importancia del concepto usando PageRank Personalizado "
            "sobre un Grafo de Conocimiento (EduKG), priorizando conceptos umbral (Threshold Concepts).\n\n"
            "Fórmula QYI (Quality Yield Index): QYI = 0.3*Φ_Q + 0.4*Φ_Y + 0.3*Φ_C\n\n"
            "📋 Tabla de umbrales por duración de video:\n"
            "• < 15 min (intro): 8–20 conceptos | Normalización: Percentil | QYI: ≥ 0.70\n"
            "• 15–30 min (intermedio): 20–40 conceptos | Normalización: Percentil o Min-Max | QYI: ≥ 0.75\n"
            "• 30–60 min (avanzado): 40–80 conceptos | Normalización: Min-Max | QYI: ≥ 0.80\n"
            "• > 60 min (especializado): 80+ conceptos | Normalización: Min-Max | QYI: ≥ 0.80"
        )
        lbl_explain = tk.Message(explain_frame, text=explain_text, width=320, font=("Segoe UI", 9), justify="left", fg="#333333")
        lbl_explain.pack(fill="both", expand=True)
        
        # Sección: Fuente de Consulta / Transcripción Completa
        self.source_frame = ttk.LabelFrame(left_panel, text="📖 Fuente de Referencia", padding=10)
        self.source_frame.pack(fill="x", pady=(0, 10))
        
        self.lbl_source_status = ttk.Label(self.source_frame, text="Estado: No detectada", font=("Segoe UI", 9, "bold"))
        self.lbl_source_status.pack(anchor="w", pady=2)
        
        self.lbl_source_info = ttk.Label(self.source_frame, text="Se usará fallback de flashcards para el grafo.", font=("Segoe UI", 9, "italic"), foreground="gray")
        self.lbl_source_info.pack(anchor="w", pady=2)
        
        btn_layout = ttk.Frame(self.source_frame)
        btn_layout.pack(fill="x", pady=2)
        
        self.btn_reconstruct = ttk.Button(btn_layout, text="🔗 Unificar Segmentos", command=self._reconstruct_source_from_segments, state="disabled")
        self.btn_reconstruct.pack(side="left", padx=2, fill="x", expand=True)
        
        self.btn_load_txt = ttk.Button(btn_layout, text="📂 Cargar TXT", command=self._load_manual_txt_source)
        self.btn_load_txt.pack(side="left", padx=2, fill="x", expand=True)
        
        btn_layout2 = ttk.Frame(self.source_frame)
        btn_layout2.pack(fill="x", pady=2)
        
        self.btn_transcribe_ia = ttk.Button(btn_layout2, text="🔊 Transcribir Segmentos (IA)", command=self._transcribe_segments_via_ia, state="disabled")
        self.btn_transcribe_ia.pack(fill="x", expand=True)
        
        self._detect_source_context()
        
        # Sección 2: Ejecución
        run_frame = ttk.LabelFrame(left_panel, text="⚙️ Ejecutar Evaluación", padding=10)
        run_frame.pack(fill="x", pady=(0, 10))
        
        self.btn_run = ttk.Button(run_frame, text="🔍 Iniciar Rúbrica con IA", command=self._start_evaluation)
        self.btn_run.pack(fill="x", pady=5)
        
        self.progress = ttk.Progressbar(run_frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=5)
        
        self.lbl_status = ttk.Label(run_frame, text="Estado: Esperando inicio...", font=("Segoe UI", 9, "italic"))
        self.lbl_status.pack(anchor="w", pady=2)
        
        # Sección 3: Métricas Globales (QYI)
        self.metrics_frame = ttk.LabelFrame(left_panel, text="📊 Indicadores QYI del Deck", padding=10)
        self.metrics_frame.pack(fill="both", expand=True)
        
        self.lbl_qyi = ttk.Label(self.metrics_frame, text="QYI Global: --", font=("Segoe UI", 12, "bold"))
        self.lbl_qyi.pack(anchor="w", pady=2)
        self.lbl_phi_q = ttk.Label(self.metrics_frame, text="• Φ_Q (Calidad): --")
        self.lbl_phi_q.pack(anchor="w", pady=2)
        self.lbl_phi_y = ttk.Label(self.metrics_frame, text="• Φ_Y (Alto Impacto): --")
        self.lbl_phi_y.pack(anchor="w", pady=2)
        self.lbl_phi_c = ttk.Label(self.metrics_frame, text="• Φ_C (Cobertura): --")
        self.lbl_phi_c.pack(anchor="w", pady=2)
        self.lbl_total = ttk.Label(self.metrics_frame, text="• Tarjetas evaluadas: --")
        self.lbl_total.pack(anchor="w", pady=2)
        
        # --- PANEL DERECHO: Tabla de Flashcards y Filtros ---
        right_panel = ttk.Frame(paned, padding=10)
        paned.add(right_panel, weight=3)
        
        # Sección 1: Filtros Rápidos
        filter_frame = ttk.LabelFrame(right_panel, text="⚡ Filtros y Descarte Rápido", padding=10)
        filter_frame.pack(fill="x", pady=(0, 10))
        
        # Fila 0: Calidad, Utilidad y Alto Impacto
        ttk.Label(filter_frame, text="Calidad Mínima (0-10):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.spin_quality = ttk.Spinbox(filter_frame, from_=0, to=10, width=5)
        self.spin_quality.set("5")
        self.spin_quality.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        ttk.Label(filter_frame, text="Utilidad Mínima (0.0-1.0):").grid(row=0, column=2, sticky="w", padx=15, pady=2)
        self.spin_utility = ttk.Spinbox(filter_frame, from_=0.0, to=1.0, increment=0.05, width=6)
        self.spin_utility.set("0.50")
        self.spin_utility.grid(row=0, column=3, sticky="w", padx=5, pady=2)
        
        self.check_only_high = tk.BooleanVar(value=False)
        chk_high = ttk.Checkbutton(filter_frame, text="Solo tarjetas de Alto Impacto", variable=self.check_only_high)
        chk_high.grid(row=0, column=4, sticky="w", padx=15, pady=2)
        
        # Fila 1: Concepto, Texto Búsqueda y Botón
        ttk.Label(filter_frame, text="Filtrar Concepto:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.combo_concept_filter = ttk.Combobox(filter_frame, state="readonly", width=18)
        self.combo_concept_filter.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.combo_concept_filter.set("Todos")
        
        ttk.Label(filter_frame, text="Buscar Texto:").grid(row=1, column=2, sticky="w", padx=15, pady=5)
        self.entry_search = ttk.Entry(filter_frame, width=15)
        self.entry_search.grid(row=1, column=3, sticky="w", padx=5, pady=5)
        
        btn_apply_filter = ttk.Button(filter_frame, text="🧹 Descartar que no cumplan", command=self._apply_quick_filters)
        btn_apply_filter.grid(row=1, column=4, sticky="e", padx=10, pady=5)
        
        self._update_concept_filter_dropdown()
        
        # Sección 2: Tabla de Tarjetas
        table_frame = ttk.LabelFrame(right_panel, text="📋 Listado de Tarjetas en Sala de Espera")
        table_frame.pack(fill="both", expand=True)
        
        columns = ("deck", "concept", "front", "calidad", "impacto", "pagerank", "utilidad", "explicacion")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        
        self.tree.heading("deck", text="Mazo")
        self.tree.heading("concept", text="Concepto")
        self.tree.heading("front", text="Pregunta")
        self.tree.heading("calidad", text="Calidad")
        self.tree.heading("impacto", text="Examen")
        self.tree.heading("pagerank", text="PageRank")
        self.tree.heading("utilidad", text="Utilidad")
        self.tree.heading("explicacion", text="Análisis Didáctico de la IA")
        
        self.tree.column("deck", width=120, stretch=False)
        self.tree.column("concept", width=120, stretch=False)
        self.tree.column("front", width=250)
        self.tree.column("calidad", width=60, stretch=False, anchor="center")
        self.tree.column("impacto", width=60, stretch=False, anchor="center")
        self.tree.column("pagerank", width=70, stretch=False, anchor="center")
        self.tree.column("utilidad", width=70, stretch=False, anchor="center")
        self.tree.column("explicacion", width=280)
        
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scroll.pack(side="right", fill="y", pady=5)
        
        # Doble clic para inspeccionar tarjeta completa
        self.tree.bind("<Double-Button-1>", self._on_double_click)
        
        # Botones de Acción de Tabla
        actions_frame = ttk.Frame(right_panel, padding=5)
        actions_frame.pack(fill="x", pady=5)
        
        btn_delete = ttk.Button(actions_frame, text="🗑️ Eliminar Seleccionadas", command=self._delete_selected)
        btn_delete.pack(side="left", padx=5)
        
        btn_restore = ttk.Button(actions_frame, text="🔄 Restaurar Todo", command=self._restore_original)
        btn_restore.pack(side="left", padx=5)
        
        btn_clear_all = ttk.Button(actions_frame, text="🗑️ Vaciar Sala de Espera", command=self._clear_entire_waiting_room)
        btn_clear_all.pack(side="left", padx=5)
        
        self.lbl_card_stats = ttk.Label(actions_frame, text="Total en lista: --")
        self.lbl_card_stats.pack(side="left", padx=15)
        
        self.btn_apply = ttk.Button(actions_frame, text="✅ Guardar y Aplicar a Sala de Espera", 
                                    command=self._apply_and_close, state="disabled")
        self.btn_apply.pack(side="right", padx=5)
        
        self._update_table_view()

    def _update_table_view(self):
        # Limpiar Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for idx, card in enumerate(self.flat_flashcards):
            impact_str = "Sí" if card['_impacto'] == 'S' else "No"
            pr_str = f"{card['_centralidad']:.3f}" if card['_status'] == "Evaluada" else "--"
            ut_str = f"{card['_utilidad']:.2f}" if card['_status'] == "Evaluada" else "--"
            cal_str = f"{card['_calidad']}/10" if card['_status'] == "Evaluada" else "--"
            
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    card['_deck_name'].split("::")[-1],  # Nombre corto de mazo
                    card.get('concept', 'general') if card.get('concept') else 'general',
                    card.get('front', card.get('text', ''))[:120],
                    cal_str,
                    impact_str if card['_status'] == "Evaluada" else "--",
                    pr_str,
                    ut_str,
                    card['_explicacion']
                )
            )
        self.lbl_card_stats.config(text=f"Total en lista: {len(self.flat_flashcards)} tarjetas")

    def _clear_entire_waiting_room(self):
        """Vacía completamente la sala de espera."""
        if not messagebox.askyesno("Vaciar Sala de Espera", "¿Estás seguro de que deseas vaciar completamente la Sala de Espera?\n\nEsto eliminará permanentemente todas las flashcards pendientes de importar."):
            return
            
        # Vaciar colecciones en la ventana actual
        self.flat_flashcards = []
        self.original_flat_cards = []
        self._update_table_view()
        
        # Vaciar la cola en la aplicación principal si está disponible
        if self.app:
            self.app.pending_flashcard_imports = []
            self.app._save_pending_queue()
            self.app._update_pending_button()
            
        messagebox.showinfo("Sala de Espera vaciada", "Se ha vaciado la sala de espera correctamente.")
        self.destroy()

    def _detect_source_context(self):
        """Detecta si hay una fuente completa disponible en la aplicación principal."""
        if not self.app:
            return
            
        # 1. Caso: Hay segmentos de video, audio o secciones de libro con transcripciones que se pueden reconstruir
        mode = getattr(self.app, 'current_mode', '')
        segments = []
        if mode == "automatic_videos":
            segments = getattr(self.app, 'current_video_segments', [])
        elif mode == "automatic_audio":
            segments = getattr(self.app, 'current_audio_segments', [])
        elif mode == "automatic_books":
            segments = getattr(self.app, 'book_sections', [])
            
        segments_with_trans = [s for s in segments if getattr(s, 'transcription_text', '')]
        
        if segments:
            # Si hay segmentos en la sesión, el usuario siempre puede transcribir y unificar de nuevo
            self.btn_transcribe_ia.config(state="normal")
            
            if segments_with_trans:
                self.btn_reconstruct.config(state="normal")
            else:
                self.btn_reconstruct.config(state="disabled")
                
            if hasattr(self.app, 'current_source_context') and self.app.current_source_context:
                char_count = len(self.app.current_source_context)
                self.lbl_source_status.config(text="✅ Fuente unificada detectada", foreground="green")
                self.lbl_source_info.config(text=f"Fuente de {char_count:,} caracteres lista para PageRank.\nSegmentos transcritos: {len(segments_with_trans)}/{len(segments)}.", foreground="black")
            elif segments_with_trans:
                self.lbl_source_status.config(text="⚠️ Fuente no unificada", foreground="orange")
                self.lbl_source_info.config(text=f"Se detectaron {len(segments_with_trans)} de {len(segments)} segmentos con texto.\nPuedes unificarlos para el PageRank.", foreground="black")
            else:
                self.lbl_source_status.config(text="⚠️ Sin transcripciones", foreground="red")
                self.lbl_source_info.config(text="Debes transcribir los segmentos para poder unificarlos.", foreground="black")
            return
            
        # 2. Caso manual o sin segmentos
        if hasattr(self.app, 'current_source_context') and self.app.current_source_context:
            char_count = len(self.app.current_source_context)
            self.lbl_source_status.config(text=f"✅ Fuente unificada detectada", foreground="green")
            self.lbl_source_info.config(text=f"Fuente de {char_count:,} caracteres lista para PageRank.", foreground="black")
            self.btn_reconstruct.config(state="disabled")
            self.btn_transcribe_ia.config(state="disabled")
            return
            
        self.lbl_source_status.config(text="❌ Fuente no detectada", foreground="red")
        self.lbl_source_info.config(text="Se usará fallback de flashcards para el grafo.", foreground="gray")
        self.btn_reconstruct.config(state="disabled")
        self.btn_transcribe_ia.config(state="disabled")

    def _reconstruct_source_from_segments(self):
        """Concatenación local de las transcripciones de segmentos disponibles."""
        if not self.app:
            return
            
        mode = getattr(self.app, 'current_mode', '')
        segments = []
        if mode == "automatic_videos":
            segments = getattr(self.app, 'current_video_segments', [])
        elif mode == "automatic_audio":
            segments = getattr(self.app, 'current_audio_segments', [])
        elif mode == "automatic_books":
            segments = getattr(self.app, 'book_sections', [])
            
        segments_with_trans = sorted([s for s in segments if getattr(s, 'transcription_text', '')], key=lambda x: getattr(x, 'segment_id', getattr(x, 'section_id', 0)))
        
        if not segments_with_trans:
            messagebox.showwarning("Error", "No se encontraron transcripciones de segmentos para unificar.")
            return
            
        # Concatenar
        reconstructed = []
        for s in segments_with_trans:
            sid = getattr(s, 'segment_id', getattr(s, 'section_id', 0))
            text = getattr(s, 'transcription_text', '').strip()
            reconstructed.append(f"--- Segmento/Sección {sid} ---\n{text}")
            
        full_text = "\n\n".join(reconstructed)
        self.app.current_source_context = full_text
        
        # Guardar también la fuente unificada en el directorio de la sesión si es que existe
        session_dir = None
        if mode == "automatic_videos":
            session_dir = getattr(self.app, 'current_video_session', None)
        elif mode == "automatic_audio":
            session_dir = getattr(self.app, 'current_audio_session', None)
        elif mode == "automatic_books":
            session_dir = getattr(self.app, 'current_book_session', None)
            
        if session_dir and os.path.isdir(session_dir):
            try:
                os.makedirs(os.path.join(session_dir, "original_text"), exist_ok=True)
                source_file = os.path.join(session_dir, "original_text", "reconstructed_faithful_source.txt")
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(full_text)
                self.app.video_log(f"💾 Fuente unificada reconstruida y guardada en sesión: {source_file}")
            except Exception as e:
                print(f"⚠️ Error guardando fuente unificada reconstruida: {e}")
                
        char_count = len(full_text)
        self.lbl_source_status.config(text="✅ Fuente reconstruida y unificada", foreground="green")
        self.lbl_source_info.config(text=f"Fuente de {char_count:,} caracteres creada localmente.", foreground="black")
        self.btn_reconstruct.config(state="disabled")
        messagebox.showinfo("Unificación Exitosa", f"Se han unificado {len(segments_with_trans)} segmentos en una sola fuente de consulta de {char_count:,} caracteres.")

    def _load_manual_txt_source(self):
        """Permite cargar un archivo de texto, PDF o Word como fuente de consulta."""
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo fuente (TXT, PDF, Word)",
            filetypes=[
                ("Archivos Soportados", "*.txt;*.pdf;*.docx"),
                ("Archivos de texto", "*.txt"),
                ("Archivos PDF", "*.pdf"),
                ("Archivos Word", "*.docx"),
                ("Todos los archivos", "*.*")
            ]
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".txt":
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                self._set_source_context(content, f"TXT ({os.path.basename(file_path)})")
            except UnicodeDecodeError:
                # Fallback a latin-1 si falla UTF-8
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read().strip()
                    self._set_source_context(content, f"TXT ({os.path.basename(file_path)})")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo leer el archivo de texto:\n{e}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo leer el archivo de texto:\n{e}")
                
        elif ext == ".docx":
            try:
                from docx import Document
                doc = Document(file_path)
                content = "\n".join([p.text for p in doc.paragraphs]).strip()
                if not content:
                    messagebox.showwarning("Archivo Vacío", "El archivo Word no contiene texto.")
                    return
                self._set_source_context(content, f"Word ({os.path.basename(file_path)})")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo leer el archivo Word:\n{e}")
                
        elif ext == ".pdf":
            # Extraer texto rápido primero
            try:
                import fitz
                doc = fitz.open(file_path)
                text_list = []
                for page in doc:
                    text_list.append(page.get_text())
                doc.close()
                raw_text = "\n".join(text_list).strip()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el PDF:\n{e}")
                return

            if len(raw_text) < 100:
                # Parece escaneado
                resp = messagebox.askyesno(
                    "PDF Escaneado",
                    "El PDF no contiene texto seleccionable (parece ser escaneado o imágenes).\n\n"
                    "¿Deseas transcribir el PDF completo usando la IA de Gemini (Vision OCR)?\n"
                    "Esto puede tardar unos minutos."
                )
                if resp:
                    self._extract_pdf_with_ia_thread(file_path, force_ocr=True)
                else:
                    messagebox.showinfo("Cancelado", "No se cargó ninguna fuente de consulta.")
            else:
                # Contiene texto seleccionable
                resp = messagebox.askyesno(
                    "Método de Extracción",
                    "El PDF contiene texto digital seleccionable.\n\n"
                    "¿Deseas procesarlo con Gemini Vision OCR para transcribir e integrar imágenes/diagramas?\n"
                    "Presiona 'Sí' para usar Gemini (Lento).\n"
                    "Presiona 'No' para extraer el texto digital de forma directa y local (Rápido)."
                )
                if resp:
                    self._extract_pdf_with_ia_thread(file_path, force_ocr=True)
                else:
                    self._set_source_context(raw_text, f"PDF rápido ({os.path.basename(file_path)})")
        else:
            # Fallback general para otros archivos
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()
                self._set_source_context(content, f"Archivo ({os.path.basename(file_path)})")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo leer el archivo:\n{e}")

    def _set_source_context(self, content: str, source_label: str):
        if not content:
            messagebox.showwarning("Archivo Vacío", "No se pudo obtener texto del archivo seleccionado.")
            return
            
        if self.app:
            self.app.current_source_context = content
            
        char_count = len(content)
        self.lbl_source_status.config(text="✅ Fuente cargada", foreground="green")
        self.lbl_source_info.config(text=f"Fuente de {char_count:,} caracteres cargada desde {source_label}.", foreground="black")

    def _extract_pdf_with_ia_thread(self, pdf_path: str, force_ocr: bool):
        """Inicia un hilo en segundo plano para transcribir el PDF con Gemini."""
        progress_win = tk.Toplevel(self)
        progress_win.title("📄 Transcribiendo PDF con Gemini")
        progress_win.geometry("450x180")
        progress_win.resizable(False, False)
        progress_win.grab_set()
        
        main_frame = ttk.Frame(progress_win, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        lbl_msg = ttk.Label(main_frame, text="Procesando archivo PDF con Gemini Vision OCR...\nEste proceso puede tomar un momento por página.", wrap=True)
        lbl_msg.pack(fill="x", pady=(0, 10))
        
        pb = ttk.Progressbar(main_frame, mode="indeterminate")
        pb.pack(fill="x", pady=10)
        pb.start(10)
        
        def run_extraction():
            try:
                # Inicializar generador si no existe
                if not self.app.flashcard_generator:
                    active_config = self.app.config_manager.get_active_set()
                    from gemini_flashcard_generator import GeminiFlashcardGenerator
                    self.app.flashcard_generator = GeminiFlashcardGenerator(
                        log_callback=self.app._mode_log,
                        config_set=active_config
                    )
                
                # Ejecutar extracción
                extraction_mode = 2 if force_ocr else 1
                text = self.app.flashcard_generator.extract_text_from_pdf_file(pdf_path, extraction_mode=extraction_mode)
                
                if text:
                    self.after(0, lambda: self._set_source_context(text, f"Gemini OCR ({os.path.basename(pdf_path)})"))
                    self.after(0, lambda: messagebox.showinfo("Éxito", f"Se ha extraído y cargado el contenido del PDF con Gemini correctamente."))
                else:
                    self.after(0, lambda: messagebox.showerror("Error", "No se pudo obtener texto del PDF usando Gemini."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Error durante la extracción de IA:\n{e}"))
            finally:
                self.after(0, progress_win.destroy)
                
        threading.Thread(target=run_extraction, daemon=True).start()

    def _start_evaluation(self):
        if not self.flat_flashcards:
            messagebox.showwarning("Sin tarjetas", "No hay tarjetas para evaluar.")
            return
            
        self.btn_run.config(state="disabled")
        self.progress.start()
        self.lbl_status.config(text="Estado: Evaluando con la IA...")
        
        threading.Thread(target=self._run_evaluation_thread, daemon=True).start()

    def _run_evaluation_thread(self):
        try:
            # 1. Obtener el texto de referencia de la fuente si está disponible
            text_ref = ""
            if self.app and hasattr(self.app, 'current_source_context') and self.app.current_source_context:
                text_ref = self.app.current_source_context
                self.after(0, lambda: self.lbl_status.config(text="Estado: Usando fuente de consulta unificada..."))
            
            # Si no está unificada en memoria, intentar unificarla automáticamente desde segmentos transcritos
            if not text_ref and self.app:
                mode = getattr(self.app, 'current_mode', '')
                segments = []
                if mode == "automatic_videos":
                    segments = getattr(self.app, 'current_video_segments', [])
                elif mode == "automatic_audio":
                    segments = getattr(self.app, 'current_audio_segments', [])
                
                segments_with_trans = sorted([s for s in segments if getattr(s, 'transcription_text', '')], key=lambda x: getattr(x, 'segment_id', 0))
                if segments_with_trans:
                    reconstructed = []
                    for s in segments_with_trans:
                        sid = getattr(s, 'segment_id', 0)
                        text = getattr(s, 'transcription_text', '').strip()
                        reconstructed.append(f"--- Segmento {sid} ---\n{text}")
                    full_text = "\n\n".join(reconstructed)
                    self.app.current_source_context = full_text
                    text_ref = full_text
                    
                    self.after(0, lambda: self.lbl_source_status.config(text="✅ Fuente unificada automáticamente", foreground="green"))
                    self.after(0, lambda: self.lbl_source_info.config(text=f"Fuente de {len(full_text):,} caracteres creada automáticamente.", foreground="black"))
                    self.after(0, lambda: self.btn_reconstruct.config(state="disabled"))
                    self.after(0, lambda: self.lbl_status.config(text="Estado: Usando fuente de consulta unificada..."))

            if not text_ref:
                # Fallback: construir texto de referencia concatenado desde las flashcards
                text_ref = "\n\n".join([
                    f"P: {c.get('front', '')}\nR: {c.get('back', '')}"
                    for c in self.flat_flashcards
                ])
                self.after(0, lambda: self.lbl_status.config(text="Estado: Usando fallback de flashcards..."))
            
            # 2. Watchdog de evaluación en lotes (evita timeouts y límites de tokens)
            evals = self._watchdog_evaluate_with_explanation(text_ref, self.flat_flashcards)
            
            # 3. Recopilar los conceptos específicos extraídos por el Watchdog de cada tarjeta
            concepts = list(set([e.get('concepto', 'general').lower().strip() for e in evals]))
            if not concepts:
                concepts = ["general"]
                
            # 4. Construir grafo y calcular PageRank
            self.after(0, lambda: self.lbl_status.config(text="Estado: Extrayendo relaciones semánticas entre conceptos..."))
            edges = self._extract_concept_relations_via_llm(concepts, text_ref)
            
            self.after(0, lambda: self.lbl_status.config(text="Estado: Calculando PageRank del Grafo..."))
            self.generator.kg_ranker.build_graph(concepts, text_ref, edges=edges)
            pagerank = self.generator.kg_ranker.calculate_pagerank()
            
            # 5. Mapear y computar puntuación de utilidad individual
            alpha, beta, gamma = 0.3, 0.4, 0.3
            
            # Construir normalizador de percentil de PageRank
            def build_pr_percentile_normalizer(pagerank_values: dict):
                values = np.array(list(pagerank_values.values()))
                def normalize_pr(pr_value: float) -> float:
                    if len(values) <= 1:
                        return 1.0
                    percentile = np.mean(values <= pr_value)
                    return float(percentile)
                return normalize_pr
                
            normalize_pr = build_pr_percentile_normalizer(pagerank)
            
            # Calcular umbral dinámico para Y_i (percentil 60)
            def calcular_pr_threshold_dinamico(pagerank_values: dict, percentil_corte: float = 0.60) -> float:
                values = list(pagerank_values.values())
                if not values:
                    return 0.0
                return float(np.percentile(values, percentil_corte * 100))
                
            pr_threshold = calcular_pr_threshold_dinamico(pagerank)
            
            qualities = []
            is_high = []
            card_concepts = []
            
            for idx, card in enumerate(self.flat_flashcards):
                # Encontrar evaluación correspondiente
                eval_data = next((e for e in evals if e.get('original_id') == idx), None)
                calidad = eval_data.get('calidad', 7) if eval_data else 7
                bloom = int(eval_data.get('bloom', 2)) if eval_data else 2
                explicacion = eval_data.get('explicacion', "Completado.") if eval_data else "Evaluado con éxito."
                matched_concept = eval_data.get('concepto', 'general') if eval_data else 'general'
                
                # Asignar concepto obtenido del LLM directamente
                card['concept'] = matched_concept
                
                # Obtener centralidad de PageRank y normalizar con percentil
                pr_val = pagerank.get(matched_concept, 0.0)
                norm_pr = normalize_pr(pr_val)
                
                # Determinar Y_i dinámico
                is_yield = (pr_val >= pr_threshold) and (bloom >= 2)
                impacto_str = 'S' if is_yield else 'N'
                
                # Calcular utilidad individual
                util_score = alpha * (calidad / 10.0) + beta * (1.0 if is_yield else 0.0) + gamma * norm_pr
                
                # Guardar valores evaluados
                card['_status'] = "Evaluada"
                card['_calidad'] = calidad
                card['_impacto'] = impacto_str
                card['_centralidad'] = pr_val
                card['_utilidad'] = util_score
                card['_explicacion'] = explicacion
                
                qualities.append(calidad / 10.0)
                is_high.append(is_yield)
                card_concepts.append(matched_concept)
                
            # 6. Calcular QYI global del deck
            metrics = self.generator.qyi_evaluator.calculate_qyi(qualities, is_high, pagerank, card_concepts)
            
            # 7. Actualizar interfaz
            self.after(0, lambda: self._on_evaluation_success(metrics))
            
        except Exception as e:
            self.after(0, lambda err=str(e): self._on_evaluation_error(err))

    def _watchdog_evaluate_with_explanation(self, text: str, cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        batch_size = 10
        all_evals = []
        total_cards = len(cards)
        
        for batch_idx in range(0, total_cards, batch_size):
            batch = cards[batch_idx:batch_idx + batch_size]
            current_progress = f"Estado: Evaluando tarjetas {batch_idx + 1} a {min(batch_idx + batch_size, total_cards)}..."
            self.after(0, lambda p=current_progress: self.lbl_status.config(text=p))
            
            prompt = (
                "Eres un Evaluador Pedagógico Senior de Flashcards de Anki. Evalúa las siguientes tarjetas respecto a:\n"
                "1. Calidad didáctica (0 a 10).\n"
                "2. Nivel Bloom (1 a 4): 1=Recordar, 2=Entender, 3=Aplicar, 4=Analizar/Evaluar.\n"
                "3. Si son de alto impacto para un examen técnico o práctica real (impacto 'S' para sí, 'N' para no).\n"
                "4. El concepto técnico o tema muy específico y atómico al que está anclada la tarjeta (máximo 3 palabras, ej: 'triada CIA', 'cifrado', 'confidencialidad', 'hashing', 'BCDR'; NO uses 'general', 'varios', 'pregunta', ni nombres de sección genéricos).\n"
                "5. Explicación muy breve (máximo 15 palabras).\n\n"
                f"Texto de referencia: {text[:1200]}\n\n"
                "Flashcards a evaluar:\n"
            )
            for idx, c in enumerate(batch):
                prompt += f"ID:{idx} | P: {c.get('front', '')[:120]} | R: {c.get('back', '')[:120]}\n"
                
            prompt += (
                "\nResponde ÚNICAMENTE con un arreglo JSON en este formato:\n"
                '[{"id": 0, "calidad": 8, "bloom": 2, "impacto": "S", "concepto": "triada CIA", "explicacion": "Explicación corta"}, ...]\n'
                "No agregues texto introductorio o de cierre fuera del JSON."
            )
            
            try:
                res = self.generator.generate_raw_response(prompt, temperature=0.1)
                match = re.search(r'\[.*\]', res, re.DOTALL)
                if match:
                    batch_evals = json.loads(match.group())
                    for e in batch_evals:
                        e['original_id'] = batch_idx + e['id']
                        # Asegurar que concepto no sea vacío o general
                        concept_val = e.get('concepto', 'general').strip().lower()
                        if not concept_val or concept_val in ["general", "varios", "pregunta"]:
                            txt = (batch[e['id']].get('front','') + batch[e['id']].get('back','')).lower()
                            words = re.findall(r'\b\w{4,}\b', txt)
                            concept_val = words[0] if words else "general"
                        e['concepto'] = concept_val
                        e['bloom'] = int(e.get('bloom', 2))
                    all_evals.extend(batch_evals)
                else:
                    raise ValueError("JSON no encontrado o defectuoso")
            except Exception as e:
                # Fallback
                for idx, card in enumerate(batch):
                    txt = (card.get('front','') + card.get('back','')).lower()
                    words = re.findall(r'\b\w{4,}\b', txt)
                    fallback_concept = words[0] if words else "general"
                    all_evals.append({
                        "original_id": batch_idx + idx,
                        "calidad": 7,
                        "bloom": 2,
                        "impacto": "N",
                        "concepto": fallback_concept,
                        "explicacion": "Fallo al procesar rúbrica IA."
                    })
        return all_evals

    def _extract_concept_relations_via_llm(self, concepts: List[str], text_ref: str) -> List[Tuple[str, str]]:
        if len(concepts) <= 1:
            return []
            
        prompt = (
            "Eres un experto en ingeniería de conocimiento y diseño instruccional.\n"
            "Dado este conjunto de conceptos atómicos extraídos de un material de estudio:\n"
            f"Conceptos: {', '.join(concepts)}\n\n"
            f"Texto de referencia (contexto): {text_ref[:3000]}\n\n"
            "Genera todas las relaciones de dependencia o jerarquía entre ellos para construir un Grafo de Conocimiento (EduKG).\n"
            "Es fundamental seguir la siguiente REGLA DE DIRECCIÓN para cada arista:\n"
            "La arista 'from' A 'to' B (A ──► B) significa: A es más específico, es parte de, implementa o ejemplifica a B (que es el concepto más general del que depende).\n"
            "Ejemplos correctos de dirección:\n"
            "- 'iam' ──► 'confidencialidad' (IAM implementa la confidencialidad)\n"
            "- 'bcdr' ──► 'disponibilidad' (BCDR implementa/garantiza la disponibilidad)\n"
            "- 'confidencialidad' ──► 'triada cia' (Confidencialidad es componente de la Tríada CIA)\n\n"
            "Es CRÍTICO que utilices EXACTAMENTE los mismos nombres de conceptos que se te proporcionan en la lista. No uses sinónimos ni alteres su escritura.\n\n"
            "Responde ÚNICAMENTE con un objeto JSON con el siguiente formato:\n"
            "{\n"
            "  \"edges\": [\n"
            "    {\"from\": \"concepto_A\", \"to\": \"concepto_B\", \"type\": \"TIPO_DE_RELACION\"},\n"
            "    ...\n"
            "  ]\n"
            "}\n"
            "No agregues explicaciones adicionales, ni bloques de código markdown. Responde solo con el JSON limpio."
        )
        
        edges = []
        try:
            res = self.generator.generate_raw_response(prompt, temperature=0.1)
            # Buscar JSON
            match = re.search(r'\{.*\}', res, re.DOTALL)
            if match:
                data = json.loads(match.group())
                raw_edges = data.get('edges', [])
                valid_concepts = set(c.lower().strip() for c in concepts)
                for edge in raw_edges:
                    u = edge.get('from', '').strip().lower()
                    v = edge.get('to', '').strip().lower()
                    # Validar que ambos conceptos estén en la lista de nodos
                    if u and v and u in valid_concepts and v in valid_concepts:
                        edges.append((u, v))
            else:
                print("⚠️ No se pudo encontrar el JSON de relaciones en la respuesta.")
        except Exception as e:
            print(f"⚠️ Error al extraer relaciones semánticas vía LLM: {e}")
            
        return edges

    def _on_evaluation_success(self, metrics):
        self.progress.stop()
        self.btn_run.config(state="normal")
        self.btn_apply.config(state="normal")
        self.lbl_status.config(text="Estado: Evaluación completada con éxito.")
        
        # Actualizar métricas generales
        qyi = metrics.get('qyi', 0.0)
        status_qyi = "Excelente" if qyi >= 0.8 else "Aceptable" if qyi >= 0.6 else "Bajo impacto"
        
        self.lbl_qyi.config(text=f"QYI Global: {qyi:.2f} [{status_qyi}]")
        self.lbl_phi_q.config(text=f"• Φ_Q (Calidad Fáctica): {metrics.get('phi_q', 0.0):.2f}")
        self.lbl_phi_y.config(text=f"• Φ_Y (Yield/Impacto): {metrics.get('phi_y', 0.0):.2f}")
        self.lbl_phi_c.config(text=f"• Φ_C (Cobertura Red): {metrics.get('phi_c', 0.0):.2f}")
        self.lbl_total.config(text=f"• Tarjetas evaluadas: {metrics.get('total', 0)}")
        
        self._update_table_view()
        self._update_concept_filter_dropdown()
        messagebox.showinfo("Evaluación Completada", f"Se han evaluado todas las tarjetas.\nÍndice QYI resultante: {qyi:.2f}")

    def _on_evaluation_error(self, err_msg):
        self.progress.stop()
        self.btn_run.config(state="normal")
        self.lbl_status.config(text=f"Error: {err_msg[:40]}...")
        messagebox.showerror("Error de Evaluación", f"No se pudo completar la evaluación:\n{err_msg}")

    def _on_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        
        idx = int(item_id)
        card = self.flat_flashcards[idx]
        
        # Mostrar ventana detallada del contenido
        detail_win = tk.Toplevel(self)
        detail_win.title("🔍 Detalle de la Tarjeta")
        detail_win.geometry("600x450")
        detail_win.grab_set()
        
        ttk.Label(detail_win, text="Pregunta / Anverso:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=15, pady=(15, 2))
        t_front = tk.Text(detail_win, height=6, width=65, wrap="word", font=("Segoe UI", 10))
        t_front.insert("1.0", card.get('front', ''))
        t_front.config(state="disabled")
        t_front.pack(fill="x", padx=15, pady=5)
        
        ttk.Label(detail_win, text="Respuesta / Reverso:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=15, pady=(10, 2))
        t_back = tk.Text(detail_win, height=6, width=65, wrap="word", font=("Segoe UI", 10))
        t_back.insert("1.0", card.get('back', ''))
        t_back.config(state="disabled")
        t_back.pack(fill="x", padx=15, pady=5)
        
        explain_frame = ttk.LabelFrame(detail_win, text="🎓 Rúbrica Pedagógica", padding=10)
        explain_frame.pack(fill="both", expand=True, padx=15, pady=(10, 15))
        
        # Info
        info_str = f"Calidad: {card['_calidad']}/10  |  Alto Impacto: {'Sí' if card['_impacto'] == 'S' else 'No'}  |  Utilidad: {card['_utilidad']:.2f}\n"
        info_str += f"Concepto: {card.get('concept', 'general')}\n\n"
        info_str += f"Justificación IA: {card['_explicacion']}"
        
        lbl_info = tk.Message(explain_frame, text=info_str, width=540, font=("Segoe UI", 9, "italic"), justify="left")
        lbl_info.pack(fill="both", expand=True)

    def _delete_selected(self):
        selections = self.tree.selection()
        if not selections:
            messagebox.showwarning("Selección vacía", "Selecciona una o más tarjetas para eliminar.")
            return
            
        if not messagebox.askyesno("Confirmar eliminación", f"¿Eliminar las {len(selections)} tarjetas seleccionadas?"):
            return
            
        # Eliminar de la lista interna (recorrer al revés para no alterar índices al borrar)
        indices_to_delete = sorted([int(s) for s in selections], reverse=True)
        for idx in indices_to_delete:
            self.flat_flashcards.pop(idx)
            
        self._update_table_view()
        self._recompute_qyi_if_evaluated()
        self._update_concept_filter_dropdown()

    def _restore_original(self):
        if not messagebox.askyesno("Confirmar restauración", "¿Restaurar todas las tarjetas al estado inicial sin filtros?"):
            return
        self.flat_flashcards = [dict(c) for c in self.original_flat_cards]
        self._update_table_view()
        self._recompute_qyi_if_evaluated()
        self._update_concept_filter_dropdown()

    def _apply_quick_filters(self):
        # Validar si han sido evaluadas
        any_evaluated = any(c['_status'] == "Evaluada" for c in self.flat_flashcards)
        if not any_evaluated:
            messagebox.showwarning("Requiere evaluación", "Debes presionar 'Iniciar Rúbrica con IA' antes de aplicar filtros.")
            return
            
        try:
            min_qual = int(self.spin_quality.get())
        except ValueError:
            min_qual = 0
            
        try:
            min_util = float(self.spin_utility.get())
        except ValueError:
            min_util = 0.0
            
        only_high = self.check_only_high.get()
        concept_filter = self.combo_concept_filter.get()
        search_query = self.entry_search.get().strip().lower()
        
        filtered = []
        discarded_count = 0
        
        for c in self.flat_flashcards:
            # 1. Filtro de Calidad
            qual_ok = c['_calidad'] >= min_qual
            
            # 2. Filtro de Utilidad
            util_ok = c['_utilidad'] >= min_util
            
            # 3. Filtro de Alto Impacto
            impact_ok = True
            if only_high and c['_impacto'] != 'S':
                impact_ok = False
                
            # 4. Filtro de Concepto
            concept_ok = True
            if concept_filter != "Todos" and c.get('concept', '').strip() != concept_filter:
                concept_ok = False
                
            # 5. Filtro de Búsqueda por Texto
            search_ok = True
            if search_query:
                front_text = c.get('front', c.get('text', '')).lower()
                back_text = c.get('back', '').lower()
                concept_text = c.get('concept', '').lower()
                if search_query not in front_text and search_query not in back_text and search_query not in concept_text:
                    search_ok = False
            
            if qual_ok and util_ok and impact_ok and concept_ok and search_ok:
                filtered.append(c)
            else:
                discarded_count += 1
                
        if discarded_count == 0:
            messagebox.showinfo("Filtros Aplicados", "Todas las tarjetas cumplen con los filtros seleccionados.")
            return
            
        msg = f"Se descartarán {discarded_count} tarjetas que no cumplen los filtros.\n¿Continuar?"
        if not messagebox.askyesno("Aplicar Filtros Rápidos", msg):
            return
            
        self.flat_flashcards = filtered
        self._update_table_view()
        self._recompute_qyi_if_evaluated()
        self._update_concept_filter_dropdown()

    def _update_concept_filter_dropdown(self):
        concepts = ["Todos"]
        for card in self.flat_flashcards:
            concept = card.get('concept')
            if concept:
                concept_clean = concept.strip()
                if concept_clean and concept_clean not in concepts:
                    concepts.append(concept_clean)
                    
        prev = self.combo_concept_filter.get() if hasattr(self, 'combo_concept_filter') else "Todos"
        self.combo_concept_filter.config(values=concepts)
        if prev in concepts:
            self.combo_concept_filter.set(prev)
        else:
            self.combo_concept_filter.set("Todos")

    def _recompute_qyi_if_evaluated(self):
        # Recalcular QYI global basado en la lista activa de tarjetas
        any_evaluated = any(c['_status'] == "Evaluada" for c in self.flat_flashcards)
        if not any_evaluated or not self.flat_flashcards:
            self.lbl_qyi.config(text="QYI Global: --")
            self.lbl_phi_q.config(text="• Φ_Q (Calidad Fáctica): --")
            self.lbl_phi_y.config(text="• Φ_Y (Yield/Impacto): --")
            self.lbl_phi_c.config(text="• Φ_C (Cobertura Red): --")
            self.lbl_total.config(text="• Tarjetas evaluadas: --")
            return
            
        qualities = [c['_calidad'] / 10.0 for c in self.flat_flashcards]
        is_high = [c['_impacto'] == 'S' for c in self.flat_flashcards]
        card_concepts = [c.get('concept', 'general') for c in self.flat_flashcards]
        
        # Obtener PageRank reconstruido o vacío
        pagerank = {}
        for c in self.flat_flashcards:
            pagerank[c.get('concept', 'general')] = c['_centralidad']
            
        metrics = self.generator.qyi_evaluator.calculate_qyi(qualities, is_high, pagerank, card_concepts)
        
        qyi = metrics.get('qyi', 0.0)
        status_qyi = "Excelente" if qyi >= 0.8 else "Aceptable" if qyi >= 0.6 else "Bajo impacto"
        
        self.lbl_qyi.config(text=f"QYI Global: {qyi:.2f} [{status_qyi}]")
        self.lbl_phi_q.config(text=f"• Φ_Q (Calidad Fáctica): {metrics.get('phi_q', 0.0):.2f}")
        self.lbl_phi_y.config(text=f"• Φ_Y (Yield/Impacto): {metrics.get('phi_y', 0.0):.2f}")
        self.lbl_phi_c.config(text=f"• Φ_C (Cobertura Red): {metrics.get('phi_c', 0.0):.2f}")
        self.lbl_total.config(text=f"• Tarjetas evaluadas: {metrics.get('total', 0)}")

    def _apply_and_close(self):
        # Reconstruir la lista de grupos (on_complete) filtrada
        updated_imports = []
        
        for group in self.pending_imports:
            # Obtener tarjetas aprobadas asociadas a este grupo
            group_cards = [
                {
                    "front": c["front"],
                    "back": c["back"],
                    "concept": c.get("concept", "general")
                }
                for c in self.flat_flashcards
                if c['_group_ref'] is group
            ]
            
            if group_cards:
                new_group = dict(group)
                new_group['flashcards'] = group_cards
                updated_imports.append(new_group)
                
        self.on_complete(updated_imports)
        self.destroy()

    def _transcribe_segments_via_ia(self):
        """Abre la ventana emergente de progreso de transcripción."""
        if not self.app:
            return
            
        mode = getattr(self.app, 'current_mode', '')
        segments = []
        if mode == "automatic_videos":
            segments = getattr(self.app, 'current_video_segments', [])
        elif mode == "automatic_audio":
            segments = getattr(self.app, 'current_audio_segments', [])
        elif mode == "automatic_books":
            segments = getattr(self.app, 'book_sections', [])
            
        if not segments:
            messagebox.showwarning("Sin segmentos", "No hay segmentos o secciones disponibles en la sesión actual.")
            return
            
        # Abrir ventana de progreso
        TranscriptionProgressUI(self, segments, self.app, self._detect_source_context)


class TranscriptionProgressUI(tk.Toplevel):
    def __init__(self, parent, segments, app, on_complete_callback):
        super().__init__(parent)
        self.title("🔊 Transcripción de Segmentos con IA")
        self.geometry("650x550")
        self.minsize(550, 450)
        self.grab_set()  # Ventana modal
        
        self.segments = segments
        self.app = app
        self.on_complete_callback = on_complete_callback
        self.is_cancelled = False
        self.is_running = False
        
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill="both", expand=True)
        
        # Título
        self.title_lbl = ttk.Label(main_frame, text="🔊 Transcripción de Segmentos con Gemini", font=("Segoe UI", 12, "bold"))
        self.title_lbl.pack(anchor="w", pady=(0, 10))
        
        # Configuración del prompt
        prompt_frame = ttk.LabelFrame(main_frame, text="Configuración del Prompt de Transcripción")
        prompt_frame.pack(fill="x", pady=(0, 10))
        
        # Determinar el prompt por defecto según el modo y primer segmento
        mode = getattr(self.app, 'current_mode', '')
        if mode == "automatic_books":
            default_prompt = (
                "Actúa como un excelente estudiante universitario y asistente académico de alto rendimiento.\n"
                "Tu tarea es transcribir y estructurar fielmente todo el contenido de este segmento del libro o documento (PDF/Word).\n\n"
                "INSTRUCCIONES DE EXTRACCIÓN Y TRANSCRIPCIÓN:\n"
                "1. EXTRACCIÓN DETALLADA: Recupera todo el contenido textual del documento, explicaciones, ejemplos y detalles técnicos. No resumas ni omitas información importante.\n"
                "2. ESTRUCTURA Y FORMATO: Organiza la información usando encabezados Markdown, viñetas y tablas de manera clara y profesional.\n"
                "3. ELEMENTOS GRÁFICOS Y FÓRMULAS: Describe diagramas, esquemas o imágenes si aparecen en la página. Transcribe íntegramente las fórmulas matemáticas y ecuaciones.\n"
                "4. CÓDIGO Y ESPECIFICACIONES: Si aparecen fragmentos de código fuente, comandos o especificaciones, recréalos íntegramente en bloques de código markdown.\n\n"
                "REGLAS:\n"
                "- NO simplifiques destructivamente; mantén la fidelidad del texto original.\n"
                "- Escribe en español con excelente ortografía."
            )
            # Ajustar por defecto si la extracción en la ventana principal es Transcripción 100% Fiel
            active_mode = ""
            if hasattr(self.app, 'extraction_mode_book'):
                active_mode = self.app.extraction_mode_book.get()

            self.prompt_templates = {
                "Transcripción y Extracción Detallada (Recomendado)": default_prompt,
                "Apuntes de Estudiante Experto": (
                    "Actúa como un estudiante de alto rendimiento. En lugar de una transcripción literal, redacta "
                    "un resumen académico estructurado del segmento.\n"
                    "Identifica y define los conceptos clave explicados, esquematiza las ideas principales "
                    "y rescata cualquier fórmula, código o paso relevante de manera clara y organizada."
                ),
                "Transcripción 100% Fiel": self.app.flashcard_generator.FAITHFUL_BOOK_PROMPT
            }

            if active_mode == "Transcripción 100% Fiel":
                default_prompt = self.app.flashcard_generator.FAITHFUL_BOOK_PROMPT
        else:
            is_audio = False
            if self.segments:
                path = getattr(self.segments[0], 'audio_path', '') or ''
                is_audio = path.lower().endswith(('.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.opus'))
                
            default_prompt = (
                self.app.video_processor.DEFAULT_SEGMENT_AUDIO_PROMPT 
                if is_audio else 
                self.app.video_processor.DEFAULT_SEGMENT_VIDEO_PROMPT
            )
            self.prompt_templates = {
                "Multimodal Completo (Recomendado)": default_prompt,
                "Literal y Estricto (Sin observaciones)": (
                    "Transcribe fielmente todo el contenido de este segmento. Incluye:\n"
                    "- Todo lo que se dice verbalmente (transcripción literal del audio, sin resumir).\n"
                    "- Todo texto visible en pantalla (diapositivas, código fuente, títulos, subtítulos, anotaciones).\n"
                    "- Descripción muy breve de esquemas o diagramas si aparecen.\n\n"
                    "REGLAS:\n"
                    "- NO resumas ni simplifiques.\n"
                    "- NO agregues observaciones, interpretaciones ni apuntes de estudiante.\n"
                    "- Escribe en español con la mejor ortografía."
                ),
                "Solo Audio / Transcripción Literal de Voz": (
                    "Transcribe de forma literal y completa todo el audio del segmento. "
                    "No agregues descripciones visuales ni apuntes de estudiante, solo reproduce el texto hablado "
                    "exactamente como lo dice el ponente, palabra por palabra, sin omitir ni resumir nada."
                ),
                "Resumen y Conceptos Clave (Apuntes)": (
                    "Actúa como un estudiante de alto rendimiento. En lugar de una transcripción literal, redacta "
                    "un resumen académico estructurado del segmento. "
                    "Identifica y define los conceptos clave explicados, esquematiza las ideas principales "
                    "y rescata cualquier fórmula, código o paso relevante de manera clara y organizada."
                )
            }
        # Selector de Plantillas
        template_frame = ttk.Frame(prompt_frame)
        template_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(template_frame, text="Plantilla:").pack(side="left", padx=(0, 5))
        
        self.combo_template = ttk.Combobox(
            template_frame, 
            values=list(self.prompt_templates.keys()), 
            state="readonly",
            width=40
        )
        self.combo_template.pack(side="left", fill="x", expand=True)
        default_template_name = "Transcripción y Extracción Detallada (Recomendado)" if mode == "automatic_books" else "Multimodal Completo (Recomendado)"
        if mode == "automatic_books" and hasattr(self.app, 'extraction_mode_book') and self.app.extraction_mode_book.get() == "Transcripción 100% Fiel":
            default_template_name = "Transcripción 100% Fiel"
        self.combo_template.set(default_template_name)
        self.combo_template.bind("<<ComboboxSelected>>", self._on_template_selected)
        
        self.prompt_text = tk.Text(prompt_frame, height=5, font=("Segoe UI", 9), wrap="word")
        self.prompt_text.pack(fill="x", padx=5, pady=5)
        self.prompt_text.insert("1.0", default_prompt)
        
        # Checkbox para forzar re-transcripción
        self.check_force = tk.BooleanVar(value=False)
        self.chk_force = ttk.Checkbutton(prompt_frame, text="Reemplazar transcripciones existentes (Forzar re-generación)", variable=self.check_force)
        self.chk_force.pack(anchor="w", padx=5, pady=(0, 5))
        
        # Barra de progreso
        self.progress = ttk.Progressbar(main_frame, mode="determinate")
        self.progress.pack(fill="x", pady=5)
        
        # Log de logs/estado
        log_frame = ttk.LabelFrame(main_frame, text="Detalle del Proceso")
        log_frame.pack(fill="both", expand=True, pady=10)
        
        self.log_text = tk.Text(log_frame, font=("Courier New", 9), wrap="word", bg="#f9f9f9", height=8)
        self.log_text.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y", pady=5)
        
        # Escribir instrucción inicial en el log
        self._write_log("ℹ️ Revisa o edita el prompt de arriba según tus necesidades, luego presiona '▶️ Iniciar Transcripción'.")
        
        # Botones
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(5, 0))
        
        self.btn_cancel = ttk.Button(btn_frame, text="❌ Cerrar", command=self._close_window)
        self.btn_cancel.pack(side="right", padx=(5, 0))
        
        self.btn_start = ttk.Button(btn_frame, text="▶️ Iniciar Transcripción", command=self._start_process)
        self.btn_start.pack(side="right")

    def _on_template_selected(self, event=None):
        selected = self.combo_template.get()
        prompt_content = self.prompt_templates.get(selected, "")
        self.prompt_text.config(state="normal")
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("1.0", prompt_content)
        if self.is_running:
            self.prompt_text.config(state="disabled")

    def _start_process(self):
        self.is_running = True
        self.is_cancelled = False
        self.custom_prompt = self.prompt_text.get("1.0", "end-1c").strip()
        self.btn_start.config(state="disabled")
        self.chk_force.config(state="disabled")
        self.combo_template.config(state="disabled")
        self.prompt_text.config(state="disabled", bg="#f0f0f0") # deshabilitar edición
        self.title_lbl.config(text="🔊 Transcribiendo segmentos con Gemini...")
        self.btn_cancel.config(text="❌ Cancelar", command=self._cancel)
        self.log_text.delete("1.0", "end") # limpiar el log inicial
        self._start_transcription()

    def _start_transcription(self):
        threading.Thread(target=self._run_transcription_thread, daemon=True).start()
        
    def _cancel(self):
        self.is_cancelled = True
        self.log("⚠️ Cancelación solicitada. Esperando a que termine el segmento actual...")
        self.btn_cancel.config(state="disabled")
        
    def _close_window(self):
        if self.is_running and not self.is_cancelled:
            self._cancel()
        else:
            self.destroy()

    def _on_window_close(self):
        self._close_window()

    def log(self, msg):
        self.after(0, lambda: self._write_log(msg))
        
    def _write_log(self, msg):
        self.log_text.insert("end", f"{msg}\n")
        self.log_text.see("end")

    def _run_transcription_thread(self):
        try:
            total = len(self.segments)
            self.log(f"📋 Iniciando transcripción de {total} segmentos...")
            
            # Obtener carpeta de guardado de chunks
            session_dir = None
            mode = getattr(self.app, 'current_mode', '')
            if mode == "automatic_videos":
                session_dir = getattr(self.app, 'current_video_session', None)
            elif mode == "automatic_audio":
                session_dir = getattr(self.app, 'current_audio_session', None)
            elif mode == "automatic_books":
                session_dir = getattr(self.app, 'current_book_session', None)
                
            if not session_dir and mode == "automatic_books" and self.segments:
                first_seg = self.segments[0]
                if getattr(first_seg, 'pdf_segment_path', None):
                    session_dir = os.path.dirname(first_seg.pdf_segment_path)
                    self.app.current_book_session = session_dir
                    
            if not session_dir:
                self.log("❌ Error: No se pudo identificar la carpeta de la sesión actual.")
                return
                
            chunks_dir = os.path.join(session_dir, "chunks")
            os.makedirs(chunks_dir, exist_ok=True)
            
            transcribed_count = 0
            
            for idx, segment in enumerate(self.segments, 1):
                if self.is_cancelled:
                    self.log("🛑 Transcripción cancelada por el usuario.")
                    break
                    
                self.after(0, lambda i=idx: self.progress.config(value=(i-1)/total * 100))
                
                sid = getattr(segment, 'segment_id', getattr(segment, 'section_id', 0))
                self.log(f"\n⚡ [{idx}/{total}] Procesando Segmento/Sección {sid}...")
                
                # Verificar si ya tiene transcripción en memoria o en disco
                chunk_file = os.path.join(chunks_dir, f"segment_{sid:03d}.txt")
                force_overwrite = self.check_force.get()
                if not force_overwrite:
                    if os.path.exists(chunk_file) and not getattr(segment, 'transcription_text', ''):
                        try:
                            with open(chunk_file, 'r', encoding='utf-8') as f:
                                text = f.read().strip()
                                if text:
                                    segment.transcription_text = text
                                    segment.char_count = len(text)
                                    segment.transcription_path = chunk_file
                                    self.log(f"   ✓ Transcripción recuperada desde disco ({len(text)} chars)")
                                    transcribed_count += 1
                                    continue
                        except Exception:
                            pass
                    
                    if getattr(segment, 'transcription_text', ''):
                        self.log(f"   ✓ Ya transcrito en memoria ({len(segment.transcription_text)} chars)")
                        transcribed_count += 1
                        continue
                
                # --- NUEVA RAMA PARA MODO LIBROS ---
                if mode == "automatic_books":
                    self.log(f"   ⬆ Extrayendo/estructurando texto para la sección {sid}...")
                    try:
                        text = ""
                        # Caso A: Fragmento PDF
                        if hasattr(segment, 'pdf_segment_path') and segment.pdf_segment_path and os.path.exists(segment.pdf_segment_path):
                            # Obtener el modo de extracción
                            selected_mode = "Apuntes de Estudiante Experto"
                            if hasattr(self.app, 'extraction_mode_book'):
                                selected_mode = self.app.extraction_mode_book.get()
                            extraction_mode = 2 if selected_mode != "Extracción Cruda (Fiel al documento)" else 1
                            
                            text = self.app.flashcard_generator.extract_text_from_pdf_file(
                                segment.pdf_segment_path, 
                                extraction_mode=extraction_mode
                            )
                            # Usar prompt personalizado si existe
                            custom_prompt = getattr(self, 'custom_prompt', None)
                            if custom_prompt and custom_prompt.strip():
                                self.log(f"   ✨ Aplicando prompt personalizado de extracción...")
                                prompt = f"{custom_prompt}\n\nCONTENIDO A PROCESAR:\n{text}"
                                text = self.app.flashcard_generator.generate_raw_response(prompt)
                            elif selected_mode == "Transcripción 100% Fiel":
                                self.log(f"   ✨ Realizando transcripción 100% fiel...")
                                text = self.app.flashcard_generator.transcribe_content_faithful(text)
                                
                        # Caso B: Imágenes
                        elif getattr(segment, 'images', []):
                            image_paths = [img["path"] for img in segment.images]
                            text = self.app.flashcard_generator.extract_text_from_images(image_paths)
                            
                        # Caso C: Texto
                        elif hasattr(segment, 'text') and segment.text:
                            text = segment.text
                            
                        if text:
                            text = text.strip()
                            segment.transcription_text = text
                            segment.char_count = len(text)
                            segment.transcription_path = chunk_file
                            
                            # Guardar incrementalmente en disco
                            with open(chunk_file, 'w', encoding='utf-8') as f:
                                f.write(text)
                                
                            self.log(f"   ✅ Éxito: {len(text):,} caracteres extraídos/transcritos.")
                            transcribed_count += 1
                        else:
                            self.log(f"   ❌ Error: No se pudo extraer texto para esta sección.")
                    except Exception as ex:
                        self.log(f"   ❌ Error al extraer/transcribir: {ex}")
                    continue
                
                # Transcribir con Gemini a través del video_processor
                if not segment.audio_path or not os.path.exists(segment.audio_path):
                    # Intentar buscar el archivo en la subcarpeta video_chunks/audio_chunks
                    rel_audio = f"segment_{segment.segment_id:03d}.mp4"
                    audio_path = os.path.join(session_dir, "video_chunks", rel_audio)
                    if os.path.exists(audio_path):
                        segment.audio_path = audio_path
                    else:
                        rel_audio_wav = f"segment_{segment.segment_id:03d}.wav"
                        audio_path_wav = os.path.join(session_dir, "audio_chunks", rel_audio_wav)
                        if os.path.exists(audio_path_wav):
                            segment.audio_path = audio_path_wav
                
                if not segment.audio_path or not os.path.exists(segment.audio_path):
                    self.log(f"   ❌ Error: No se encontró archivo multimedia en {segment.audio_path or 'chunks/'}")
                    continue
                
                self.log(f"   ⬆ Subiendo segmento a Gemini para análisis de audio...")
                
                try:
                    text = self.app.video_processor.transcribe_video_segment(
                        segment,
                        custom_prompt=getattr(self, 'custom_prompt', None)
                    )
                    if text:
                        text = text.strip()
                        segment.transcription_text = text
                        segment.char_count = len(text)
                        segment.transcription_path = chunk_file
                        
                        # Guardar incrementalmente en disco
                        with open(chunk_file, 'w', encoding='utf-8') as f:
                            f.write(text)
                            
                        self.log(f"   ✅ Éxito: {len(text):,} caracteres transcritos.")
                        transcribed_count += 1
                    else:
                        self.log(f"   ❌ Error: Gemini retornó transcripción vacía.")
                except Exception as ex:
                    self.log(f"   ❌ Error en transcripción: {ex}")
            
            self.after(0, lambda: self.progress.config(value=100))
            if not self.is_cancelled:
                self.log(f"\n🎉 PROCESO FINALIZADO. Se transcribieron {transcribed_count} de {total} segmentos.")
                messagebox.showinfo("Proceso Terminado", f"Se han transcrito {transcribed_count} segmentos correctamente con la IA.")
            
            self.after(0, self.on_complete_callback)
            
        except Exception as e:
            self.log(f"❌ Error inesperado en el hilo de transcripción: {e}")
