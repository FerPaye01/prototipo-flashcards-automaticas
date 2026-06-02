import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import List, Dict, Any, Callable
from deduplication_engine import DeduplicationEngine

class DeduplicationUI(tk.Toplevel):
    def __init__(self, parent, pending_imports: List[Dict[str, Any]], on_complete: Callable,
                 engine=None):
        super().__init__(parent)
        self.title("🧠 Filtro de Interferencia por IA (Embeddings)")
        self.geometry("1100x650")
        self.minsize(900, 500)
        self.grab_set()  # Modal
        
        self.pending_imports = pending_imports
        self.on_complete = on_complete
        
        # Índices separados por árbol para evitar colisión de iid entre widgets
        self._unique_index:  Dict[str, dict] = {}   # iid de tree_unique  → card
        self._cluster_index: Dict[str, dict] = {}   # iid de tree_cluster → card
        
        # Usar engine externo (con caché persistente) o crear uno nuevo
        if engine is not None:
            self.engine = engine
            # Actualizar el log_callback para apuntar a esta ventana
            self.engine.log_callback = self._log_progress
        else:
            from deduplication_engine import DeduplicationEngine
            self.engine = DeduplicationEngine(log_callback=self._log_progress)
        
        self.unique_cards = []
        self.clusters = []
        
        # Flatten flashcards for engine
        self.flat_flashcards = []
        for group in self.pending_imports:
            deck_name = group['deck_name']
            card_type = group['card_type']
            for card in group['flashcards']:
                card['_group_ref'] = group
                card['_deck_name'] = deck_name
                card['_card_type'] = card_type
                self.flat_flashcards.append(card)
                
        self._build_ui()
        self._start_engine()

    # ─────────────────────────────────────────────────────────────
    # UI CONSTRUCTION
    # ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Top frame for status
        top_frame = ttk.Frame(self, padding=10)
        top_frame.pack(fill="x")
        self._top_frame = top_frame  # Referencia para el botón de reintento
        
        self.lbl_status = ttk.Label(top_frame, text="Iniciando motor semántico...", font=("Segoe UI", 11, "bold"))
        self.lbl_status.pack(side="left")
        
        self.progress = ttk.Progressbar(top_frame, mode="indeterminate")
        self.progress.pack(side="right", fill="x", expand=True, padx=10)
        # (La barra se inicia en _start_engine, no aqui)
        
        # Hint label
        hint = ttk.Label(top_frame, text="💡 Doble clic para ver contenido completo",
                         font=("Segoe UI", 9), foreground="gray")
        hint.pack(side="right", padx=15)
        
        # Main Split Frame
        self.paned = ttk.PanedWindow(self, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Left Panel (Uniques)
        left_frame = ttk.LabelFrame(self.paned, text="✅ Tarjetas Únicas (Seguras)")
        self.paned.add(left_frame, weight=1)
        
        columns = ("deck", "front")
        self.tree_unique = ttk.Treeview(left_frame, columns=columns, show="headings", selectmode="extended")
        self.tree_unique.heading("deck", text="Mazo Destino")
        self.tree_unique.heading("front", text="Pregunta")
        self.tree_unique.column("deck", width=150, stretch=False)
        self.tree_unique.column("front", width=300)
        
        scroll_unique = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree_unique.yview)
        self.tree_unique.configure(yscrollcommand=scroll_unique.set)
        self.tree_unique.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scroll_unique.pack(side="right", fill="y", pady=5)
        
        # Double-click on unique cards
        self.tree_unique.bind("<Double-Button-1>", self._on_unique_double_click)
        
        # Right Panel (Clusters)
        right_frame = ttk.LabelFrame(self.paned, text="⚠️ Interferencia / Duplicados Detectados")
        self.paned.add(right_frame, weight=2)
        
        self.tree_cluster = ttk.Treeview(right_frame, columns=("sim", "deck", "front"), show="tree headings", selectmode="browse")
        self.tree_cluster.heading("#0", text="Eliminar")
        self.tree_cluster.heading("sim", text="Similitud")
        self.tree_cluster.heading("deck", text="Mazo Destino")
        self.tree_cluster.heading("front", text="Pregunta / Anverso")
        
        self.tree_cluster.column("#0", width=80, stretch=False, anchor="center")
        self.tree_cluster.column("sim", width=70, stretch=False, anchor="center")
        self.tree_cluster.column("deck", width=120, stretch=False)
        self.tree_cluster.column("front", width=300)
        
        scroll_cluster = ttk.Scrollbar(right_frame, orient="vertical", command=self.tree_cluster.yview)
        self.tree_cluster.configure(yscrollcommand=scroll_cluster.set)
        self.tree_cluster.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scroll_cluster.pack(side="right", fill="y", pady=5)
        
        # Events for cluster tree
        self.tree_cluster.bind("<ButtonRelease-1>", self._on_tree_click)
        self.tree_cluster.bind("<space>", self._on_tree_space)
        self.tree_cluster.bind("<Double-Button-1>", self._on_cluster_double_click)
        
        # Bottom Frame
        bottom_frame = ttk.Frame(self, padding=10)
        bottom_frame.pack(fill="x")
        
        self.lbl_stats = ttk.Label(bottom_frame, text="Esperando...")
        self.lbl_stats.pack(side="left")
        
        self.btn_apply = ttk.Button(bottom_frame, text="✅ Eliminar Marcados y Aplicar",
                                    command=self._apply_and_close, state="disabled")
        self.btn_apply.pack(side="right")

    # ─────────────────────────────────────────────────────────────
    # ENGINE
    # ─────────────────────────────────────────────────────────────
    def _start_engine(self):
        """Inicia (o reinicia) el motor semántico en un hilo daemon."""
        self.progress.start()
        self.btn_apply.config(state="disabled")
        threading.Thread(target=self._run_engine, daemon=True).start()

    def _log_progress(self, msg: str):
        self.after(0, lambda m=msg: self.lbl_status.config(text=m))
        
    def _run_engine(self):
        try:
            self.unique_cards, self.clusters = self.engine.cluster_flashcards(
                self.flat_flashcards, threshold=0.88
            )
            self.after(0, self._populate_ui)
        except Exception as e:
            self.after(0, lambda err=str(e): self._show_engine_error(err))

    def _show_engine_error(self, error_msg: str):
        """Muestra el error sin cerrar la ventana — permite reintentar."""
        self.progress.stop()
        self.progress.pack_forget()
        self.lbl_status.config(
            text=f"⚠️ Error: {error_msg[:120]}",
            foreground="red"
        )
        # Mostrar botón de reintento
        retry_btn = ttk.Button(
            self,
            text="🔄 Reintentar Análisis",
            command=self._on_retry
        )
        retry_btn.pack(pady=5)
        self._retry_btn = retry_btn

    def _on_retry(self):
        """Limpia el estado y relanza el motor."""
        if hasattr(self, '_retry_btn'):
            self._retry_btn.destroy()
        self.lbl_status.config(text="Reintentando...", foreground="black")
        # Re-mostrar barra de progreso
        self.progress = ttk.Progressbar(self._top_frame, mode="indeterminate")
        self.progress.pack(side="right", fill="x", expand=True, padx=10)
        self._start_engine()

    # ─────────────────────────────────────────────────────────────
    # POPULATION
    # ─────────────────────────────────────────────────────────────
    def _get_display_text(self, card: dict) -> str:
        if 'front' in card: return card['front']
        if 'text' in card: return card['text']
        if 'term' in card: return card['term']
        return str(card)[:80]

    def _populate_ui(self):
        self.progress.stop()
        self.progress.pack_forget()
        self.lbl_status.config(text="✅ Análisis semántico completado. Doble clic para ver tarjeta completa.")
        
        # Populate Uniques — guardar en índice de únicas
        for card in self.unique_cards:
            iid = self.tree_unique.insert("", "end", values=(
                card.get('_deck_name', 'Default'),
                self._get_display_text(card)
            ))
            self._unique_index[iid] = card
            
        # Populate Clusters
        for idx, cluster in enumerate(self.clusters):
            parent_id = self.tree_cluster.insert("", "end", text="[ ]", values=(
                "", "", f"📁 Clúster {idx+1} ({len(cluster)} tarjetas similares)"
            ), tags=('parent',))
            
            for c_idx, card in enumerate(cluster):
                checkbox = "[x]" if c_idx > 0 else "[ ]"
                if c_idx == 0:
                    sim_str = "100% (Base)"
                else:
                    sim_combined = card.get('_similitud', 0)
                    sim_front    = card.get('_sim_front')
                    sim_back     = card.get('_sim_back')
                    reason       = card.get('_match_reason', 'combinada')

                    reason_icons = {
                        "pregunta":  "❓",
                        "respuesta": "💡",
                        "combinada": "🔗",
                    }
                    icon = reason_icons.get(reason, "🔗")

                    parts = [f"{icon} {sim_combined}%"]
                    if sim_front is not None:
                        parts.append(f"P:{sim_front}%")
                    if sim_back is not None:
                        parts.append(f"R:{sim_back}%")
                    sim_str = " | ".join(parts)
                
                iid = self.tree_cluster.insert(parent_id, "end", text=checkbox, values=(
                    sim_str,
                    card.get('_deck_name', 'Default'),
                    self._get_display_text(card)
                ), tags=('child', card['_id']))
                
                # Guardar en índice de clústeres (separado del de únicas)
                self._cluster_index[iid] = card
                
            self.tree_cluster.item(parent_id, open=True)
            
        self.lbl_stats.config(
            text=f"Total: {len(self.flat_flashcards)} | "
                 f"Únicas: {len(self.unique_cards)} | "
                 f"Grupos Duplicados: {len(self.clusters)}"
        )
        self.btn_apply.config(state="normal")

    # ─────────────────────────────────────────────────────────────
    # DOUBLE CLICK → CARD DETAIL VIEWER
    # ─────────────────────────────────────────────────────────────
    def _on_unique_double_click(self, event):
        item_id = self.tree_unique.identify_row(event.y)
        if item_id and item_id in self._unique_index:
            self._show_card_detail(self._unique_index[item_id])

    def _on_cluster_double_click(self, event):
        item_id = self.tree_cluster.identify_row(event.y)
        if not item_id:
            return
        tags = self.tree_cluster.item(item_id, "tags")
        if 'parent' in tags:
            return
        if item_id in self._cluster_index:
            self._show_card_detail(self._cluster_index[item_id])

    def _show_card_detail(self, card: dict):
        """Ventana flotante que muestra el contenido completo de una flashcard."""
        win = tk.Toplevel(self)
        win.title("📄 Contenido de la Flashcard")
        win.geometry("620x420")
        win.resizable(True, True)
        win.transient(self)
        
        # Center over deduplication window
        win.update_idletasks()
        px = self.winfo_x() + (self.winfo_width() - 620) // 2
        py = self.winfo_y() + (self.winfo_height() - 420) // 2
        win.geometry(f"+{px}+{py}")
        
        # Header info
        header = ttk.Frame(win, padding=(10, 8, 10, 4))
        header.pack(fill="x")
        
        deck_name = card.get('_deck_name', '')
        card_type = card.get('_card_type', '')
        sim = card.get('_similitud')
        sim_front = card.get('_sim_front')
        sim_back  = card.get('_sim_back')
        
        ttk.Label(header, text=f"🗂 Mazo: {deck_name}", font=("Segoe UI", 9),
                  foreground="#555").pack(anchor="w")
        ttk.Label(header, text=f"🏷 Tipo: {card_type}", font=("Segoe UI", 9),
                  foreground="#555").pack(anchor="w")
        if sim is not None and sim < 100:
            reason = card.get('_match_reason', 'combinada')
            reason_labels = {
                "pregunta":  ("❓", "Pregunta similar"),
                "respuesta": ("💡", "Respuesta similar"),
                "combinada": ("🔗", "Similitud combinada"),
            }
            icon, label = reason_labels.get(reason, ("🔗", "Similitud combinada"))
            sim_color = "#c0392b" if sim >= 90 else "#e67e22"
            sim_frame = ttk.Frame(header)
            sim_frame.pack(anchor="w", pady=(2, 0))
            ttk.Label(sim_frame, text=f"{icon} {label}: {sim}%",
                      font=("Segoe UI", 9, "bold"), foreground=sim_color).pack(side="left")
            sim_front    = card.get('_sim_front')
            sim_back     = card.get('_sim_back')
            sim_combined = card.get('_sim_combined')
            detail_parts = []
            if sim_front    is not None: detail_parts.append(f"P: {sim_front}%")
            if sim_back     is not None: detail_parts.append(f"R: {sim_back}%")
            if sim_combined is not None and reason != "combinada": detail_parts.append(f"Comb: {sim_combined}%")
            if detail_parts:
                ttk.Label(sim_frame, text=f"  ({' · '.join(detail_parts)})",
                          font=("Segoe UI", 9), foreground="#666").pack(side="left")
        
        ttk.Separator(win, orient="horizontal").pack(fill="x", padx=10, pady=4)
        
        # Paned: anverso arriba, reverso abajo
        paned = ttk.PanedWindow(win, orient="vertical")
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        
        # Anverso
        front_frame = ttk.LabelFrame(paned, text="📝 Anverso / Pregunta")
        paned.add(front_frame, weight=1)
        
        front_text = tk.Text(front_frame, wrap="word", font=("Segoe UI", 11),
                             relief="flat", bg="#f8f9fa", state="normal", height=5)
        front_scroll = ttk.Scrollbar(front_frame, orient="vertical", command=front_text.yview)
        front_text.configure(yscrollcommand=front_scroll.set)
        front_scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)
        front_text.pack(fill="both", expand=True, padx=4, pady=4)
        
        # Reverso
        back_frame = ttk.LabelFrame(paned, text="💡 Reverso / Respuesta")
        paned.add(back_frame, weight=1)
        
        back_text = tk.Text(back_frame, wrap="word", font=("Segoe UI", 11),
                            relief="flat", bg="#f0fff4", state="normal", height=5)
        back_scroll = ttk.Scrollbar(back_frame, orient="vertical", command=back_text.yview)
        back_text.configure(yscrollcommand=back_scroll.set)
        back_scroll.pack(side="right", fill="y", padx=(0, 4), pady=4)
        back_text.pack(fill="both", expand=True, padx=4, pady=4)
        
        # Fill content
        front_content = card.get('front', card.get('text', card.get('term', '')))
        back_content = card.get('back', card.get('extra', card.get('context', '')))
        
        front_text.insert("1.0", front_content)
        front_text.config(state="disabled")
        
        back_text.insert("1.0", back_content)
        back_text.config(state="disabled")
        
        # Close button
        ttk.Button(win, text="Cerrar", command=win.destroy).pack(pady=(0, 8))

    # ─────────────────────────────────────────────────────────────
    # CHECKBOX LOGIC
    # ─────────────────────────────────────────────────────────────
    def _toggle_node(self, item_id):
        current_text = self.tree_cluster.item(item_id, "text")
        new_text = "[ ]" if current_text == "[x]" else "[x]"
        self.tree_cluster.item(item_id, text=new_text)
        
        tags = self.tree_cluster.item(item_id, "tags")
        if 'parent' in tags:
            for child_id in self.tree_cluster.get_children(item_id):
                self.tree_cluster.item(child_id, text=new_text)

    def _on_tree_click(self, event):
        region = self.tree_cluster.identify_region(event.x, event.y)
        if region == "tree":
            item_id = self.tree_cluster.identify_row(event.y)
            if item_id:
                self._toggle_node(item_id)
                
    def _on_tree_space(self, event):
        selected = self.tree_cluster.selection()
        if selected:
            self._toggle_node(selected[0])

    # ─────────────────────────────────────────────────────────────
    # APPLY & CLOSE
    # ─────────────────────────────────────────────────────────────
    def _apply_and_close(self):
        to_delete_ids = set()
        for parent_id in self.tree_cluster.get_children():
            for child_id in self.tree_cluster.get_children(parent_id):
                if self.tree_cluster.item(child_id, "text") == "[x]":
                    tags = self.tree_cluster.item(child_id, "tags")
                    if len(tags) > 1:
                        to_delete_ids.add(tags[1])
        
        deleted_count = 0
        for group in self.pending_imports:
            original_len = len(group['flashcards'])
            group['flashcards'] = [c for c in group['flashcards'] if c.get('_id') not in to_delete_ids]
            deleted_count += (original_len - len(group['flashcards']))
            
            for c in group['flashcards']:
                c.pop('_id', None)
                c.pop('_group_ref', None)
                c.pop('_deck_name', None)
                c.pop('_card_type', None)
                c.pop('_similitud', None)
                
        messagebox.showinfo("Deduplicación", f"Se han eliminado {deleted_count} tarjetas duplicadas.", parent=self)
        self.on_complete(self.pending_imports)
        self.destroy()
