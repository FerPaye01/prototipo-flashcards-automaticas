"""
Generador de Flashcards usando Gemini API.
Procesa imágenes, video, audio y PDF para generar flashcards pedagógicas de alta calidad (QYI).
"""

import os
import threading
import time
import json
import re
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image
from config_sets_manager import (DEFAULT_PROMPTS, DEFAULT_PROMPTS2, DEFAULT_PROMPTS3,
                                 DEFAULT_PROMPTS4, DEFAULT_PROMPTS5, DEFAULT_PROMPTS6,
                                 SOURCE_CONTEXT_INSTRUCTION)
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

class GeminiFlashcardGenerator:
    """Generador avanzado con soporte Multimodal y Evaluación QYI."""
    
    OCR_PROMPT = """Actúa como un excelente estudiante universitario especializado, elaborando material de estudio integral basado en las IMÁGENES proporcionadas. 
    Tu instrucción ESTRICTA es integrar y consolidar paso a paso todo el conocimiento visual (diapositivas, tablas, esquemas, ejemplos en pantalla) que aparezca a lo largo de las imágenes, en conjunto cronológico con el texto que logres identificar.
    Debes añadir observaciones y apuntes complementarios como un estudiante brillante resaltando lo relevante del contenido, todo con la mejor ortografía y puntuación posibles en español.
    ESTÁ ESTRICTAMENTE PROHIBIDO SIMPLIFICAR O RESUMIR; no debes perder información sin importar qué tan largo sea el texto. Debes recuperar hasta el último detalle técnico válido.
    ADICIONALMENTE: Si detectas fragmentos de CÓDIGO o ESPECIFICACIONES TÉCNICAS, debes recrearlos ÍNTEGRAMENTE sin modificar ni una sola línea de sintaxis. Si es una tabla, reconsrúyela en formato Markdown.
    Devuelve solo el texto extraído y enriquecido, estructurado en Markdown limpio."""
    
    TYPE_TO_API_INDEX = {
        "basic": 1, "multiple_choice": 2, "cloze": 3, "vocabulary": 4,
        "level_1_cloze": 1, "level_2_relations": 2, "level_3_application": 3, "level_4_analysis": 4,
        "atomic_extraction": 1, "high_performance_architect": 1, "exam_pareto": 1, "exam_faithful": 1
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

    def generate_raw_response(self, prompt: str, api_index: int = 1, files: List[Any] = None) -> str:
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
                try:
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel(model_name)
                    
                    content = [prompt]
                    if files: content.extend(files)
                    
                    response = model.generate_content(content)
                    return response.text
                except Exception as e:
                    err_msg = str(e)
                    if "429" in err_msg or "quota" in err_msg.lower():
                        self._log(f"⚠️ Cuota agotada para llave (...{key[-4:]}) con modelo {model_name}. Rotando...")
                        self.exhausted_keys.add(key)
                    else:
                        self._log(f"❌ Error con modelo {model_name}: {err_msg}")
                        errors.append(f"{model_name}: {err_msg}")
                    continue # Probar siguiente llave/modelo

        raise Exception(f"No se pudo obtener respuesta de Gemini tras agotar el pool: {'; '.join(errors)}")

    # --- QYI PIPELINE ---
    
    def extract_concepts(self, text: str) -> List[str]:
        prompt = f"Extrae los 15 conceptos técnicos clave de este texto (solo nombres separados por comas):\n{text[:4000]}"
        try:
            res = self.generate_raw_response(prompt)
            return [c.strip() for c in res.split(",") if c.strip()]
        except: return []

    def run_qyi_evaluation(self, source_text: str, flashcards: List[Dict[str, str]]) -> Dict[str, Any]:
        if not flashcards: return {"qyi": 0.0}
        self._log("\n🧪 EVALUACIÓN QYI...")
        
        concepts = self.extract_concepts(source_text)
        self.kg_ranker.build_graph(concepts, source_text)
        pagerank = self.kg_ranker.calculate_pagerank()
        
        evals = self._watchdog_evaluate(source_text, flashcards)
        qualities = [e.get('calidad', 7)/10.0 for e in evals]
        is_high = [e.get('impacto', 'N') == 'S' for e in evals]
        
        card_concepts = []
        for c in flashcards:
            txt = (c.get('front','') + c.get('P','')).lower()
            card_concepts.append(next((cp for cp in concepts if cp.lower() in txt), "general"))
            
        metrics = self.qyi_evaluator.calculate_qyi(qualities, is_high, pagerank, card_concepts)
        self.last_evaluation_metrics = metrics
        self._log(f"✅ QYI: {metrics['qyi']:.2f} | Φ_Q: {metrics['phi_q']:.2f} | Φ_Y: {metrics['phi_y']:.2f} | Φ_C: {metrics['phi_c']:.2f}")
        return metrics

    def _watchdog_evaluate(self, text: str, cards: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        prompt = f"Evalúa estas flashcards (Calidad 0-10, Impacto S/N). Texto ref: {text[:1000]}\nCards:\n"
        for i, c in enumerate(cards):
            prompt += f"ID:{i} P:{c.get('front', c.get('P',''))[:100]}\n"
        prompt += "\nResponde JSON: [{\"id\":0, \"calidad\":8, \"impacto\":\"S\"}, ...]"
        try:
            res = self.generate_raw_response(prompt)
            match = re.search(r'\[.*\]', res, re.DOTALL)
            return json.loads(match.group()) if match else []
        except: return []

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

        self.run_qyi_evaluation(text, all_cards)
        return {"success": True, "results": final_res, "qyi_metrics": self.last_evaluation_metrics}

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
                    f = genai.upload_file(vp)
                    while f.state.name == "PROCESSING": 
                        time.sleep(5)
                        f = genai.get_file(f.name)
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
                for f in uploaded_files: f.delete()

                # QYI
                self.run_qyi_evaluation(f"Multimodal Video Context: {section_title}", all_cards_for_qyi)
                final_results["qyi_metrics"] = self.last_evaluation_metrics

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
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
        path = os.path.join(folder, f"{safe_title}.txt")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
        except Exception as e:
            self._log(f"⚠️ Error guardando transcripción: {e}")

    def _save_flashcards_tsv(self, tsv: str, session_path: str, title: str, card_type: str):
        folder = os.path.join(session_path, "flashcards")
        os.makedirs(folder, exist_ok=True)
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
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
                    results[t] = {"success": False, "error": str(e)}

        if all_cards_for_qyi:
            self.run_qyi_evaluation(text, all_cards_for_qyi)

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
    def check_all_apis(self) -> Dict[str, bool]:
        status = {}
        for i in range(1, 5):
            keys = self.api_keys.get(i, [])
            status[f"API {i}"] = len(keys) > 0
        status["OCR API"] = len(self.ocr_api_keys) > 0
        return status
