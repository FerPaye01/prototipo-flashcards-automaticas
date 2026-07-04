"""
Generador de Flashcards usando Gemini API.
Procesa imágenes, video, audio y PDF para generar flashcards pedagógicas de alta calidad (QYI).
"""

import os
import threading
import time
import socket
import json
import re
from typing import List, Dict, Any, Callable, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv
import numpy as np
import google.generativeai as genai
from PIL import Image
from config_sets_manager import (DEFAULT_PROMPTS, DEFAULT_PROMPTS2, DEFAULT_PROMPTS3,
                                 DEFAULT_PROMPTS4, DEFAULT_PROMPTS5, DEFAULT_PROMPTS6,
                                 DEFAULT_PROMPTS7, SOURCE_CONTEXT_INSTRUCTION)
from qyi_evaluator import QYIEvaluator, EduKGRanker

# Tesseract OCR como fallback
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# Cargar variables de entorno
load_dotenv()

# Carpeta maestra
MASTER_FOLDER = "Flashcards Programa"

# Mínimo de caracteres para considerar que hay contenido educativo real
MIN_CONTENT_CHARS = 300


def _safe_filename(name: str, fallback: str = "sin_titulo") -> str:
    """Sanitiza una cadena para uso como nombre de archivo/carpeta en Windows.
    Reemplaza saltos de línea, elimina caracteres prohibidos y limita la longitud."""
    if not name:
        return fallback
    name = name.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = " ".join(name.split())
    if len(name) > 120:
        name = name[:117] + "..."
    return name.strip() or fallback

class GeminiFlashcardGenerator:
    """Generador avanzado con soporte Multimodal y Evaluación QYI."""
    
    OCR_PROMPT = """Actúa como un excelente estudiante universitario especializado, elaborando material de estudio integral basado en las IMÁGENES proporcionadas. 
    Tu instrucción ESTRICTA es integrar y consolidar paso a paso todo el conocimiento visual (diapositivas, tablas, esquemas, ejemplos en pantalla) que aparezca a lo largo de las imágenes, en conjunto cronológico con el texto que logres identificar.
    Debes añadir observaciones y apuntes complementarios como un estudiante brillante resaltando lo relevante del contenido, todo con la mejor ortografía y puntuación posibles en español.
    ESTÁ ESTRICTAMENTE PROHIBIDO SIMPLIFICAR O RESUMIR; no debes perder información sin importar qué tan largo sea el texto. Debes recuperar hasta el último detalle técnico válido.
    ADICIONALMENTE: Si detectas fragmentos de CÓDIGO o ESPECIFICACIONES TÉCNICAS, debes recrearlos ÍNTEGRAMENTE sin modificar ni una sola línea de sintaxis. Si es una tabla, reconsrúyela en formato Markdown.
    Devuelve solo el texto extraído y enriquecido, estructurado en Markdown limpio."""
    
    FAITHFUL_BOOK_PROMPT = """Actúa como un transcriptor y asistente académico de precisión quirúrgica.
    Tu única tarea es transcribir fielmente y al 100% el contenido del documento proporcionado, sin resumir, sin parafrasear destructivamente, sin omitir y sin agregar comentarios personales u observaciones.

    INSTRUCCIONES DETALLADAS DE TRANSCRIPCIÓN:
    1. FIDELIDAD ABSOLUTA DEL TEXTO: Recupera todo el contenido escrito, explicaciones, ejemplos, definiciones y detalles técnicos verbatim (tal y como están escritos). No resumas capítulos ni simplifiques las ideas.
    2. ESTRUCTURA Y COMPAGINACIÓN: Usa formato Markdown (encabezados, listas con viñetas, tablas) para mantener la estructura jerárquica original del documento. Si hay tablas de datos, recréalas tal cual usando tablas de Markdown.
    3. CÓDIGO Y COMANDOS: Si aparecen fragmentos de código, comandos de consola o especificaciones de software, recréalos ÍNTEGRAMENTE en bloques de código markdown con su sintaxis correspondiente.
    4. FÓRMULAS Y SÍMBOLOS: Transcribe íntegramente las fórmulas matemáticas, ecuaciones y símbolos especiales sin omitir ningún operando.
    5. ELEMENTOS VISUALES: Si se describen imágenes, diagramas de flujo o esquemas, genera una descripción objetiva y detallada del diagrama para que no se pierda la información explicativa asociada.

    REGLAS ESTRICTAS:
    - MANTÉN la fidelidad del texto original al 100%.
    - PROHIBIDO agregar comentarios, anotaciones de estudio o resúmenes de nivel conceptual.
    - Escribe en español con excelente ortografía."""
    
    TYPE_TO_API_INDEX = {
        "basic": 1, "multiple_choice": 2, "cloze": 3, "vocabulary": 4,
        "level_1_cloze": 1, "level_2_relations": 2, "level_3_application": 3, "level_4_analysis": 4,
        "atomic_extraction": 1, "high_performance_architect": 1, "exam_pareto": 1, "exam_faithful": 1,
        "forensic_analyst": 1, "environment_architect": 2, "speedrun_trainer": 3
    }

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, 
                 config_set: Optional[Dict] = None):
        self.log_callback = log_callback or print
        self.config_set = config_set or {}
        
        # Cargar llaves y modelos desde entorno
        self.api_keys = self._load_api_keys_pool()
        self.models_pool = self._load_models_pool()
        
        self.exhausted_keys = set()
        self.active_types = self.config_set.get("active_types", {"basic": True, "multiple_choice": True, "cloze": True, "vocabulary": True})
        
        # QYI Components
        self.qyi_evaluator = QYIEvaluator()
        self.kg_ranker = EduKGRanker()
        self.last_evaluation_metrics = {}

    @property
    def model_name(self) -> str:
        """Retorna el primer modelo del pool (para logs y compatibilidad)."""
        return self.models_pool[0] if self.models_pool else "gemini-1.5-flash"

    def _load_api_keys_pool(self) -> List[str]:
        """Carga un pool de llaves API desde GEMINI_API_KEY (separadas por coma)."""
        kstr = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEYS_1") # Fallback a v1
        if not kstr:
            # Intentar recolectar de GEMINI_API_KEY_1..4 para compatibilidad
            all_keys = []
            for i in range(1, 5):
                k = os.getenv(f"GEMINI_API_KEY_{i}") or os.getenv(f"GEMINI_API_KEYS_{i}")
                if k: all_keys.extend([x.strip() for x in k.split(",") if x.strip()])
            return all_keys
        return [k.strip() for k in kstr.split(",") if k.strip()]

    def _load_models_pool(self) -> List[str]:
        """Carga un pool de modelos desde GEMINI_MODEL (separados por coma)."""
        mstr = os.getenv("GEMINI_MODEL") or "gemini-1.5-flash"
        # Limpiar posibles puntos finales o espacios extra de cada modelo
        return [m.strip().strip(".") for m in mstr.split(",") if m.strip()]

    def _log(self, msg: str):
        if self.log_callback: self.log_callback(msg)

    def _is_content_sufficient(self, text: str) -> bool:
        return len(text.strip()) >= MIN_CONTENT_CHARS

    def _check_internet_connection(self, host="8.8.8.8", port=53, timeout=3) -> bool:
        """Verifica si hay una conexión de red activa."""
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except Exception:
            try:
                socket.gethostbyname("generativelanguage.googleapis.com")
                return True
            except Exception:
                return False

    def _wait_for_connection(self, reason="operación de red"):
        """Pausa la ejecución si no hay conexión a internet y espera hasta que regrese."""
        if not self._check_internet_connection():
            self._log(f"\n⚠️ [RED] Sin conexión a internet ({reason}). Pausando y esperando reconexión...")
            while not self._check_internet_connection():
                time.sleep(5)
            self._log("✅ [RED] Conexión a internet restablecida. Continuando con la tarea...\n")

    def _upload_file_with_retry(self, file_path: str, max_retries: int = 5, initial_delay: float = 2.0):
        """Sube un archivo a Gemini con reintentos para fallas de red e internet persistente."""
        last_exception = None
        delay = initial_delay
        attempt = 0
        
        while attempt < max_retries:
            self._wait_for_connection(reason="subida de archivo multimodal")
            
            try:
                return genai.upload_file(file_path)
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                
                # Detectar errores de conexión o lectura/timeout
                is_connection_error = any(msg in error_str for msg in [
                    "connection", "10054", "reset", "broken pipe", "timeout", "network", "dns", "unreachable", "host", "read operation timed out"
                ])
                
                if is_connection_error:
                    if not self._check_internet_connection():
                        self._wait_for_connection(reason="reintento de subida tras desconexión")
                        self._log(f"   🔄 Reintentando subida de archivo tras restaurarse la red...")
                        delay = initial_delay  # Reset delay
                        continue
                    
                    remaining = max_retries - attempt - 1
                    if remaining > 0:
                        self._log(f"   ⚠️ Error de conexión/lectura al subir ({e}). Reintentando en {delay}s... ({remaining} intentos restantes)")
                        time.sleep(delay)
                        delay *= 2  # Backoff exponencial
                        attempt += 1
                        continue
                
                self._log(f"   ❌ Error crítico subiendo a Gemini: {e}")
                raise e
        
        raise last_exception

    def _get_file_with_retry(self, file_name: str, max_retries: int = 5, initial_delay: float = 2.0):
        """Obtiene el estado de un archivo en Gemini con reintentos para fallas de red."""
        last_exception = None
        delay = initial_delay
        attempt = 0
        
        while attempt < max_retries:
            self._wait_for_connection(reason="verificación de archivo multimodal")
            
            try:
                return genai.get_file(file_name)
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                
                is_connection_error = any(msg in error_str for msg in [
                    "connection", "10054", "reset", "broken pipe", "timeout", "network", "dns", "unreachable", "host", "read operation timed out"
                ])
                
                if is_connection_error:
                    if not self._check_internet_connection():
                        self._wait_for_connection(reason="reintento de verificación tras desconexión")
                        delay = initial_delay
                        continue
                    
                    remaining = max_retries - attempt - 1
                    if remaining > 0:
                        self._log(f"   ⚠️ Error de conexión/lectura al verificar ({e}). Reintentando en {delay}s... ({remaining} intentos restantes)")
                        time.sleep(delay)
                        delay *= 2
                        attempt += 1
                        continue
                
                self._log(f"   ❌ Error crítico verificando archivo en Gemini: {e}")
                raise e
        
        raise last_exception

    def generate_raw_response(self, prompt: str, api_index: int = 1, files: List[Any] = None, temperature: Optional[float] = None) -> str:
        """
        Llamada robusta a Gemini con failover automático entre modelos y llaves.
        Ignora api_index en favor del pool global secuencial.
        """
        if not self.api_keys:
            raise Exception("No hay llaves GEMINI_API_KEY configuradas en el entorno.")

        errors = []
        # Intentar con cada modelo del pool
        for model_name in self.models_pool:
            # Para cada modelo, intentar con las llaves disponibles (que no estén marcadas como agotadas este turno)
            available_keys = [k for k in self.api_keys if k not in self.exhausted_keys]
            
            if not available_keys:
                self._log("⚠️ Todas las llaves están agotadas. Reintentando con el pool completo...")
                self.exhausted_keys.clear()
                available_keys = self.api_keys

            for key in available_keys:
                while True:
                    # Nos aseguramos de tener internet antes de intentar la llamada
                    self._wait_for_connection(reason=f"generar respuesta con {model_name}")
                    
                    try:
                        genai.configure(api_key=key)
                        model = genai.GenerativeModel(model_name)
                        
                        content = [prompt]
                        if files: content.extend(files)
                        
                        config_dict = {}
                        if temperature is not None:
                            config_dict["temperature"] = temperature
                            
                        response = model.generate_content(content, generation_config=config_dict if config_dict else None)
                        return response.text
                    except Exception as e:
                        err_msg = str(e)
                        err_msg_lower = err_msg.lower()
                        
                        # Detectar problemas de conexión a internet
                        is_connection_error = any(msg in err_msg_lower for msg in [
                            "connection", "10054", "reset", "broken pipe", "timeout", "network", "dns", "unreachable", "host"
                        ])
                        
                        if is_connection_error:
                            if not self._check_internet_connection():
                                self._log(f"⚠️ Error de conexión de red durante llamada a Gemini: {err_msg}. Esperando reconexión...")
                                self._wait_for_connection(reason="reintento de llamada tras desconexión")
                                self._log("🔄 Reintentando llamada con el mismo modelo y llave...")
                                continue  # Reintentar en el bucle True
                        
                        if "429" in err_msg or "quota" in err_msg_lower:
                            self._log(f"⚠️ Cuota agotada para llave (...{key[-4:]}) con modelo {model_name}. Rotando...")
                            self.exhausted_keys.add(key)
                        else:
                            self._log(f"❌ Error con modelo {model_name}: {err_msg}")
                            errors.append(f"{model_name}: {err_msg}")
                        break  # Salir del bucle de reintento para rotar a la siguiente llave/modelo

        raise Exception(f"No se pudo obtener respuesta de Gemini tras agotar el pool: {'; '.join(errors)}")

    # --- QYI PIPELINE ---
    
    def extract_concepts(self, text: str) -> List[str]:
        prompt = f"Extrae los 15 conceptos técnicos clave de este texto (solo nombres separados por comas):\n{text[:4000]}"
        try:
            res = self.generate_raw_response(prompt, temperature=0.1)
            return [c.strip() for c in res.split(",") if c.strip()]
        except: return []

    def run_qyi_evaluation(self, source_text: str, flashcards: List[Dict[str, str]]) -> Dict[str, Any]:
        if not flashcards: return {"qyi": 0.0}
        self._log("\n🧪 EVALUACIÓN QYI...")
        
        concepts = self.extract_concepts(source_text)
        edges = self._extract_concept_relations_via_llm(concepts, source_text)
        self.kg_ranker.build_graph(concepts, source_text, edges=edges)
        pagerank = self.kg_ranker.calculate_pagerank()
        
        # Calcular umbral dinámico para Y_i (percentil 60)
        all_pr_values = list(pagerank.values())
        pr_threshold = float(np.percentile(all_pr_values, 60)) if all_pr_values else 0.0
        
        evals = self._watchdog_evaluate(source_text, flashcards)
        
        qualities = []
        is_high = []
        card_concepts = []
        
        for idx, card in enumerate(flashcards):
            # Encontrar la evaluación correspondiente
            eval_data = next((e for e in evals if e.get('original_id') == idx), None)
            calidad = eval_data.get('calidad', 7) if eval_data else 7
            bloom = int(eval_data.get('bloom', 2)) if eval_data else 2
            matched_concept = eval_data.get('concepto', 'general').strip().lower() if eval_data else 'general'
            
            pr_val = pagerank.get(matched_concept, 0.0)
            is_yield = (pr_val >= pr_threshold) and (bloom >= 2)
            
            qualities.append(calidad / 10.0)
            is_high.append(is_yield)
            card_concepts.append(matched_concept)
            
        metrics = self.qyi_evaluator.calculate_qyi(qualities, is_high, pagerank, card_concepts)
        self.last_evaluation_metrics = metrics
        self._log(f"✅ QYI: {metrics['qyi']:.2f} | Φ_Q: {metrics['phi_q']:.2f} | Φ_Y: {metrics['phi_y']:.2f} | Φ_C: {metrics['phi_c']:.2f}")
        return metrics

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
            res = self.generate_raw_response(prompt, temperature=0.1)
            match = re.search(r'\{.*\}', res, re.DOTALL)
            if match:
                data = json.loads(match.group())
                raw_edges = data.get('edges', [])
                valid_concepts = set(c.lower().strip() for c in concepts)
                for edge in raw_edges:
                    u = edge.get('from', '').strip().lower()
                    v = edge.get('to', '').strip().lower()
                    if u and v and u in valid_concepts and v in valid_concepts:
                        edges.append((u, v))
            else:
                self._log("⚠️ No se pudo encontrar el JSON de relaciones en la respuesta.")
        except Exception as e:
            self._log(f"⚠️ Error al extraer relaciones semánticas vía LLM: {e}")
            
        return edges

    def _watchdog_evaluate(self, text: str, cards: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        batch_size = 10
        all_evals = []
        total_cards = len(cards)
        
        for batch_idx in range(0, total_cards, batch_size):
            batch = cards[batch_idx:batch_idx + batch_size]
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
                prompt += f"ID:{idx} | P: {c.get('front', c.get('P', ''))[:120]} | R: {c.get('back', c.get('R', ''))[:120]}\n"
                
            prompt += (
                "\nResponde ÚNICAMENTE con un arreglo JSON en este formato:\n"
                '[{"id": 0, "calidad": 8, "bloom": 2, "impacto": "S", "concepto": "triada CIA", "explicacion": "Explicación corta"}, ...]\n'
                "No agregues texto introductorio o de cierre fuera del JSON."
            )
            
            try:
                res = self.generate_raw_response(prompt, temperature=0.1)
                match = re.search(r'\[.*\]', res, re.DOTALL)
                if match:
                    batch_evals = json.loads(match.group())
                    for e in batch_evals:
                        e['original_id'] = batch_idx + e['id']
                        concept_val = e.get('concepto', 'general').strip().lower()
                        if not concept_val or concept_val in ["general", "varios", "pregunta"]:
                            txt = (batch[e['id']].get('front', batch[e['id']].get('P', '')) + 
                                   batch[e['id']].get('back', batch[e['id']].get('R', ''))).lower()
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
                    txt = (card.get('front', card.get('P', '')) + card.get('back', card.get('R', ''))).lower()
                    words = re.findall(r'\b\w{4,}\b', txt)
                    fallback_concept = words[0] if words else "general"
                    all_evals.append({
                        "original_id": batch_idx + idx,
                        "calidad": 7,
                        "bloom": 2,
                        "impacto": "N",
                        "concepto": fallback_concept,
                        "explicacion": f"Fallo al procesar rúbrica IA: {e}"
                    })
        return all_evals

    # --- MODALIDADES DE PROCESAMIENTO ---

    def process_all_sections(self, sections: List[Dict], converter, anki_manager, 
                             bisabuelo_str: str, grandparent_str: str, 
                             progress_callback: Optional[Callable] = None,
                             session_path: Optional[str] = None) -> List[Dict]:
        """Procesa múltiples secciones de imágenes de forma secuencial."""
        results = []
        total = len(sections)

        # Carpeta para transcripciones OCR
        if session_path:
            os.makedirs(os.path.join(session_path, "ocr_transcripts"), exist_ok=True)
            os.makedirs(os.path.join(session_path, "flashcards"), exist_ok=True)

        for i, sec_data in enumerate(sections, 1):
            title = sec_data["title"]
            image_paths = sec_data["image_paths"]

            if progress_callback:
                progress_callback(title, i, total)

            self._log(f"\n{'='*50}")
            self._log(f"📦 PROCESANDO SECCIÓN {i}/{total}: {title}")
            self._log(f"{'='*50}")

            # 1. OCR
            text = self.extract_text_from_images(image_paths)
            if not text:
                self._log(f"⚠️ No se pudo extraer texto de {title}")
                results.append({"section": title, "success": False, "error": "OCR Fail"})
                continue

            # Guardar transcripción OCR
            if session_path:
                self._save_ocr_transcript(text, session_path, title)

            # 2. Generación
            self._log(f"✨ Generando flashcards para {title}...")
            gen_results = self.generate_all_flashcards_sequential(text)

            section_res = {
                "section": title,
                "success": True,
                "results": {},
                "qyi_metrics": self.last_evaluation_metrics
            }

            # 3. Procesar resultados de cada tipo
            for card_type, res in gen_results.items():
                if res.get("success"):
                    raw_content = res.get("content", "")
                    # Convertir a TSV
                    tsv_content = converter.convert(raw_content, card_type)
                    # Parsear para el interface
                    flashcards = self._parse_tsv_to_flashcards(tsv_content)

                    if flashcards:
                        # Guardar flashcards generadas
                        if session_path:
                            self._save_flashcards_tsv(tsv_content, session_path, title, card_type)

                        # Determinar deck name
                        deck = f"{bisabuelo_str}::{grandparent_str}::{title}" if bisabuelo_str else f"{grandparent_str}::{title}"

                        section_res["results"][card_type] = {
                            "success": True,
                            "count": len(flashcards),
                            "flashcards": flashcards,
                            "deck": deck
                        }
                    else:
                        section_res["results"][card_type] = {"success": False, "error": "No flashcards parsed"}
                else:
                    section_res["results"][card_type] = {"success": False, "error": res.get("error")}

            results.append(section_res)

            # Espera entre secciones si no es la última
            if i < total:
                wait_time = self.config_set.get("wait_time", 60)
                self._log(f"⌛ Esperando {wait_time} segundos para evitar límites de API...")
                time.sleep(wait_time)

        return results

    def process_section(self, title: str, images: List[str], converter, anki, deck: str) -> Dict[str, Any]:
        """Procesamiento de IMÁGENES (Individual)."""
        text = self.extract_text_from_images(images)
        if not text: return {"success": False}

        results = self.generate_all_flashcards_parallel(text)
        all_cards = []
        final_res = {}

        for t, r in results.items():
            if r.get("success"):
                cards = self._parse_tsv(converter.convert(r["content"], t))
                all_cards.extend(cards)
                final_res[t] = {"success": True, "flashcards": cards}

        # self.run_qyi_evaluation(text, all_cards)
        return {"success": True, "results": final_res, "qyi_metrics": getattr(self, 'last_evaluation_metrics', {})}

    def process_video_section(self, section_title: str, transcription_paths: List[str], 
                            converter, anki_manager, deck_prefix: str,
                            session_path: Optional[str] = None,
                            full_context: str = "") -> Dict[str, Any]:
        """Procesa una sección de video (basada en transcripciones existentes)."""
        # Unir todas las transcripciones de la sección
        full_text = ""
        for tp in transcription_paths:
            if os.path.exists(tp):
                with open(tp, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Limpiar headers de Whisper si existen
                    lines = [l for l in content.split('\n') if not l.startswith('#')]
                    full_text += "\n" + "\n".join(lines).strip()

        if not full_text.strip():
            return {"success": False, "error": "No text content found"}

        # Adjuntar fuente de consulta si existe
        text_to_process = full_text
        if full_context:
            text_to_process = f"CONTEXTO DE REFERENCIA:\n{full_context}\n\n---\n\nCONTENIDO A PROCESAR:\n{full_text}"

        # Generar flashcards
        gen_results = self.generate_all_flashcards_sequential(text_to_process)

        section_res = {
            "success": True,
            "results": {},
            "qyi_metrics": self.last_evaluation_metrics
        }

        # Procesar resultados
        for card_type, res in gen_results.items():
            if res.get("success"):
                raw_content = res.get("content", "")
                tsv_content = converter.convert(raw_content, card_type)
                flashcards = self._parse_tsv_to_flashcards(tsv_content)

                if flashcards:
                    if session_path:
                        self._save_flashcards_tsv(tsv_content, session_path, section_title, card_type)

                    section_res["results"][card_type] = {
                        "success": True,
                        "count": len(flashcards),
                        "flashcards": flashcards,
                        "deck": f"{deck_prefix}::{card_type}"
                    }
                else:
                    section_res["results"][card_type] = {"success": False, "error": "No flashcards parsed"}
            else:
                section_res["results"][card_type] = {"success": False, "error": res.get("error")}

        return section_res

    def process_video_section_multimodal(self, section_title: str, video_paths: List[str], 
                                       converter, anki_manager, deck_prefix: str,
                                       session_path: Optional[str] = None,
                                       full_context: str = "") -> Dict[str, Any]:
        """Procesamiento MULTIMODAL de VIDEO (Directo a Gemini)."""
        self._log(f"🎬 Subiendo video(s) para análisis multimodal: {video_paths}")

        # Intentar con las llaves disponibles
        for key in self.api_keys:
            if key in self.exhausted_keys: continue

            try:
                genai.configure(api_key=key)
                uploaded_files = []
                for vp in video_paths:
                    if not os.path.exists(vp): continue
                    f = self._upload_file_with_retry(vp)
                    while f.state.name == "PROCESSING": 
                        time.sleep(5)
                        f = self._get_file_with_retry(f.name)
                    uploaded_files.append(f)

                if not uploaded_files:
                    return {"success": False, "error": "No files uploaded"}

                final_results = {"success": True, "results": {}}
                all_cards_for_qyi = []

                for t, active in self.active_types.items():
                    if not active: continue

                    base_prompt = self.config_set.get("prompts", {}).get(t, DEFAULT_PROMPTS.get(t, ""))
                    prompt = base_prompt
                    if full_context:
                        prompt = f"CONTEXTO DE REFERENCIA:\n{full_context}\n\n---\n\n{base_prompt}"

                    # Usar el método robusto para generar la respuesta
                    res_text = self.generate_raw_response(prompt.format(texto_ocr="CONTENIDO MULTIMODAL"), files=uploaded_files)

                    tsv_content = converter.convert(res_text, t)
                    flashcards = self._parse_tsv_to_flashcards(tsv_content)

                    if flashcards:
                        if session_path:
                            self._save_flashcards_tsv(tsv_content, session_path, section_title, f"{t}_multimodal")

                        final_results["results"][t] = {
                            "success": True,
                            "count": len(flashcards),
                            "flashcards": flashcards,
                            "deck": f"{deck_prefix}::{t}"
                        }
                        all_cards_for_qyi.extend(flashcards)

                # Cleanup
                for f in uploaded_files:
                    try:
                        f.delete()
                    except Exception as cleanup_err:
                        self._log(f"⚠️ Advertencia: No se pudo eliminar el archivo subido {f.name}: {cleanup_err}")

                # QYI (desactivado en medio de la generación para evitar bloqueos)
                # self.run_qyi_evaluation(f"Multimodal Video Context: {section_title}", all_cards_for_qyi)
                final_results["qyi_metrics"] = getattr(self, 'last_evaluation_metrics', {})

                return final_results
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    self.exhausted_keys.add(key)
                    self._log(f"⚠️ Cuota agotada para llave en multimodal. Rotando...")
                    continue
                self._log(f"❌ Error Multimodal: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "All API keys exhausted for multimodal processing"}
    # --- HELPERS ---

    def _save_ocr_transcript(self, text: str, session_path: str, title: str, subfolder: str = "ocr_transcripts"):
        folder = os.path.join(session_path, subfolder)
        os.makedirs(folder, exist_ok=True)
        safe_title = _safe_filename(title)
        path = os.path.join(folder, f"{safe_title}.txt")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
        except Exception as e:
            self._log(f"⚠️ Error guardando transcripción: {e}")

    def _save_flashcards_tsv(self, tsv: str, session_path: str, title: str, card_type: str):
        folder = os.path.join(session_path, "flashcards")
        os.makedirs(folder, exist_ok=True)
        safe_title = _safe_filename(title)
        path = os.path.join(folder, f"{safe_title}_{card_type}.txt")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(tsv)
        except: pass

    def _parse_tsv_to_flashcards(self, tsv: str) -> List[Dict[str, str]]:
        cards = []
        for line in tsv.strip().split('\n'):
            parts = line.split('\t')
            if len(parts) >= 2:
                cards.append({"front": parts[0].strip(), "back": parts[1].strip()})
        return cards

    def extract_text_from_images(self, paths: List[str]) -> str:
        """OCR multimodal de imágenes con failover de llaves."""
        self._log(f"📸 OCR en {len(paths)} imágenes...")
        
        # Intentar con cada modelo y llave disponible
        for model_name in self.models_pool:
            for key in self.api_keys:
                if key in self.exhausted_keys: continue
                
                try:
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel(model_name)
                    imgs = [Image.open(p) for p in paths]
                    res = model.generate_content([self.OCR_PROMPT] + imgs)
                    return res.text
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower():
                        self.exhausted_keys.add(key)
                        continue
                    self._log(f"⚠️ OCR Fail con modelo {model_name} y llave (...{key[-4:]}): {e}")
        
        return ""

    def generate_all_flashcards_parallel(self, text: str) -> Dict[str, Any]:
        results = {}
        all_cards_for_qyi = []
        for t, active in self.active_types.items():
            if active:
                prompt = self.config_set.get("prompts", {}).get(t, DEFAULT_PROMPTS.get(t, ""))
                try:
                    # Usar replace en lugar de format para evitar errores con llaves extra en los prompts
                    full_prompt = prompt.replace("{texto_ocr}", text)
                    res = self.generate_raw_response(full_prompt, self.TYPE_TO_API_INDEX.get(t, 1))
                    results[t] = {"success": True, "content": res}
                    # Colectar para QYI
                    cards = self._parse_tsv(res) # Intento de parseo rápido
                    all_cards_for_qyi.extend(cards)
                except Exception as e:
                    self._log(f"❌ Error al generar tipo '{t}': {e}")
                    results[t] = {"success": False, "error": str(e)}

        # if all_cards_for_qyi:
        #     self.run_qyi_evaluation(text, all_cards_for_qyi)

        return results

    def generate_all_flashcards_sequential(self, text: str) -> Dict[str, Any]:
        """Alias para parallel con evaluación QYI integrada."""
        return self.generate_all_flashcards_parallel(text)

    def _parse_tsv(self, tsv: str) -> List[Dict[str, str]]:
        # Alias para compatibilidad
        return self._parse_tsv_to_flashcards(tsv)

    def reset_exhausted_keys(self):
        self.exhausted_keys.clear()

    def update_config(self, config: Dict):
        self.config_set = config
        self.active_types = config.get("active_types", self.active_types)
        # El pool de modelos ahora es dinámico desde el entorno
    def check_api_connection(self, api_index: int = 1) -> bool:
        """Verifica la conexión con una API de Gemini utilizando la pool de llaves."""
        label = f"API {api_index}"
        try:
            if not self.api_keys:
                self._log("❌ No se encontraron llaves API en la pool")
                return False
            
            idx = api_index - 1
            if idx < len(self.api_keys):
                key = self.api_keys[idx]
            else:
                key = self.api_keys[0]
                label = f"API {api_index} (Reutilizando principal)"
            
            genai.configure(api_key=key)
            models = list(genai.list_models())
            self._log(f"✅ {label} conectada correctamente")
            return True
        except Exception as e:
            self._log(f"❌ {label} falló: {e}")
            return False

    def check_all_apis(self) -> Dict[str, bool]:
        """Verifica todas las APIs (1 a 4)."""
        status = {}
        for i in range(1, 5):
            status[f"API {i}"] = self.check_api_connection(i)
        return status

    def extract_text_from_pdf_file(self, pdf_path: str, extraction_mode: int = 1) -> str:
        """Extrae texto de un archivo PDF usando PyMuPDF o Vision OCR."""
        self._log(f"📄 Extrayendo texto de PDF: {os.path.basename(pdf_path)} (Modo {extraction_mode})...")
        try:
            import fitz
            doc = fitz.open(pdf_path)
            text_list = []
            for page in doc:
                text_list.append(page.get_text())
            doc.close()
            full_text = "\n".join(text_list).strip()
            
            # Si el texto es muy corto o modo es 2, intentamos usar OCR multimodal de Gemini
            if len(full_text) < 100 or extraction_mode == 2:
                self._log("⚠️ Poco texto o modo estructurado. Renderizando páginas a imágenes para OCR...")
                import tempfile
                with tempfile.TemporaryDirectory() as tmpdir:
                    doc = fitz.open(pdf_path)
                    image_paths = []
                    for page_num in range(len(doc)):
                        page = doc.load_page(page_num)
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        img_path = os.path.join(tmpdir, f"page_{page_num}.png")
                        pix.save(img_path)
                        image_paths.append(img_path)
                    doc.close()
                    full_text = self.extract_text_from_images(image_paths)
            
            return full_text
        except Exception as e:
            self._log(f"❌ Error al extraer texto del PDF: {e}")
            return ""

    def transcribe_content_faithful(self, text: str) -> str:
        """Transcribe de forma 100% fiel el contenido de un libro/documento."""
        self._log("🔊 Transcribiendo contenido de forma 100% fiel con Gemini...")
        prompt = f"{self.FAITHFUL_BOOK_PROMPT}\n\nCONTENIDO A TRANSCRIBIR:\n{text}"
        try:
            return self.generate_raw_response(prompt)
        except Exception as e:
            self._log(f"❌ Error en transcripción fiel: {e}")
            return text

    def structure_content_expert(self, text: str) -> str:
        """Optimiza y estructura el texto en apuntes de estudio exhaustivos."""
        self._log("✨ Optimizando apuntes expertos con Gemini...")
        prompt = (
            "Actúa como un profesor y estudiante brillante. Toma el siguiente texto de estudio y "
            "estructúralo en apuntes Markdown limpios, legibles, completos y exhaustivos. "
            "No resumas de forma destructiva; conserva todos los detalles técnicos, definiciones, "
            "fórmulas, código y tablas. Devuelve solo el Markdown estructurado.\n\n"
            f"TEXTO A ESTRUCTURAR:\n{text}"
        )
        try:
            return self.generate_raw_response(prompt)
        except Exception as e:
            self._log(f"❌ Error estructurando apuntes expertos: {e}")
            return text

    def analyze_book_semantic_sections(self, text_with_markers: str, total_pages: int) -> List[Dict[str, Any]]:
        """Identifica rangos semánticos (capítulos o temas) en un libro usando Gemini."""
        self._log("🧠 Analizando estructura semántica del libro con Gemini...")
        prompt = (
            "Analiza el siguiente texto de un libro que contiene marcadores de página (por ejemplo, '--- PÁGINA X ---'). "
            "Tu tarea es identificar las secciones o capítulos principales del libro y devolverlos en un formato JSON estructurado. "
            "Para cada sección, debes proporcionar un título descriptivo ('title') y el rango de páginas correspondiente: "
            "el número de página de inicio ('start_page', entero) y el número de página de fin ('end_page', entero). "
            "Asegúrate de cubrir todo el rango del libro desde la página 1 hasta la página final. "
            "No agregues texto explicativo, responde ÚNICAMENTE con una lista JSON válida de objetos con el formato:\n"
            '[{"title": "Nombre de la Sección", "start_page": 1, "end_page": 10}, ...]\n\n'
            f"TOTAL PÁGINAS: {total_pages}\n\n"
            f"TEXTO CON MARCADORES (Muestra):\n{text_with_markers[:8000]}"
        )
        try:
            res = self.generate_raw_response(prompt)
            match = re.search(r'\[.*\]', res, re.DOTALL)
            if match:
                sections = json.loads(match.group())
                for sec in sections:
                    start = sec.get("start_page", 1)
                    end = sec.get("end_page", start)
                    sec["pages"] = list(range(start, end + 1))
                return sections
        except Exception as e:
            self._log(f"❌ Error analizando secciones semánticas: {e}")
        return []

    def generate_all_flashcards_multimodal(self, pdf_segment_path: str, extraction_mode: int = 2) -> Dict[str, Any]:
        """Genera flashcards directamente a partir de un fragmento de PDF."""
        self._log(f"🎬 Generando flashcards multimodales directas de PDF: {os.path.basename(pdf_segment_path)} (Extracción: {extraction_mode})")
        try:
            text = self.extract_text_from_pdf_file(pdf_segment_path, extraction_mode=extraction_mode)
            if not text:
                return {"success": False, "error": "No se pudo extraer texto del PDF para generación"}
            results = self.generate_all_flashcards_parallel(text)
            if isinstance(results, dict):
                results["_extracted_text"] = text
            return results
        except Exception as e:
            self._log(f"❌ Error en generación multimodal de PDF: {e}")
            return {}
