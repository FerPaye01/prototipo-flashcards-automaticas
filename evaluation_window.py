import tkinter as tk
from tkinter import ttk, messagebox
import threading
import re
import json
from typing import List, Dict, Any, Callable

class EvaluationUI(tk.Toplevel):
    def __init__(self, parent, pending_imports: List[Dict[str, Any]], on_complete: Callable, generator):
        super().__init__(parent)
        self.title("🎓 Rúbrica Pedagógica e Indicadores QYI (IA)")
        self.geometry("1200x700")
        self.minsize(1000, 550)
        self.grab_set()  # Ventana modal
        
        self.pending_imports = pending_imports
        self.on_complete = on_complete
        self.generator = generator
        
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
            "Fórmula QYI (Quality Yield Index): QYI = 0.3*Φ_Q + 0.4*Φ_Y + 0.3*Φ_C"
        )
        lbl_explain = tk.Message(explain_frame, text=explain_text, width=320, font=("Segoe UI", 9), justify="left", fg="#333333")
        lbl_explain.pack(fill="both", expand=True)
        
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
        
        ttk.Label(filter_frame, text="Calidad Mínima (0-10):").grid(row=0, column=0, sticky="w", padx=5)
        self.spin_quality = ttk.Spinbox(filter_frame, from_=0, to=10, width=5)
        self.spin_quality.set("5")
        self.spin_quality.grid(row=0, column=1, sticky="w", padx=5)
        
        self.check_only_high = tk.BooleanVar(value=False)
        chk_high = ttk.Checkbutton(filter_frame, text="Solo tarjetas de Alto Impacto", variable=self.check_only_high)
        chk_high.grid(row=0, column=2, sticky="w", padx=15)
        
        btn_apply_filter = ttk.Button(filter_frame, text="🧹 Descartar que no cumplan", command=self._apply_quick_filters)
        btn_apply_filter.grid(row=0, column=3, sticky="e", padx=10)
        
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
            # 1. Construir texto de referencia concatenado
            text_ref = "\n\n".join([
                f"P: {c.get('front', '')}\nR: {c.get('back', '')}"
                for c in self.flat_flashcards
            ])
            
            # 2. Extraer conceptos usando el generador
            self.after(0, lambda: self.lbl_status.config(text="Estado: Analizando mapa de conceptos..."))
            concepts = self.generator.extract_concepts(text_ref)
            if not concepts:
                concepts = ["general"]
                
            # 3. Construir grafo y PageRank
            self.after(0, lambda: self.lbl_status.config(text="Estado: Calculando PageRank del Grafo..."))
            self.generator.kg_ranker.build_graph(concepts, text_ref)
            pagerank = self.generator.kg_ranker.calculate_pagerank()
            
            # 4. Watchdog de evaluación en lotes (evita timeouts y límites de tokens)
            evals = self._watchdog_evaluate_with_explanation(text_ref, self.flat_flashcards)
            
            # 5. Mapear y computar puntuación de utilidad individual
            alpha, beta, gamma = 0.3, 0.4, 0.3
            all_pr = list(pagerank.values())
            pr_min = min(all_pr) if all_pr else 0.0
            pr_max = max(all_pr) if all_pr else 1.0
            pr_range = pr_max - pr_min if pr_max > pr_min else 1.0
            
            qualities = []
            is_high = []
            card_concepts = []
            
            for idx, card in enumerate(self.flat_flashcards):
                # Encontrar evaluación correspondiente
                eval_data = next((e for e in evals if e.get('original_id') == idx), None)
                calidad = eval_data.get('calidad', 7) if eval_data else 7
                impacto = eval_data.get('impacto', 'N') if eval_data else 'N'
                explicacion = eval_data.get('explicacion', "Completado.") if eval_data else "Evaluado con éxito."
                
                # Asignar concepto
                txt = (card.get('front','') + card.get('back','')).lower()
                matched_concept = next((cp for cp in concepts if cp.lower() in txt), "general")
                card['concept'] = matched_concept
                
                # Obtener centralidad de PageRank
                pr_val = pagerank.get(matched_concept, 0.0)
                norm_pr = (pr_val - pr_min) / pr_range if pr_range > 0 else 0.5
                
                # Calcular utilidad individual
                util_score = alpha * (calidad / 10.0) + beta * (1.0 if impacto == 'S' else 0.0) + gamma * norm_pr
                
                # Guardar valores evaluados
                card['_status'] = "Evaluada"
                card['_calidad'] = calidad
                card['_impacto'] = impacto
                card['_centralidad'] = pr_val
                card['_utilidad'] = util_score
                card['_explicacion'] = explicacion
                
                qualities.append(calidad / 10.0)
                is_high.append(impacto == 'S')
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
                "Eres un Evaluador Pedagógico Senior de Flashcards de Anki. Evalúa las siguientes tarjetas respecto a su calidad didáctica (0 a 10), "
                "si son de alto impacto para un examen técnico o práctica real (impacto 'S' para sí, 'N' para no) y provee una explicación muy breve (máximo 15 palabras).\n"
                f"Texto de referencia: {text[:1200]}\n\n"
                "Flashcards a evaluar:\n"
            )
            for idx, c in enumerate(batch):
                prompt += f"ID:{idx} | P: {c.get('front', '')[:120]} | R: {c.get('back', '')[:120]}\n"
                
            prompt += (
                "\nResponde ÚNICAMENTE con un arreglo JSON en este formato:\n"
                '[{"id": 0, "calidad": 8, "impacto": "S", "explicacion": "Explicación corta de la relevancia o fallo"}, ...]\n'
                "No agregues texto introductorio o de cierre fuera del JSON."
            )
            
            try:
                res = self.generator.generate_raw_response(prompt)
                match = re.search(r'\[.*\]', res, re.DOTALL)
                if match:
                    batch_evals = json.loads(match.group())
                    for e in batch_evals:
                        e['original_id'] = batch_idx + e['id']
                    all_evals.extend(batch_evals)
                else:
                    raise ValueError("JSON no encontrado o defectuoso")
            except Exception as e:
                # Fallback
                for idx, _ in enumerate(batch):
                    all_evals.append({
                        "original_id": batch_idx + idx,
                        "calidad": 7,
                        "impacto": "N",
                        "explicacion": "Fallo al procesar rúbrica IA."
                    })
        return all_evals

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

    def _restore_original(self):
        if not messagebox.askyesno("Confirmar restauración", "¿Restaurar todas las tarjetas al estado inicial sin filtros?"):
            return
        self.flat_flashcards = [dict(c) for c in self.original_flat_cards]
        self._update_table_view()
        self._recompute_qyi_if_evaluated()

    def _apply_quick_filters(self):
        # Validar si han sido evaluadas
        any_evaluated = any(c['_status'] == "Evaluada" for c in self.flat_flashcards)
        if not any_evaluated:
            messagebox.showwarning("Requiere evaluación", "Debes presionar 'Iniciar Rúbrica con IA' antes de aplicar filtros.")
            return
            
        min_qual = int(self.spin_quality.get())
        only_high = self.check_only_high.get()
        
        filtered = []
        discarded_count = 0
        
        for c in self.flat_flashcards:
            qual_ok = c['_calidad'] >= min_qual
            impact_ok = True
            if only_high and c['_impacto'] != 'S':
                impact_ok = False
                
            if qual_ok and impact_ok:
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
