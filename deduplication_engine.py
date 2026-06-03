import os
import math
import uuid
import time
from typing import List, Dict, Any, Tuple, Optional, Callable
from google import genai
from dotenv import load_dotenv


class DeduplicationEngine:
    """
    Motor de deduplicación semántica.

    - Embeddings uno a uno con rotación de llaves/modelos (estrategia matriz).
    - Caché persistente por _id de tarjeta: nunca se re-embede la misma tarjeta.
    - Similitud dual (anverso + reverso) con lógica OR entre 3 condiciones.
    """
    FRONT_WEIGHT = 0.6
    BACK_WEIGHT  = 0.4
    RETRY_WAIT   = 2     # Segundos de espera en 429

    def __init__(self, log_callback: Optional[Callable] = None):
        self.log_callback = log_callback or print
        load_dotenv()

        # Cargar pool de llaves (Misma lógica que el generador)
        kstr = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEYS_OCR") or os.getenv("GEMINI_API_KEY_1")
        if kstr:
            self.api_keys = [k.strip() for k in kstr.split(",") if k.strip()]
        else:
            # Fallback a recolección secuencial si no hay lista
            self.api_keys = []
            for i in range(1, 5):
                k = os.getenv(f"GEMINI_API_KEY_{i}")
                if k: self.api_keys.extend([x.strip() for x in k.split(",") if x.strip()])

        if not self.api_keys:
            raise ValueError("No se encontraron llaves API (GEMINI_API_KEY).")

        # Cargar pool de modelos de embedding
        models_raw = os.getenv("GEMINI_EMBEDDING") or os.getenv("GEMINI_EMBEDDINGS") or "gemini-embedding-2,text-embedding-004"
        self.models = [m.strip() for m in models_raw.split(",") if m.strip()]
        
        # Dimensiones del vector (Configurable)
        self.dimension = int(os.getenv("GEMINI_EMBEDDING_DIM", "768"))

        # ── Caché persistente: card._id → vector ─────────────────────────────
        self._front_cache: Dict[str, List[float]] = {}
        self._back_cache:  Dict[str, List[float]] = {}

    def _log(self, msg: str):
        if self.log_callback:
            self.log_callback(msg)

    # ──────────────────────────────────────────────────────────────────────────
    # Embedding de UN texto con rotación clave×modelo
    # ──────────────────────────────────────────────────────────────────────────
    def _embed_single(self, text: str) -> List[float]:
        """
        Embede un único texto probando todas las combinaciones
        clave × modelo hasta obtener un vector.
        """
        for model_name in self.models:
            for key_idx, api_key in enumerate(self.api_keys):
                try:
                    client = genai.Client(api_key=api_key)
                    response = client.models.embed_content(
                        model=model_name,
                        contents=text          # Un solo texto — garantizado
                    )
                    # El SDK devuelve response.embeddings[0].values
                    if hasattr(response, 'embeddings') and response.embeddings:
                        return list(response.embeddings[0].values)
                    raise ValueError("Respuesta vacía del API de embeddings.")

                except Exception as e:
                    err_str = str(e)
                    if '429' in err_str or 'RESOURCE_EXHAUSTED' in err_str:
                        self._log(
                            f"   ⚠️ 429 — {model_name} Key{key_idx+1} "
                            f"(espera {self.RETRY_WAIT}s, rotando...)"
                        )
                        time.sleep(self.RETRY_WAIT)
                        continue
                    elif '503' in err_str or 'UNAVAILABLE' in err_str:
                        self._log(f"   ⚠️ 503 — {model_name} Key{key_idx+1} (rotando...)")
                        time.sleep(1)
                        continue
                    else:
                        # Error no recuperable con esta llave → probar siguiente
                        self._log(f"   ❌ Error permanente {model_name} Key{key_idx+1}: {e}")
                        break

            self._log(f"   ⚠️ {model_name} agotado → siguiente modelo...")

        raise Exception("Todos los modelos y llaves fallaron para este texto.")

    # ──────────────────────────────────────────────────────────────────────────
    # Embeddings con caché persistente
    # ──────────────────────────────────────────────────────────────────────────
    def _embed_cards(
        self,
        cards: List[dict],
        text_extractor: Callable[[dict], str],
        cache: Dict[str, List[float]],
        phase_label: str
    ) -> List[List[float]]:
        """
        Devuelve un vector por tarjeta usando la caché.
        Solo llama a la API para tarjetas sin vector previo.
        """
        total    = len(cards)
        hits     = sum(1 for c in cards if c.get('_id', '') in cache)
        misses   = total - hits

        if hits > 0:
            self._log(f"   💾 {phase_label}: {hits} de caché, {misses} nuevos.")

        results: List[List[float]] = []
        computed = 0

        for i, card in enumerate(cards):
            cid = card.get('_id', '')
            if cid and cid in cache:
                results.append(cache[cid])
                continue

            text = text_extractor(card)
            if not text.strip():
                # Texto vacío → vector cero (evita llamada innecesaria)
                dummy = [0.0] * self.dimension
                if cid:
                    cache[cid] = dummy
                results.append(dummy)
                continue

            computed += 1
            self._log(
                f"   🧠 {phase_label} [{computed}/{misses}] "
                f"Calculando embedding #{i+1}..."
            )
            vec = self._embed_single(text)
            if cid:
                cache[cid] = vec
            results.append(vec)

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers de extracción de texto
    # ──────────────────────────────────────────────────────────────────────────
    def _get_front(self, card: dict) -> str:
        return card.get('front', card.get('text', card.get('term', '')))

    def _get_back(self, card: dict) -> str:
        return card.get('back', card.get('extra', card.get('context', '')))

    # ──────────────────────────────────────────────────────────────────────────
    # Similitud coseno
    # ──────────────────────────────────────────────────────────────────────────
    def cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        dot  = sum(a * b for a, b in zip(v1, v2))
        mag1 = math.sqrt(sum(a * a for a in v1))
        mag2 = math.sqrt(sum(b * b for b in v2))
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)

    # ──────────────────────────────────────────────────────────────────────────
    # Clustering principal
    # ──────────────────────────────────────────────────────────────────────────
    def cluster_flashcards(
        self,
        flashcards: List[Dict[str, Any]],
        threshold: float = 0.88
    ) -> Tuple[List[Dict], List[List[Dict]]]:
        """
        Retorna (unicas, clusters_de_duplicados).

        Condiciones OR (cualquiera marca como duplicado):
          1. sim_front    >= threshold  → pregunta similar
          2. sim_back     >= threshold  → respuesta similar
          3. sim_combined >= threshold  → combinación ponderada
        """
        self._log(f"📊 Analizando {len(flashcards)} flashcards...")

        if not flashcards:
            return [], []

        # Asignar IDs únicos
        for card in flashcards:
            if '_id' not in card:
                card['_id'] = str(uuid.uuid4())

        # ── Fase 1: Embeddings de anversos ────────────────────────────────
        self._log("📡 Fase 1/2: Anversos (preguntas)...")
        front_vecs = self._embed_cards(
            flashcards, self._get_front, self._front_cache, "Anverso"
        )

        # ── Fase 2: Embeddings de reversos ────────────────────────────────
        has_backs = any(self._get_back(c).strip() for c in flashcards)
        if has_backs:
            self._log("📡 Fase 2/2: Reversos (respuestas)...")
            back_vecs: Optional[List[List[float]]] = self._embed_cards(
                flashcards, self._get_back, self._back_cache, "Reverso"
            )
        else:
            self._log("ℹ️ Sin reversos — usando solo similitud de anversos.")
            back_vecs = None

        # ── Fase 3: Clustering O(N²) con lógica OR ────────────────────────
        self._log("🔍 Calculando similitudes...")
        clusters:     List[List[Dict]] = []
        assigned_ids: set              = set()

        for i, card_i in enumerate(flashcards):
            if card_i['_id'] in assigned_ids:
                continue

            cluster = [card_i]
            assigned_ids.add(card_i['_id'])

            for j in range(i + 1, len(flashcards)):
                card_j = flashcards[j]
                if card_j['_id'] in assigned_ids:
                    continue

                sim_front = self.cosine_similarity(front_vecs[i], front_vecs[j])

                sim_back: Optional[float] = None
                back_i = self._get_back(card_i).strip()
                back_j = self._get_back(card_j).strip()
                if back_vecs and back_i and back_j:
                    sim_back = self.cosine_similarity(back_vecs[i], back_vecs[j])

                sim_combined = (
                    self.FRONT_WEIGHT * sim_front + self.BACK_WEIGHT * sim_back
                    if sim_back is not None
                    else sim_front
                )

                match_reason: Optional[str] = None
                if sim_front >= threshold:
                    match_reason = "pregunta"
                elif sim_back is not None and sim_back >= threshold:
                    match_reason = "respuesta"
                elif sim_combined >= threshold:
                    match_reason = "combinada"

                if match_reason:
                    display_sim = {
                        "pregunta":  sim_front,
                        "respuesta": sim_back if sim_back is not None else sim_front,
                        "combinada": sim_combined,
                    }[match_reason]

                    card_j['_similitud']    = round(display_sim  * 100, 1)
                    card_j['_sim_front']    = round(sim_front    * 100, 1)
                    card_j['_sim_back']     = round(sim_back     * 100, 1) if sim_back is not None else None
                    card_j['_sim_combined'] = round(sim_combined * 100, 1)
                    card_j['_match_reason'] = match_reason
                    cluster.append(card_j)
                    assigned_ids.add(card_j['_id'])

            if len(cluster) > 1:
                card_i['_similitud']    = 100.0
                card_i['_sim_front']    = 100.0
                card_i['_sim_back']     = None
                card_i['_sim_combined'] = 100.0
                card_i['_match_reason'] = "base"
                clusters.append(cluster)

        in_cluster   = {c['_id'] for cl in clusters for c in cl}
        unique_cards = [c for c in flashcards if c['_id'] not in in_cluster]

        self._log(
            f"✅ {len(unique_cards)} únicas · {len(clusters)} grupos de interferencia "
            f"(umbral {threshold*100:.0f}%)"
        )
        return unique_cards, clusters
