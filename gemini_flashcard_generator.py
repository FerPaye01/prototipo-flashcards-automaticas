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
    
    OCR_PROMPT = """Actúa como un excelente estudiante universitario especializado... (ocr logic)"""
    
    TYPE_TO_API_INDEX = {
        "basic": 1, "multiple_choice": 2, "cloze": 3, "vocabulary": 4,
        "level_1_cloze": 1, "level_2_relations": 2, "level_3_application": 3, "level_4_analysis": 4,
        "atomic_extraction": 1, "high_performance_architect": 1, "exam_pareto": 1, "exam_faithful": 1
    }

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, 
                 config_set: Optional[Dict] = None):
        self.log_callback = log_callback or print
        self.config_set = config_set or {}
        self._parse_models()
        self.api_keys = self._load_api_keys()
        self.ocr_api_keys = self._load_ocr_api_keys()
        self.exhausted_keys = set()
        self.active_types = self.config_set.get("active_types", {"basic": True, "multiple_choice": True, "cloze": True, "vocabulary": True})
        
        # QYI Components
        self.qyi_evaluator = QYIEvaluator()
        self.kg_ranker = EduKGRanker()
        self.last_evaluation_metrics = {}

    def _parse_models(self):
        config_model = self.config_set.get("model")
        env_models = [m.strip() for m in (os.getenv("GEMINI_MODEL") or "gemini-1.5-flash").split(",") if m.strip()]
        self.model_name = config_model or (env_models[0] if env_models else "gemini-1.5-flash")
        self.fallback_models = [m for m in env_models if m != self.model_name]

    def _load_api_keys(self) -> Dict[int, List[str]]:
        keys = {}
        for i in range(1, 5):
            kstr = os.getenv(f"GEMINI_API_KEYS_{i}") or os.getenv(f"GEMINI_API_KEY_{i}")
            keys[i] = [k.strip() for k in kstr.split(",") if k.strip()] if kstr else []
        return keys

    def _load_ocr_api_keys(self) -> List[str]:
        kstr = os.getenv("GEMINI_API_KEYS_OCR") or os.getenv("GEMINI_API_KEY_OCR")
        return [k.strip() for k in kstr.split(",") if k.strip()] if kstr else []

    def _log(self, msg: str):
        if self.log_callback: self.log_callback(msg)

    def _is_content_sufficient(self, text: str) -> bool:
        return len(text.strip()) >= MIN_CONTENT_CHARS

    def generate_raw_response(self, prompt: str, api_index: int = 1, files: List[Any] = None) -> str:
        """Llamada base a Gemini con soporte para archivos (multimodal)."""
        keys = self.api_keys.get(api_index, []) or self.ocr_api_keys
        if not keys: raise Exception("No API keys available")
        
        genai.configure(api_key=keys[0])
        model = genai.GenerativeModel(self.model_name)
        
        content = [prompt]
        if files: content.extend(files)
        
        response = model.generate_content(content)
        return response.text

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

    def process_section(self, title: str, images: List[str], converter, anki, deck: str) -> Dict[str, Any]:
        """Procesamiento de IMÁGENES."""
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

    def process_video_section_multimodal(self, title: str, video_paths: List[str], converter, anki, deck: str) -> Dict[str, Any]:
        """Procesamiento MULTIMODAL de VIDEO (Directo a Gemini)."""
        self._log(f"🎬 Subiendo video(s) para análisis multimodal: {video_paths}")
        try:
            genai.configure(api_key=self.ocr_api_keys[0] if self.ocr_api_keys else self.api_keys[1][0])
            uploaded_files = []
            for vp in video_paths:
                f = genai.upload_file(vp)
                while f.state.name == "PROCESSING": time.sleep(5); f = genai.get_file(f.name)
                uploaded_files.append(f)
            
            # Generar contenido directamente desde el video
            all_cards = []
            final_res = {}
            for t, active in self.active_types.items():
                if not active: continue
                prompt = self.config_set.get("prompts", {}).get(t, DEFAULT_PROMPTS.get(t, ""))
                res_text = self.generate_raw_response(prompt, api_index=self.TYPE_TO_API_INDEX.get(t, 1), files=uploaded_files)
                cards = self._parse_tsv(converter.convert(res_text, t))
                all_cards.extend(cards)
                final_res[t] = {"success": True, "flashcards": cards}
            
            for f in uploaded_files: f.delete()
            
            self.run_qyi_evaluation(f"Multimodal Video: {title}", all_cards)
            return {"success": True, "results": final_res, "qyi_metrics": self.last_evaluation_metrics}
        except Exception as e:
            self._log(f"❌ Error Multimodal: {e}")
            return {"success": False, "error": str(e)}

    # --- HELPERS ---

    def extract_text_from_images(self, paths: List[str]) -> str:
        # Lógica OCR simplificada para el ejemplo, pero funcional
        self._log(f"📸 OCR en {len(paths)} imágenes...")
        try:
            genai.configure(api_key=self.ocr_api_keys[0])
            model = genai.GenerativeModel(self.model_name)
            imgs = [Image.open(p) for p in paths]
            res = model.generate_content([self.OCR_PROMPT] + imgs)
            return res.text
        except Exception as e:
            self._log(f"⚠️ OCR Fail: {e}")
            return ""

    def generate_all_flashcards_parallel(self, text: str) -> Dict[str, Any]:
        results = {}
        all_cards_for_qyi = []
        for t, active in self.active_types.items():
            if active:
                prompt = self.config_set.get("prompts", {}).get(t, DEFAULT_PROMPTS.get(t, ""))
                try:
                    res = self.generate_raw_response(prompt.format(texto_ocr=text), self.TYPE_TO_API_INDEX.get(t, 1))
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
        cards = []
        for line in tsv.strip().split('\n'):
            parts = line.split('\t')
            if len(parts) >= 2: cards.append({"front": parts[0], "back": parts[1]})
        return cards

    def check_all_apis(self) -> Dict[str, bool]:
        status = {}
        for i in range(1, 5):
            keys = self.api_keys.get(i, [])
            status[f"API {i}"] = len(keys) > 0
        status["OCR API"] = len(self.ocr_api_keys) > 0
        return status
