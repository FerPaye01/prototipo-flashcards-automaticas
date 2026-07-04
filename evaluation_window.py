import tkinter as tk
from tkinter import ttk, messagebox
import threading
import re
import json
import os
import numpy as np
from typing import List, Dict, Any, Callable, Tuple
from qyi_evaluator import EduKGRanker

class EvaluationUI(tk.Toplevel):
    def __init__(self, parent, pending_imports: List[Dict[str, Any]], on_complete: Callable, generator, app=None):
        super().__init__(parent)
        self.title("🎓 Rúbrica Pedagógica e Indicadores QYI (IA)")
        self.geometry("1250x750")
        self.minsize(1000, 550)
        self.grab_set()  # Ventana modal
        
        self.pending_imports = pending_imports
        self.on_complete = on_complete
        self.generator = generator
        self.app = app
        
        # Guardar una copia profunda/segura original en caso de restauración
        self.original_flat_cards = []
        self.flat_flashcards = []
        self.discard_history = []
        
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
                c_copy['_bloom'] = 2
                
                self.flat_flashcards.append(c_copy)
                self.original_flat_cards.append(dict(c_copy))
        
        self._build_ui()

    def _build_ui(self):
        # Crear Notebook para las pestañas
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="🎓 Evaluación QYI")

        self.lab_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.lab_tab, text="🔬 Laboratorio QYI")

        # Panel principal dividido en la pestaña de Evaluación
        paned = ttk.PanedWindow(self.main_tab, orient="horizontal")
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
        
        run_frame = ttk.LabelFrame(left_panel, text="⚙️ Ejecutar Evaluación", padding=10)
        run_frame.pack(fill="x", pady=(0, 10))
        
        # Tamaño del Lote de Flashcards para IA
        batch_row = ttk.Frame(run_frame)
        batch_row.pack(fill="x", pady=2)
        ttk.Label(batch_row, text="Tamaño de Lote IA:").pack(side="left", padx=5)
        self.spin_batch_size = ttk.Spinbox(batch_row, from_=1, to=50, width=5)
        self.spin_batch_size.set("10")
        self.spin_batch_size.pack(side="left", padx=5)
        
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
        
        # Fila 1: Concepto, Texto Búsqueda, Umbral PageRank
        ttk.Label(filter_frame, text="Filtrar Concepto:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.combo_concept_filter = ttk.Combobox(filter_frame, state="readonly", width=18)
        self.combo_concept_filter.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.combo_concept_filter.set("Todos")
        
        ttk.Label(filter_frame, text="Buscar Texto:").grid(row=1, column=2, sticky="w", padx=15, pady=5)
        self.entry_search = ttk.Entry(filter_frame, width=15)
        self.entry_search.grid(row=1, column=3, sticky="w", padx=5, pady=5)
        
        ttk.Label(filter_frame, text="Umbral PageRank (Percentil):").grid(row=1, column=4, sticky="w", padx=15, pady=5)
        self.spin_pr_threshold = ttk.Spinbox(filter_frame, from_=0.0, to=1.0, increment=0.05, width=6)
        self.spin_pr_threshold.set("0.60")
        self.spin_pr_threshold.grid(row=1, column=5, sticky="w", padx=5, pady=5)
        
        # Fila 2: Botones de Descarte y Guardado
        btn_filter_frame = ttk.Frame(filter_frame)
        btn_filter_frame.grid(row=2, column=0, columnspan=6, sticky="ew", pady=(8, 2))
        
        btn_prelim = ttk.Button(btn_filter_frame, text="🧹 Aplicar Descarte Preliminar", command=self._apply_preliminary_discard)
        btn_prelim.pack(side="left", padx=5)
        
        btn_visible = ttk.Button(btn_filter_frame, text="👁️ Descartar solo lo visible", command=self._apply_visible_discard)
        btn_visible.pack(side="left", padx=5)
        
        btn_save_normal = ttk.Button(btn_filter_frame, text="💾 Guardar Normal", command=self._apply_and_close)
        btn_save_normal.pack(side="left", padx=5)
        
        self.btn_undo = ttk.Button(btn_filter_frame, text="↩️ Deshacer último paso", command=self._undo_last_discard, state="disabled")
        self.btn_undo.pack(side="left", padx=5)
        
        self._update_concept_filter_dropdown()
        
        # Binds para filtrado visual en tiempo real
        self.combo_concept_filter.bind("<<ComboboxSelected>>", lambda e: self._update_table_view())
        self.entry_search.bind("<KeyRelease>", lambda e: self._update_table_view())
        
        # Sección 2: Tabla de Tarjetas
        table_frame = ttk.LabelFrame(right_panel, text="📋 Listado de Tarjetas en Sala de Espera")
        table_frame.pack(fill="both", expand=True)
        
        columns = ("deck", "concept", "front", "calidad", "impacto", "pagerank", "utilidad", "explicacion")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        
        self.tree.heading("deck", text="Mazo", command=lambda: self._sort_treeview_column("deck", False))
        self.tree.heading("concept", text="Concepto", command=lambda: self._sort_treeview_column("concept", False))
        self.tree.heading("front", text="Pregunta", command=lambda: self._sort_treeview_column("front", False))
        self.tree.heading("calidad", text="Calidad", command=lambda: self._sort_treeview_column("calidad", False))
        self.tree.heading("impacto", text="Examen", command=lambda: self._sort_treeview_column("impacto", False))
        self.tree.heading("pagerank", text="PageRank", command=lambda: self._sort_treeview_column("pagerank", False))
        self.tree.heading("utilidad", text="Utilidad", command=lambda: self._sort_treeview_column("utilidad", False))
        self.tree.heading("explicacion", text="Análisis Didáctico de la IA", command=lambda: self._sort_treeview_column("explicacion", False))
        
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
                                    command=self._apply_and_close)
        self.btn_apply.pack(side="right", padx=5)
        
        self._update_table_view()
        
        # --- AGREGAR DASHBOARD EN METRICS_FRAME (Sección 5) ---
        ttk.Separator(self.metrics_frame, orient="horizontal").pack(fill="x", pady=10)
        
        db_title = ttk.Label(self.metrics_frame, text="📊 Dashboard Rápido", font=("Segoe UI", 10, "bold"))
        db_title.pack(anchor="w", pady=(0, 5))
        
        self.db_grid_frame = tk.Frame(self.metrics_frame)
        self.db_grid_frame.pack(fill="x", expand=True)
        
        self.db_grid_frame.columnconfigure(0, weight=1)
        self.db_grid_frame.columnconfigure(1, weight=1)
        self.db_grid_frame.columnconfigure(2, weight=1)
        
        # Tarjetas resumen
        f_total, self.lbl_db_total = self._create_dashboard_card(self.db_grid_frame, "Total Flashcards", "#E8F0FE", "#1A73E8")
        f_total.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")
        
        f_aprob, self.lbl_db_aprob = self._create_dashboard_card(self.db_grid_frame, "Aprobadas", "#ECFDF5", "#059669")
        f_aprob.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")
        
        f_rech, self.lbl_db_rech = self._create_dashboard_card(self.db_grid_frame, "Rechazadas", "#FFE4E6", "#E11D48")
        f_rech.grid(row=0, column=2, padx=2, pady=2, sticky="nsew")
        
        f_b1, self.lbl_db_b1 = self._create_dashboard_card(self.db_grid_frame, "Bloom I", "#F3E8FF", "#7C3AED")
        f_b1.grid(row=1, column=0, padx=2, pady=2, sticky="nsew")
        
        f_b2, self.lbl_db_b2 = self._create_dashboard_card(self.db_grid_frame, "Bloom II", "#E6FFFA", "#0D9488")
        f_b2.grid(row=1, column=1, padx=2, pady=2, sticky="nsew")
        
        f_b3, self.lbl_db_b3 = self._create_dashboard_card(self.db_grid_frame, "Bloom III+", "#FEF3C7", "#D97706")
        f_b3.grid(row=1, column=2, padx=2, pady=2, sticky="nsew")
        
        # --- INICIALIZAR PESTAÑA LABORATORIO ---
        self._build_lab_tab()

    def _update_table_view(self):
        # Limpiar Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Filtros visuales en tiempo real (no destructivos)
        concept_filter = self.combo_concept_filter.get() if hasattr(self, 'combo_concept_filter') else "Todos"
        search_query = self.entry_search.get().strip().lower() if hasattr(self, 'entry_search') else ""
        
        for idx, card in enumerate(self.flat_flashcards):
            card_concept = card.get('concept', 'general') if card.get('concept') else 'general'
            
            # Filtro de concepto
            if concept_filter != "Todos" and card_concept != concept_filter:
                continue
                
            # Filtro de búsqueda por texto
            if search_query:
                front_text = card.get('front', card.get('text', '')).lower()
                back_text = card.get('back', '').lower()
                concept_text = card_concept.lower()
                if search_query not in front_text and search_query not in back_text and search_query not in concept_text:
                    continue
                    
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
                    card_concept,
                    card.get('front', card.get('text', ''))[:120],
                    cal_str,
                    impact_str if card['_status'] == "Evaluada" else "--",
                    pr_str,
                    ut_str,
                    card['_explicacion']
                )
            )
        self.lbl_card_stats.config(text=f"Total en lista: {len(self.flat_flashcards)} tarjetas")
        self._update_dashboard_metrics()

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
            
        mode = getattr(self.app, 'current_mode', '')
        segments = []
        if mode == "automatic_videos":
            segments = getattr(self.app, 'current_video_segments', [])
        elif mode == "automatic_audio":
            segments = getattr(self.app, 'current_audio_segments', [])
        elif mode == "automatic_books":
            segments = getattr(self.app, 'book_sections', [])
        elif mode == "automatic_text":
            segments = getattr(self.app, 'text_sections', [])
            
        def get_segment_text(s):
            t = getattr(s, 'transcription_text', '')
            if not t:
                t = getattr(s, 'text', '')
            if not t and hasattr(s, 'get_text'):
                try:
                    t = s.get_text()
                except Exception:
                    pass
            return t or ""

        segments_with_trans = [s for s in segments if get_segment_text(s).strip()]
        
        if segments:
            # En modo texto, no tiene sentido transcribir con IA ya que el texto ya fue proveído
            if mode == "automatic_text":
                self.btn_transcribe_ia.config(state="disabled")
            else:
                self.btn_transcribe_ia.config(state="normal")
            
            if segments_with_trans:
                self.btn_reconstruct.config(state="normal")
            else:
                self.btn_reconstruct.config(state="disabled")
                
            if hasattr(self.app, 'current_source_context') and self.app.current_source_context:
                char_count = len(self.app.current_source_context)
                self.lbl_source_status.config(text="✅ Fuente unificada detectada", foreground="green")
                self.lbl_source_info.config(text=f"Fuente de {char_count:,} caracteres lista para PageRank.\nSegmentos/Secciones listos: {len(segments_with_trans)}/{len(segments)}.", foreground="black")
            elif segments_with_trans:
                self.lbl_source_status.config(text="⚠️ Fuente no unificada", foreground="orange")
                self.lbl_source_info.config(text=f"Se detectaron {len(segments_with_trans)} de {len(segments)} segmentos con texto.\nPuedes unificarlos para el PageRank.", foreground="black")
            else:
                self.lbl_source_status.config(text="⚠️ Sin texto en segmentos", foreground="red")
                if mode == "automatic_text":
                    self.lbl_source_info.config(text="Las secciones no contienen texto.", foreground="black")
                else:
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
        elif mode == "automatic_text":
            segments = getattr(self.app, 'text_sections', [])
            
        def get_segment_text(s):
            t = getattr(s, 'transcription_text', '')
            if not t:
                t = getattr(s, 'text', '')
            if not t and hasattr(s, 'get_text'):
                try:
                    t = s.get_text()
                except Exception:
                    pass
            return t or ""

        segments_with_trans = sorted(
            [s for s in segments if get_segment_text(s).strip()],
            key=lambda x: getattr(x, 'segment_id', getattr(x, 'section_id', 0))
        )
        
        if not segments_with_trans:
            messagebox.showwarning("Error", "No se encontraron transcripciones o textos de segmentos para unificar.")
            return
            
        # Concatenar
        reconstructed = []
        for s in segments_with_trans:
            sid = getattr(s, 'segment_id', getattr(s, 'section_id', 0))
            text = get_segment_text(s).strip()
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
        elif mode == "automatic_text":
            session_dir = getattr(self.app, 'current_text_session', None)
            
        if session_dir and os.path.isdir(session_dir):
            try:
                os.makedirs(os.path.join(session_dir, "original_text"), exist_ok=True)
                source_file = os.path.join(session_dir, "original_text", "reconstructed_faithful_source.txt")
                with open(source_file, 'w', encoding='utf-8') as f:
                    f.write(full_text)
                if hasattr(self.app, 'text_log') and mode == "automatic_text":
                    self.app.text_log(f"💾 Fuente unificada reconstruida y guardada en sesión: {source_file}")
                elif hasattr(self.app, 'video_log'):
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
                elif mode == "automatic_books":
                    segments = getattr(self.app, 'book_sections', [])
                elif mode == "automatic_text":
                    segments = getattr(self.app, 'text_sections', [])
                
                def get_segment_text(s):
                    t = getattr(s, 'transcription_text', '')
                    if not t:
                        t = getattr(s, 'text', '')
                    if not t and hasattr(s, 'get_text'):
                        try:
                            t = s.get_text()
                        except Exception:
                            pass
                    return t or ""

                segments_with_trans = sorted(
                    [s for s in segments if get_segment_text(s).strip()],
                    key=lambda x: getattr(x, 'segment_id', getattr(x, 'section_id', 0))
                )
                if segments_with_trans:
                    reconstructed = []
                    for s in segments_with_trans:
                        sid = getattr(s, 'segment_id', getattr(s, 'section_id', 0))
                        text = get_segment_text(s).strip()
                        reconstructed.append(f"--- Segmento/Sección {sid} ---\n{text}")
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
            
            # Calcular umbral dinámico para Y_i
            def calcular_pr_threshold_dinamico(pagerank_values: dict, percentil_corte: float) -> float:
                values = list(pagerank_values.values())
                if not values:
                    return 0.0
                return float(np.percentile(values, percentil_corte * 100))
                
            try:
                corte_val = float(self.spin_pr_threshold.get())
            except ValueError:
                corte_val = 0.60
            pr_threshold = calcular_pr_threshold_dinamico(pagerank, corte_val)
            
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
                card['_bloom'] = bloom
                
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
        try:
            batch_size = int(self.spin_batch_size.get())
        except Exception:
            batch_size = 10
        batch_size = max(1, min(100, batch_size)) # Guard constraints
        
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
        detail_win.transient(self)
        
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

        detail_win.wait_visibility()
        detail_win.grab_set()

    def _push_history(self):
        # Guardamos una copia del estado actual
        self.discard_history.append([dict(c) for c in self.flat_flashcards])
        if len(self.discard_history) > 20:
            self.discard_history.pop(0)
        if hasattr(self, 'btn_undo'):
            self.btn_undo.config(state="normal")

    def _undo_last_discard(self):
        if not self.discard_history:
            if hasattr(self, 'btn_undo'):
                self.btn_undo.config(state="disabled")
            messagebox.showinfo("Deshacer", "No hay acciones de descarte para deshacer.")
            return
        
        self.flat_flashcards = self.discard_history.pop()
        self._update_table_view()
        self._recompute_qyi_if_evaluated()
        self._update_concept_filter_dropdown()
        
        if not self.discard_history:
            if hasattr(self, 'btn_undo'):
                self.btn_undo.config(state="disabled")

    def _delete_selected(self):
        selections = self.tree.selection()
        if not selections:
            messagebox.showwarning("Selección vacía", "Selecciona una o más tarjetas para eliminar.")
            return
            
        if not messagebox.askyesno("Confirmar eliminación", f"¿Eliminar las {len(selections)} tarjetas seleccionadas?"):
            return
            
        self._push_history()
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
        self._push_history()
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
            
        self._push_history()
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
            self._update_dashboard_metrics()
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
        self._update_dashboard_metrics()

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

    def _create_dashboard_card(self, parent, title, bg_color, fg_color):
        card = tk.Frame(parent, bg=bg_color, highlightbackground="#DDDDDD", highlightthickness=1, bd=0)
        
        lbl_title = tk.Label(card, text=title, font=("Segoe UI", 8, "bold"), bg=bg_color, fg="#555555", anchor="w")
        lbl_title.pack(fill="x", padx=6, pady=(4, 1))
        
        lbl_val = tk.Label(card, text="0", font=("Segoe UI", 14, "bold"), bg=bg_color, fg=fg_color, anchor="w")
        lbl_val.pack(fill="x", padx=6, pady=(0, 4))
        
        return card, lbl_val

    def _update_dashboard_metrics(self):
        if not hasattr(self, 'lbl_db_total'):
            return
            
        total_count = len(self.original_flat_cards)
        aprob_count = len(self.flat_flashcards)
        rech_count = total_count - aprob_count
        
        b1_count = sum(1 for c in self.flat_flashcards if c.get('_bloom', 2) == 1)
        b2_count = sum(1 for c in self.flat_flashcards if c.get('_bloom', 2) == 2)
        b3_count = sum(1 for c in self.flat_flashcards if c.get('_bloom', 2) >= 3)
        
        self.lbl_db_total.config(text=str(total_count))
        self.lbl_db_aprob.config(text=str(aprob_count))
        self.lbl_db_rech.config(text=str(rech_count))
        self.lbl_db_b1.config(text=str(b1_count))
        self.lbl_db_b2.config(text=str(b2_count))
        self.lbl_db_b3.config(text=str(b3_count))

    def _apply_preliminary_discard(self):
        any_evaluated = any(c['_status'] == "Evaluada" for c in self.flat_flashcards)
        if not any_evaluated:
            messagebox.showwarning("Requiere evaluación", "Debes presionar 'Iniciar Rúbrica con IA' antes de aplicar filtros pedagógicos.")
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
        
        filtered = []
        discarded_count = 0
        
        for c in self.flat_flashcards:
            qual_ok = c['_calidad'] >= min_qual
            util_ok = c['_utilidad'] >= min_util
            impact_ok = True
            if only_high and c['_impacto'] != 'S':
                impact_ok = False
                
            if qual_ok and util_ok and impact_ok:
                filtered.append(c)
            else:
                discarded_count += 1
                
        if discarded_count == 0:
            messagebox.showinfo("Filtros Aplicados", "Todas las tarjetas cumplen con los filtros seleccionados.")
            return
            
        msg = f"Se descartarán {discarded_count} tarjetas en todo el deck que no cumplen los filtros.\n¿Continuar?"
        if not messagebox.askyesno("Aplicar Descarte Preliminar", msg):
            return
            
        self._push_history()
        self.flat_flashcards = filtered
        self._update_table_view()
        self._recompute_qyi_if_evaluated()
        self._update_concept_filter_dropdown()

    def _apply_visible_discard(self):
        any_evaluated = any(c['_status'] == "Evaluada" for c in self.flat_flashcards)
        if not any_evaluated:
            messagebox.showwarning("Requiere evaluación", "Debes presionar 'Iniciar Rúbrica con IA' antes de aplicar filtros pedagógicos.")
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
            card_concept = c.get('concept', 'general') if c.get('concept') else 'general'
            
            is_visible = True
            if concept_filter != "Todos" and card_concept != concept_filter:
                is_visible = False
            if search_query:
                front_text = c.get('front', c.get('text', '')).lower()
                back_text = c.get('back', '').lower()
                concept_text = card_concept.lower()
                if search_query not in front_text and search_query not in back_text and search_query not in concept_text:
                    is_visible = False
                    
            if is_visible:
                qual_ok = c['_calidad'] >= min_qual
                util_ok = c['_utilidad'] >= min_util
                impact_ok = True
                if only_high and c['_impacto'] != 'S':
                    impact_ok = False
                    
                if qual_ok and util_ok and impact_ok:
                    filtered.append(c)
                else:
                    discarded_count += 1
            else:
                filtered.append(c)
                
        if discarded_count == 0:
            messagebox.showinfo("Filtros Aplicados", "Todas las tarjetas visibles cumplen con los filtros seleccionados.")
            return
            
        msg = f"Se descartarán {discarded_count} tarjetas visibles del concepto seleccionado.\n¿Continuar?"
        if not messagebox.askyesno("Aplicar Descarte a Visibles", msg):
            return
            
        self._push_history()
        self.flat_flashcards = filtered
        self._update_table_view()
        self._recompute_qyi_if_evaluated()
        self._update_concept_filter_dropdown()

    def _sort_treeview_column(self, col, reverse):
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        
        try:
            def parse_val(val):
                val_clean = val.replace('/10', '').replace('%', '').strip()
                if val_clean == '--' or not val_clean:
                    return -1.0
                return float(val_clean)
            l.sort(key=lambda t: parse_val(t[0]), reverse=reverse)
        except ValueError:
            l.sort(key=lambda t: t[0].lower(), reverse=reverse)
            
        for index, (val, k) in enumerate(l):
            self.tree.move(k, '', index)
            
        self.tree.heading(col, command=lambda _col=col: self._sort_treeview_column(_col, not reverse))

    def _build_lab_tab(self):
        # Configurar panel superior para el caso de prueba (Sección 7)
        top_frame = ttk.Frame(self.lab_tab, padding=10)
        top_frame.pack(fill="x")
        
        lbl_title = ttk.Label(top_frame, text="🔬 Laboratorio de Exploración y Pruebas QYI", font=("Segoe UI", 12, "bold"))
        lbl_title.pack(side="left", padx=5)
        
        # Sección 7: Casos de prueba
        case_frame = ttk.Frame(top_frame)
        case_frame.pack(side="right", padx=10)
        
        ttk.Label(case_frame, text="Caso de prueba:").pack(side="left", padx=5)
        self.combo_cases = ttk.Combobox(case_frame, values=[
            "Seleccionar un caso...",
            "Detección de ruido",
            "Bloom I vs II vs III",
            "Concepto central vs periférico"
        ], state="readonly", width=25)
        self.combo_cases.set("Seleccionar un caso...")
        self.combo_cases.pack(side="left", padx=5)
        self.combo_cases.bind("<<ComboboxSelected>>", self._load_lab_case)
        
        # Main split using PanedWindow (Vertical: Top is Inputs, Bottom is Settings & Results)
        v_paned = ttk.PanedWindow(self.lab_tab, orient="vertical")
        v_paned.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # --- PANE SUPERIOR: INPUTS (Sección 1) ---
        inputs_paned = ttk.PanedWindow(v_paned, orient="horizontal")
        v_paned.add(inputs_paned, weight=2)
        
        # Panel Izquierdo: Transcripción
        left_input = ttk.LabelFrame(inputs_paned, text="📝 Transcripción de Referencia", padding=10)
        inputs_paned.add(left_input, weight=1)
        
        self.lab_text = tk.Text(left_input, wrap="word", height=8, font=("Courier New", 9))
        self.lab_text.pack(side="left", fill="both", expand=True)
        
        scroll_txt = ttk.Scrollbar(left_input, orient="vertical", command=self.lab_text.yview)
        scroll_txt.pack(side="right", fill="y")
        self.lab_text.configure(yscrollcommand=scroll_txt.set)
        
        # Panel Derecho: Flashcards de prueba (Tabla editable)
        right_input = ttk.LabelFrame(inputs_paned, text="📋 Flashcards de Prueba (Tabla Editable)", padding=10)
        inputs_paned.add(right_input, weight=1)
        
        columns = ("front", "back", "bloom", "comment")
        self.lab_tree = ttk.Treeview(right_input, columns=columns, show="headings", selectmode="browse")
        self.lab_tree.heading("front", text="Pregunta")
        self.lab_tree.heading("back", text="Respuesta")
        self.lab_tree.heading("bloom", text="Bloom Esperado")
        self.lab_tree.heading("comment", text="Comentario")
        
        self.lab_tree.column("front", width=120)
        self.lab_tree.column("back", width=120)
        self.lab_tree.column("bloom", width=80, stretch=False, anchor="center")
        self.lab_tree.column("comment", width=120)
        
        self.lab_tree.pack(fill="both", expand=True)
        
        # Botones de la tabla (Agregar, Editar, Eliminar)
        btn_table_frame = ttk.Frame(right_input)
        btn_table_frame.pack(fill="x", pady=(5, 0))
        
        btn_add = ttk.Button(btn_table_frame, text="➕ Agregar flashcard", command=self._lab_add_card)
        btn_add.pack(side="left", padx=2)
        
        btn_edit = ttk.Button(btn_table_frame, text="✏️ Editar", command=self._lab_edit_card)
        btn_edit.pack(side="left", padx=2)
        
        btn_del = ttk.Button(btn_table_frame, text="🗑️ Eliminar", command=self._lab_delete_card)
        btn_del.pack(side="left", padx=2)
        
        # --- PANE INFERIOR: CONTROLES Y RESULTADOS (Secciones 2, 3, 4, 6) ---
        bottom_frame = ttk.Frame(v_paned, padding=5)
        v_paned.add(bottom_frame, weight=3)
        
        # Split bottom frame horizontally: Left is Config, Right is Results & Ranking
        bottom_paned = ttk.PanedWindow(bottom_frame, orient="horizontal")
        bottom_paned.pack(fill="both", expand=True)
        
        # Sección 2: Configuración (Panel izquierdo)
        config_frame = ttk.LabelFrame(bottom_paned, text="⚙️ Configuración y Ejecución", padding=10)
        bottom_paned.add(config_frame, weight=1)
        
        # Método de normalización
        norm_row = ttk.Frame(config_frame)
        norm_row.pack(fill="x", pady=5)
        ttk.Label(norm_row, text="Normalización:").pack(side="left", padx=5)
        
        self.combo_norm = ttk.Combobox(norm_row, values=["Min-Max", "Percentil", "Z-Score", "Pesos"], state="readonly", width=12)
        self.combo_norm.set("Percentil")
        self.combo_norm.pack(side="left", padx=5)
        self.combo_norm.bind("<<ComboboxSelected>>", lambda e: self._refresh_lab_results_ui())
        
        # Checkbox para usar IA
        self.check_use_ia = tk.BooleanVar(value=True)
        self.chk_ia = ttk.Checkbutton(norm_row, text="Usar IA (Watchdog)", variable=self.check_use_ia)
        self.chk_ia.pack(side="left", padx=10)
        
        # Preset de Pesos (Sección 5)
        preset_row = ttk.Frame(config_frame)
        preset_row.pack(fill="x", pady=5)
        ttk.Label(preset_row, text="Preset de Pesos:").pack(side="left", padx=5)
        
        self.combo_presets = ttk.Combobox(preset_row, values=[
            "Personalizado",
            "Examen alta exigencia (default)",
            "Máxima precisión fáctica",
            "Exploración de tema nuevo",
            "Filtrado agresivo para examen"
        ], state="readonly", width=25)
        self.combo_presets.set("Examen alta exigencia (default)")
        self.combo_presets.pack(side="left", padx=5)
        self.combo_presets.bind("<<ComboboxSelected>>", self._apply_lab_preset)
        
        # Sliders ΦQ, ΦY, ΦC
        slider_frame = ttk.Frame(config_frame)
        slider_frame.pack(fill="both", expand=True, pady=10)
        
        # ΦQ
        row_q = ttk.Frame(slider_frame)
        row_q.pack(fill="x", pady=4)
        ttk.Label(row_q, text="ΦQ (Calidad):", width=16, anchor="w").pack(side="left")
        self.slider_phi_q = ttk.Scale(row_q, from_=0.0, to=1.0, value=0.30, orient="horizontal", command=self._on_slider_change)
        self.slider_phi_q.pack(side="left", fill="x", expand=True, padx=5)
        self.lbl_phi_q_val = ttk.Label(row_q, text="0.30", width=4)
        self.lbl_phi_q_val.pack(side="right", padx=5)
        
        # ΦY
        row_y = ttk.Frame(slider_frame)
        row_y.pack(fill="x", pady=4)
        ttk.Label(row_y, text="ΦY (Yield):", width=16, anchor="w").pack(side="left")
        self.slider_phi_y = ttk.Scale(row_y, from_=0.0, to=1.0, value=0.40, orient="horizontal", command=self._on_slider_change)
        self.slider_phi_y.pack(side="left", fill="x", expand=True, padx=5)
        self.lbl_phi_y_val = ttk.Label(row_y, text="0.40", width=4)
        self.lbl_phi_y_val.pack(side="right", padx=5)
        
        # ΦC
        row_c = ttk.Frame(slider_frame)
        row_c.pack(fill="x", pady=4)
        ttk.Label(row_c, text="ΦC (Cobertura):", width=16, anchor="w").pack(side="left")
        self.slider_phi_c = ttk.Scale(row_c, from_=0.0, to=1.0, value=0.30, orient="horizontal", command=self._on_slider_change)
        self.slider_phi_c.pack(side="left", fill="x", expand=True, padx=5)
        self.lbl_phi_c_val = ttk.Label(row_c, text="0.30", width=4)
        self.lbl_phi_c_val.pack(side="right", padx=5)
        
        # Umbral PageRank
        row_pr = ttk.Frame(slider_frame)
        row_pr.pack(fill="x", pady=4)
        ttk.Label(row_pr, text="Umbral PageRank:", width=16, anchor="w").pack(side="left")
        self.slider_pr_thresh = ttk.Scale(row_pr, from_=0.0, to=1.0, value=0.60, orient="horizontal", command=self._on_slider_change)
        self.slider_pr_thresh.pack(side="left", fill="x", expand=True, padx=5)
        self.lbl_pr_thresh_val = ttk.Label(row_pr, text="0.60", width=4)
        self.lbl_pr_thresh_val.pack(side="right", padx=5)
        
        # Botones de simulación
        btn_action_frame = ttk.Frame(config_frame)
        btn_action_frame.pack(fill="x", pady=(10, 0))
        
        self.btn_simulate = ttk.Button(btn_action_frame, text="▶️ Ejecutar Simulación", command=self._run_lab_simulation)
        self.btn_simulate.pack(fill="x", pady=2)
        
        self.btn_compare_norm = ttk.Button(btn_action_frame, text="🔄 Comparar normalizaciones", command=self._compare_lab_normalizations)
        self.btn_compare_norm.pack(fill="x", pady=2)
        
        self.lbl_lab_status = ttk.Label(btn_action_frame, text="Estado: Esperando simulación...", font=("Segoe UI", 9, "italic"))
        self.lbl_lab_status.pack(fill="x", pady=5)
        
        # Resultados & Ranking (Panel derecho)
        results_container = ttk.Frame(bottom_paned)
        bottom_paned.add(results_container, weight=2)
        
        # Sección 3: Tabla de Resultados
        results_frame = ttk.LabelFrame(results_container, text="📊 Resultados de la Simulación", padding=10)
        results_frame.pack(fill="both", expand=True, side="left", padx=2)
        
        res_cols = ("front", "q", "y", "c", "score")
        self.lab_res_tree = ttk.Treeview(results_frame, columns=res_cols, show="headings", selectmode="browse")
        self.lab_res_tree.heading("front", text="Flashcard")
        self.lab_res_tree.heading("q", text="Q")
        self.lab_res_tree.heading("y", text="Y")
        self.lab_res_tree.heading("c", text="C")
        self.lab_res_tree.heading("score", text="Score Final")
        
        self.lab_res_tree.column("front", width=180)
        self.lab_res_tree.column("q", width=50, anchor="center")
        self.lab_res_tree.column("y", width=50, anchor="center")
        self.lab_res_tree.column("c", width=50, anchor="center")
        self.lab_res_tree.column("score", width=80, anchor="center")
        
        self.lab_res_tree.pack(fill="both", expand=True)
        
        # Sección 4: Ranking visual
        ranking_frame = ttk.LabelFrame(results_container, text="🏆 Ranking Visual", padding=10)
        ranking_frame.pack(fill="both", expand=True, side="right", padx=2)
        
        # Mejores flashcards
        ttk.Label(ranking_frame, text="⭐ Mejores Flashcards (Top):", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.lab_txt_best = tk.Text(ranking_frame, height=5, wrap="word", font=("Segoe UI", 9), bg="#F0FFF4")
        self.lab_txt_best.pack(fill="x", pady=(0, 10))
        self.lab_txt_best.config(state="disabled")
        
        # Peores flashcards
        ttk.Label(ranking_frame, text="⚠️ Peores Flashcards (Bottom):", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.lab_txt_worst = tk.Text(ranking_frame, height=5, wrap="word", font=("Segoe UI", 9), bg="#FFF5F5")
        self.lab_txt_worst.pack(fill="x")
        self.lab_txt_worst.config(state="disabled")
        
        # Cargar lista vacía de tarjetas
        self.lab_cards = []
        self._update_lab_table()

    def _on_slider_change(self, val=None):
        q_val = self.slider_phi_q.get()
        y_val = self.slider_phi_y.get()
        c_val = self.slider_phi_c.get()
        pr_val = self.slider_pr_thresh.get()
        
        self.lbl_phi_q_val.config(text=f"{q_val:.2f}")
        self.lbl_phi_y_val.config(text=f"{y_val:.2f}")
        self.lbl_phi_c_val.config(text=f"{c_val:.2f}")
        self.lbl_pr_thresh_val.config(text=f"{pr_val:.2f}")
        
        if hasattr(self, 'combo_presets') and self.combo_presets.get() != "Personalizado":
            preset_name = self.combo_presets.get()
            matches = False
            if preset_name == "Examen alta exigencia (default)" and np.isclose(q_val, 0.3) and np.isclose(y_val, 0.4) and np.isclose(c_val, 0.3):
                matches = True
            elif preset_name == "Máxima precisión fáctica" and np.isclose(q_val, 0.5) and np.isclose(y_val, 0.3) and np.isclose(c_val, 0.2):
                matches = True
            elif preset_name == "Exploración de tema nuevo" and np.isclose(q_val, 0.2) and np.isclose(y_val, 0.3) and np.isclose(c_val, 0.5):
                matches = True
            elif preset_name == "Filtrado agresivo para examen" and np.isclose(q_val, 0.3) and np.isclose(y_val, 0.6) and np.isclose(c_val, 0.1):
                matches = True
                
            if not matches:
                self.combo_presets.set("Personalizado")
                
        self._refresh_lab_results_ui()

    def _apply_lab_preset(self, event=None):
        preset_name = self.combo_presets.get()
        if preset_name == "Examen alta exigencia (default)":
            self.slider_phi_q.set(0.30)
            self.slider_phi_y.set(0.40)
            self.slider_phi_c.set(0.30)
        elif preset_name == "Máxima precisión fáctica":
            self.slider_phi_q.set(0.50)
            self.slider_phi_y.set(0.30)
            self.slider_phi_c.set(0.20)
        elif preset_name == "Exploración de tema nuevo":
            self.slider_phi_q.set(0.20)
            self.slider_phi_y.set(0.30)
            self.slider_phi_c.set(0.50)
        elif preset_name == "Filtrado agresivo para examen":
            self.slider_phi_q.set(0.30)
            self.slider_phi_y.set(0.60)
            self.slider_phi_c.set(0.10)
        
        self._on_slider_change()

    def _lab_add_card(self):
        self._show_card_editor_dialog(None)

    def _lab_edit_card(self):
        selected = self.lab_tree.selection()
        if not selected:
            messagebox.showwarning("Selección vacía", "Por favor selecciona una flashcard para editar.")
            return
        idx = int(selected[0])
        self._show_card_editor_dialog(idx)

    def _lab_delete_card(self):
        selected = self.lab_tree.selection()
        if not selected:
            messagebox.showwarning("Selección vacía", "Por favor selecciona una flashcard para eliminar.")
            return
        idx = int(selected[0])
        if messagebox.askyesno("Confirmar eliminación", "¿Estás seguro de que deseas eliminar esta flashcard de prueba?"):
            self.lab_cards.pop(idx)
            self._update_lab_table()

    def _show_card_editor_dialog(self, idx=None):
        dialog = tk.Toplevel(self)
        dialog.title("Editar Flashcard de Prueba" if idx is not None else "Agregar Flashcard de Prueba")
        dialog.geometry("500x350")
        dialog.minsize(400, 300)
        dialog.grab_set()
        
        init_front = ""
        init_back = ""
        init_bloom = "Bloom II"
        init_comment = ""
        
        if idx is not None:
            card = self.lab_cards[idx]
            init_front = card.get('front', '')
            init_back = card.get('back', '')
            init_bloom = card.get('bloom', 'Bloom II')
            init_comment = card.get('comentario', '')
            
        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill="both", expand=True)
        
        ttk.Label(frame, text="Pregunta:").pack(anchor="w", pady=2)
        txt_front = tk.Text(frame, height=3, wrap="word")
        txt_front.pack(fill="x", pady=2)
        txt_front.insert("1.0", init_front)
        
        ttk.Label(frame, text="Respuesta:").pack(anchor="w", pady=2)
        txt_back = tk.Text(frame, height=3, wrap="word")
        txt_back.pack(fill="x", pady=2)
        txt_back.insert("1.0", init_back)
        
        row_bloom = ttk.Frame(frame)
        row_bloom.pack(fill="x", pady=5)
        ttk.Label(row_bloom, text="Bloom Esperado:").pack(side="left", padx=(0, 10))
        combo_bloom = ttk.Combobox(row_bloom, values=["Bloom I", "Bloom II", "Bloom III"], state="readonly", width=15)
        combo_bloom.set(init_bloom)
        combo_bloom.pack(side="left")
        
        ttk.Label(frame, text="Comentario:").pack(anchor="w", pady=2)
        entry_comment = ttk.Entry(frame)
        entry_comment.pack(fill="x", pady=2)
        entry_comment.insert(0, init_comment)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(15, 0))
        
        def save():
            front = txt_front.get("1.0", "end-1c").strip()
            back = txt_back.get("1.0", "end-1c").strip()
            bloom = combo_bloom.get()
            comment = entry_comment.get().strip()
            
            if not front or not back:
                messagebox.showerror("Campos vacíos", "Pregunta y Respuesta son campos obligatorios.")
                return
                
            new_card = {
                "front": front,
                "back": back,
                "bloom": bloom,
                "comentario": comment
            }
            
            if idx is not None:
                self.lab_cards[idx] = new_card
            else:
                self.lab_cards.append(new_card)
                
            self._update_lab_table()
            dialog.destroy()
            
        ttk.Button(btn_frame, text="Guardar", command=save).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side="right", padx=5)

    def _update_lab_table(self):
        for item in self.lab_tree.get_children():
            self.lab_tree.delete(item)
            
        for idx, card in enumerate(self.lab_cards):
            self.lab_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    card['front'][:80],
                    card['back'][:80],
                    card['bloom'],
                    card.get('comentario', '')
                )
            )

    def _calculate_lab_metrics(self):
        transcript = self.lab_text.get("1.0", "end-1c").strip()
        if not self.lab_cards:
            messagebox.showwarning("Sin datos", "Por favor agrega al menos una flashcard de prueba.")
            return None
            
        concepts_map = {}
        all_concepts = set()
        
        for idx, card in enumerate(self.lab_cards):
            q_text = card['front']
            ans_text = card['back']
            
            concept = "general"
            combined_text = (q_text + " " + ans_text).lower()
            words = re.findall(r'\b[a-záéíóúñ]{4,}\b', combined_text)
            
            if transcript:
                trans_lower = transcript.lower()
                matching = [w for w in words if w in trans_lower]
                if matching:
                    concept = max(matching, key=len)
            else:
                q_words = re.findall(r'\b[a-záéíóúñ]{4,}\b', q_text.lower())
                if q_words:
                    concept = max(q_words, key=len)
            
            concepts_map[idx] = concept
            all_concepts.add(concept)
            
        pagerank = {}
        if transcript and all_concepts:
            try:
                ranker = EduKGRanker()
                ranker.build_graph(list(all_concepts), transcript)
                pagerank = ranker.calculate_pagerank()
            except Exception as e:
                print(f"Error en EduKGRanker: {e}")
            
        raw_results = []
        for idx, card in enumerate(self.lab_cards):
            q_text = card['front']
            ans_text = card['back']
            bloom = card['bloom']
            
            words_ans = len(ans_text.split())
            q_score = 1.0
            if words_ans > 12:
                q_score -= (words_ans - 12) * 0.04
            q_score = max(0.1, min(1.0, q_score))
            
            b_num = 1 if bloom == "Bloom I" else 2 if bloom == "Bloom II" else 3
                
            concept = concepts_map[idx]
            c_raw = pagerank.get(concept, 0.0)
            
            raw_results.append({
                'idx': idx,
                'card': card,
                'concept': concept,
                'q': q_score,
                'bloom_num': b_num,
                'c_raw': c_raw
            })
            
        return raw_results

    def _compute_scores_for_method(self, raw_results, method, w_q, w_y, w_c, pr_threshold):
        all_c = [r['c_raw'] for r in raw_results]
        
        normalized_results = []
        for r in raw_results:
            c_raw = r['c_raw']
            c_norm = 0.0
            
            if method == "Min-Max":
                c_min = min(all_c)
                c_max = max(all_c)
                if c_max > c_min:
                    c_norm = (c_raw - c_min) / (c_max - c_min)
                else:
                    c_norm = 1.0 if c_raw > 0 else 0.5
            elif method == "Percentil":
                if len(all_c) > 1:
                    c_norm = np.mean([c <= c_raw for c in all_c])
                else:
                    c_norm = 1.0
            elif method == "Z-Score":
                if len(all_c) > 1:
                    c_mean = np.mean(all_c)
                    c_std = np.std(all_c)
                    if c_std > 0:
                        z = (c_raw - c_mean) / c_std
                        c_norm = 1.0 / (1.0 + np.exp(-z))
                    else:
                        c_norm = 0.5
                else:
                    c_norm = 1.0
            else: # Pesos (Raw PageRank)
                c_norm = c_raw
                
            # Dinámico Y score en base a PageRank y Bloom
            is_yield = (c_raw >= pr_threshold) and (r['bloom_num'] >= 2)
            y_score = 1.0 if is_yield else 0.4
            
            score_final = w_q * r['q'] + w_y * y_score + w_c * c_norm
            
            normalized_results.append({
                'card': r['card'],
                'q': r['q'],
                'y': y_score,
                'c': c_norm,
                'score': score_final
            })
            
        normalized_results.sort(key=lambda x: x['score'], reverse=True)
        return normalized_results

    def _run_lab_simulation(self):
        if not self.lab_cards:
            messagebox.showwarning("Sin datos", "Por favor agrega al menos una flashcard de prueba.")
            return
            
        use_ia = self.check_use_ia.get()
        
        if use_ia:
            self.lbl_lab_status.config(text="⏳ Conectando con Gemini...")
            self.btn_simulate.config(state="disabled")
            self.btn_compare_norm.config(state="disabled")
            threading.Thread(target=self._run_lab_simulation_thread, daemon=True).start()
        else:
            self.lbl_lab_status.config(text="⚡ Simulación Rápida (Heurística)")
            self._run_lab_simulation_heuristic()

    def _run_lab_simulation_thread(self):
        try:
            transcript = self.lab_text.get("1.0", "end-1c").strip()
            
            if not self.generator:
                raise ValueError("Generador de contenido IA (Gemini) no configurado en la aplicación.")
                
            # Llamamos al watchdog del sistema
            evals = self._watchdog_evaluate_with_explanation(transcript, self.lab_cards)
            
            # Extraer conceptos
            concepts = [e.get('concepto', 'general') for e in evals]
            
            # Calcular PageRank
            pagerank = {}
            if transcript and concepts:
                try:
                    ranker = EduKGRanker()
                    ranker.build_graph(concepts, transcript)
                    pagerank = ranker.calculate_pagerank()
                except Exception as e:
                    print(f"Error en EduKGRanker: {e}")
                    
            # Construir raw_results
            raw_results = []
            for idx, card in enumerate(self.lab_cards):
                eval_data = next((e for e in evals if e.get('original_id') == idx), None)
                calidad = eval_data.get('calidad', 7) if eval_data else 7
                bloom = eval_data.get('bloom', 2) if eval_data else 2
                concept = eval_data.get('concepto', 'general') if eval_data else 'general'
                
                q_score = calidad / 10.0
                c_raw = pagerank.get(concept, 0.0)
                
                raw_results.append({
                    'idx': idx,
                    'card': card,
                    'concept': concept,
                    'q': q_score,
                    'bloom_num': bloom,
                    'c_raw': c_raw
                })
                
            self.after(0, lambda: self._on_lab_simulation_success(raw_results))
            
        except Exception as e:
            self.after(0, lambda err=str(e): self._on_lab_simulation_error(err))

    def _on_lab_simulation_success(self, raw_results):
        self.lbl_lab_status.config(text="✅ Evaluación IA completada.")
        self.btn_simulate.config(state="normal")
        self.btn_compare_norm.config(state="normal")
        self.last_raw_results = raw_results
        self._refresh_lab_results_ui()

    def _on_lab_simulation_error(self, err_msg):
        self.lbl_lab_status.config(text="❌ Falló evaluación IA.")
        self.btn_simulate.config(state="normal")
        self.btn_compare_norm.config(state="normal")
        messagebox.showerror("Error de Simulación IA", f"Hubo un problema llamando a la IA:\n{err_msg}\n\nSe usará la simulación heurística local como fallback.")
        self._run_lab_simulation_heuristic()

    def _run_lab_simulation_heuristic(self):
        raw_results = self._calculate_lab_metrics()
        if not raw_results:
            return
        self.last_raw_results = raw_results
        self._refresh_lab_results_ui()

    def _refresh_lab_results_ui(self):
        if not hasattr(self, 'last_raw_results') or not self.last_raw_results:
            return
            
        method = self.combo_norm.get()
        w_q = self.slider_phi_q.get()
        w_y = self.slider_phi_y.get()
        w_c = self.slider_phi_c.get()
        
        # Calcular el umbral dinámico de PageRank del slider
        all_c = [r['c_raw'] for r in self.last_raw_results]
        corte_val = self.slider_pr_thresh.get()
        pr_threshold = float(np.percentile(all_c, corte_val * 100)) if all_c else 0.0
        
        results = self._compute_scores_for_method(self.last_raw_results, method, w_q, w_y, w_c, pr_threshold)
        
        for item in self.lab_res_tree.get_children():
            self.lab_res_tree.delete(item)
            
        for r in results:
            self.lab_res_tree.insert(
                "",
                "end",
                values=(
                    r['card']['front'][:80],
                    f"{r['q']:.2f}",
                    f"{r['y']:.2f}",
                    f"{r['c']:.2f}",
                    f"{r['score']:.2f}"
                )
            )
            
        self.lab_txt_best.config(state="normal")
        self.lab_txt_worst.config(state="normal")
        
        self.lab_txt_best.delete("1.0", "end")
        self.lab_txt_worst.delete("1.0", "end")
        
        top_cards = results[:3]
        for idx, r in enumerate(top_cards):
            medals = ["🏆 1º", "🥈 2º", "🥉 3º"]
            medal = medals[idx] if idx < len(medals) else "⭐"
            self.lab_txt_best.insert("end", f"{medal} [{r['score']:.2f}] {r['card']['front'][:60]}...\n")
            
        bottom_cards = list(reversed(results))[:3]
        for idx, r in enumerate(bottom_cards):
            self.lab_txt_worst.insert("end", f"🔴 [{r['score']:.2f}] {r['card']['front'][:60]}...\n")
            
        self.lab_txt_best.config(state="disabled")
        self.lab_txt_worst.config(state="disabled")

    def _compare_lab_normalizations(self):
        raw_results = getattr(self, 'last_raw_results', None)
        if not raw_results:
            raw_results = self._calculate_lab_metrics()
            
        if not raw_results:
            return
            
        w_q = self.slider_phi_q.get()
        w_y = self.slider_phi_y.get()
        w_c = self.slider_phi_c.get()
        
        # Calcular el umbral dinámico de PageRank del slider
        all_c = [r['c_raw'] for r in raw_results]
        corte_val = self.slider_pr_thresh.get()
        pr_threshold = float(np.percentile(all_c, corte_val * 100)) if all_c else 0.0
        
        res_minmax = self._compute_scores_for_method(raw_results, "Min-Max", w_q, w_y, w_c, pr_threshold)
        res_percentil = self._compute_scores_for_method(raw_results, "Percentil", w_q, w_y, w_c, pr_threshold)
        res_zscore = self._compute_scores_for_method(raw_results, "Z-Score", w_q, w_y, w_c, pr_threshold)
        
        compare_win = tk.Toplevel(self)
        compare_win.title("🔄 Comparación Rápida de Normalizaciones (C)")
        compare_win.geometry("950x450")
        compare_win.minsize(800, 350)
        compare_win.grab_set()
        
        info_frame = ttk.Frame(compare_win, padding=10)
        info_frame.pack(fill="x")
        ttk.Label(info_frame, text=f"Comparativa lado a lado utilizando pesos: ΦQ={w_q:.2f}, ΦY={w_y:.2f}, ΦC={w_c:.2f}", 
                  font=("Segoe UI", 10, "italic")).pack(anchor="w")
                  
        panels_frame = ttk.Frame(compare_win, padding=10)
        panels_frame.pack(fill="both", expand=True)
        
        panels_frame.columnconfigure(0, weight=1)
        panels_frame.columnconfigure(1, weight=1)
        panels_frame.columnconfigure(2, weight=1)
        
        def create_ranking_table(parent, title, results):
            frame = ttk.LabelFrame(parent, text=title, padding=5)
            
            cols = ("rank", "card", "score")
            tree = ttk.Treeview(frame, columns=cols, show="headings")
            tree.heading("rank", text="Puesto")
            tree.heading("card", text="Flashcard")
            tree.heading("score", text="Score Final")
            
            tree.column("rank", width=50, stretch=False, anchor="center")
            tree.column("card", width=180)
            tree.column("score", width=80, stretch=False, anchor="center")
            
            for rank, r in enumerate(results, 1):
                tree.insert("", "end", values=(rank, r['card']['front'][:45], f"{r['score']:.2f}"))
                
            tree.pack(fill="both", expand=True)
            return frame
            
        f1 = create_ranking_table(panels_frame, "Ranking Min-Max", res_minmax)
        f1.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        f2 = create_ranking_table(panels_frame, "Ranking Percentil", res_percentil)
        f2.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        
        f3 = create_ranking_table(panels_frame, "Ranking Z-Score", res_zscore)
        f3.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        
        btn_close = ttk.Button(compare_win, text="Cerrar", command=compare_win.destroy)
        btn_close.pack(pady=10)

    def _load_lab_case(self, event):
        case_name = self.combo_cases.get()
        if case_name == "Detección de ruido":
            transcript = (
                "El ciclo del agua es el proceso de circulación del agua en la Tierra. "
                "La evaporación ocurre cuando el sol calienta el agua líquida y esta sube en forma de vapor. "
                "Por otro lado, ayer el instructor tomó café en una taza roja en la oficina. "
                "Luego, la condensación se produce cuando el vapor se enfría y forma nubes. "
                "Hubo una charla sobre fútbol a mediodía. "
                "Finalmente, la precipitación ocurre cuando el agua cae de las nubes en forma de lluvia."
            )
            cards = [
                {
                    "front": "¿Qué es la evaporación en el ciclo del agua?",
                    "back": "El paso de agua líquida a vapor debido al calentamiento solar.",
                    "bloom": "Bloom II",
                    "comentario": "Concepto central y bien formulado."
                },
                {
                    "front": "¿De qué color era la taza de café del instructor?",
                    "back": "Taza roja.",
                    "bloom": "Bloom I",
                    "comentario": "Información totalmente irrelevante (ruido)."
                },
                {
                    "front": "¿Qué es la condensación?",
                    "back": "El proceso donde el vapor de agua se enfría y se convierte en líquido.",
                    "bloom": "Bloom II",
                    "comentario": "Concepto clave del ciclo."
                },
                {
                    "front": "¿De qué hablaron los empleados a mediodía?",
                    "back": "De fútbol.",
                    "bloom": "Bloom I",
                    "comentario": "Otro detalle ruidoso e irrelevante."
                }
            ]
        elif case_name == "Bloom I vs II vs III":
            transcript = (
                "La Ley de Ohm establece la relación entre voltaje, corriente y resistencia. "
                "La fórmula fundamental es V = I * R. "
                "Voltaje (V) es la diferencia de potencial medida en Voltios. "
                "Corriente (I) es el flujo de carga medida en Amperios. "
                "Resistencia (R) es la oposición al flujo medida en Ohmios. "
                "Si la resistencia se reduce a la mitad, la corriente se duplica para un voltaje constante."
            )
            cards = [
                {
                    "front": "¿Qué significa la letra 'V' en la fórmula de la Ley de Ohm?",
                    "back": "Voltaje.",
                    "bloom": "Bloom I",
                    "comentario": "Nivel recordar: memorización simple del símbolo."
                },
                {
                    "front": "¿Por qué aumenta la corriente si la resistencia disminuye con voltaje constante?",
                    "back": "Porque la corriente es inversamente proporcional a la resistencia según la Ley de Ohm.",
                    "bloom": "Bloom II",
                    "comentario": "Nivel entender: requiere comprender la relación conceptual."
                },
                {
                    "front": "Si un circuito tiene un voltaje de 12V y una resistencia de 6 Ohmios, ¿cuál es la corriente?",
                    "back": "2 Amperios. Se calcula usando I = V / R, donde I = 12 / 6 = 2.",
                    "bloom": "Bloom III",
                    "comentario": "Nivel aplicar: requiere resolver un ejercicio práctico con la fórmula."
                }
            ]
        elif case_name == "Concepto central vs periférico":
            transcript = (
                "La criptografía simétrica utiliza una única clave secreta para cifrar y descifrar la información. "
                "El algoritmo estándar para criptografía simétrica es AES. "
                "La criptografía simétrica requiere que el emisor y receptor compartan la clave de forma segura. "
                "Un detalle histórico menor es que el concurso para elegir AES se inició en 1997."
            )
            cards = [
                {
                    "front": "¿Cuál es la característica principal de la criptografía simétrica?",
                    "back": "Que utiliza la misma clave para cifrar y descifrar los datos.",
                    "bloom": "Bloom II",
                    "comentario": "Concepto central con alta frecuencia y centralidad."
                },
                {
                    "front": "¿En qué año se inició el concurso para elegir el estándar AES?",
                    "back": "En 1997.",
                    "bloom": "Bloom I",
                    "comentario": "Dato periférico e histórico secundario (baja centralidad)."
                }
            ]
        else:
            return
            
        self.lab_text.delete("1.0", "end")
        self.lab_text.insert("1.0", transcript)
        
        self.lab_cards = cards
        self._update_lab_table()

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

    def _set_source_context(self, content: str, source_label: str):
        if not content:
            messagebox.showwarning("Archivo Vacío", "No se pudo obtener texto del archivo seleccionado.")
            return
            
        if self.app:
            self.app.current_source_context = content
            
        char_count = len(content)
        self.lbl_source_status.config(text="✅ Fuente cargada", foreground="green")
        self.lbl_source_info.config(text=f"Fuente de {char_count:,} caracteres cargada desde {source_label}.", foreground="black")

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
