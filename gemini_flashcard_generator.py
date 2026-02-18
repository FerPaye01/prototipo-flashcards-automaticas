"""
Generador de Flashcards usando Gemini API.
Procesa imágenes con Gemini Vision para OCR y genera 4 tipos de flashcards en paralelo.
"""

import os
import threading
import time
import json
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image
from config_sets_manager import DEFAULT_PROMPTS, DEFAULT_PROMPTS2

# Tesseract OCR como fallback
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# Cargar variables de entorno
load_dotenv()

# Archivo para flashcards pendientes de importar
PENDING_FLASHCARDS_FILE = "pending_flashcards.json"


class GeminiFlashcardGenerator:
    """Genera flashcards usando 5 APIs de Gemini (1 OCR + 4 flashcards)."""
    
    # Prompt para OCR con Gemini Vision
    OCR_PROMPT = """CONTEXTO IMPORTANTE: Estas son fotografías de mis propios apuntes de clase y notas de estudio personal que he tomado durante mis clases universitarias. Necesito digitalizarlas para crear material de repaso personal.

Rol: Asistente de estudio que ayuda a digitalizar apuntes personales.

Objetivo: Ayúdame a transcribir el contenido de mis apuntes/notas a formato Markdown limpio para poder estudiar mejor.

Instrucciones de Transcripción:
- Texto: Transcribe todo el texto legible de mis notas. Usa encabezados (#, ##) para respetar la jerarquía visual.
- Tablas: Si hay tablas en mis apuntes, conviértelas a formato Markdown estándar (| Col1 | Col2 |).
- Diagramas/Figuras: Si hay diagramas o esquemas que dibujé, describe brevemente qué representan: [DESCRIPCIÓN: diagrama que muestra X].
- Corrección: Si hay palabras cortadas o errores de escritura, corrígelos para que el texto sea legible.

Salida: Únicamente el texto transcrito en Markdown, sin comentarios adicionales."""

    # Prompts para cada tipo de flashcard
    PROMPTS = {
        "basic": """Rol: Asesor experto en pedagogía cognitiva y diseño instruccional, especializado en la deconstrucción de material técnico.

Objetivos: Analizar el [Input_Texto_OCR] y generar un conjunto de flashcards que escalen en profundidad cognitiva (Taxonomía de Bloom). El objetivo es estudiar y comprender el material desde cero, asegurando una cobertura completa del tema seleccionado, forzando el procesamiento algorítmico y la comprensión del sistema, no la memorización de hechos aislados.

Entradas:
Input_Texto_OCR: {texto_ocr}

Generación Cognitiva:
Nivel 1: Declarativa (Recordar/Entender) .- Acción: Genera preguntas que definan o describan los axiomas, conceptos y términos fundamentales presentes en el [Input_Texto_OCR], usando la terminología precisa del texto.

Cláusula de Control de Volumen y Cobertura (MANDATORIO):
*Prioridad de Cobertura: Tu objetivo principal es que yo pueda estudiar el texto completo desde cero. No te limites a una sola tarjeta por nivel. Genera tantas tarjetas de Nivel 1 (Declarativas) como sean necesarias para cubrir todo el vocabulario y hechos nuevos. No omitas información clave por intentar ser breve en la lista.
*Concisión en Respuestas: Aunque la lista de tarjetas sea larga, mantén el campo de "Respuesta" (R:) extremadamente conciso. Usa máximo 1 o 2 oraciones directas por respuesta. Calidad sobre cantidad de texto.
*Integración de Autoría: Si el texto menciona autores, años o estudios específicos (ej: "Según Pérez (2020)..."), inclúyelos explícitamente en la formulación de la pregunta o respuesta para garantizar rigor académico.

Instrucción de Formato de Salida (Estricto): Tu respuesta final debe ser ÚNICAMENTE una lista de texto plano siguiendo este patrón exacto. No uses bloques de código (```), no uses JSON, y no agregues introducciones ni conclusiones.
*Matemáticas: Al escribir operaciones matemáticas, enciérrelas con las etiquetas \\( ... \\) [p. ej., \\( a^2+b^2=c^2 \\)].
*Estructura obligatoria: 
P: [Aquí va el Estímulo / Pregunta] 
R: [Aquí va la Respuesta / Solución / Definición]
(Deja una línea en blanco entre cada par P/R)""",

        "multiple_choice": """Rol: Diseñador Senior de Exámenes de Certificación Técnica y Psicometría.

Objetivos: Generar preguntas de opción múltiple diseñadas para engañar a estudiantes con conocimiento superficial. Los distractores deben ser versiones alteradas de la verdad.

Entradas:
Input_Texto_OCR: {texto_ocr}

Instrucciones de Ingeniería de Distractores (MANDATORIO):
Para cada pregunta, genera 3 distractores usando estas estrategias (NO uses lógica inversa simple):
1. El Espejo Sintáctico: Misma gramática que la correcta, pero cambia una palabra clave técnica.
2. La Invención Plausible: Inventa un término que suene real pero no exista.
3. Verdad Mal Atribuida: Describe un beneficio real de otro concepto del texto, pero atribúyelo incorrectamente a la pregunta actual.

Instrucción de Formato de Salida (Estricto):
Tu respuesta final debe ser ÚNICAMENTE una lista de texto plano.
Estructura obligatoria:
P: [Enunciado de la pregunta]
a) [Opción]
b) [Opción]
c) [Opción]
d) [Opción]
R: [Letra Correcta] - [Breve explicación del porqué]
(Deja una línea en blanco entre cada par P/R)""",

        "cloze": """Rol: Editor de Diseño Instruccional experto en minería de textos.

Objetivos:
Analizar el [Input_Texto_OCR] completo. Tu tarea es identificar los 10-15 conceptos técnicos, datos o definiciones más críticas del texto y convertirlos en tarjetas de memorización "Cloze" (huecos), priorizando la fidelidad al texto original.

Entradas:
Input_Texto_OCR: {texto_ocr}

Reglas de Procesamiento:
Selección Autónoma: Identifica los conceptos clave (términos técnicos, métricas, nombres propios, causas-efectos). Ignora la paja.
Fidelidad: Extrae la oración original donde aparece el concepto. Recorta lo innecesario para que la frase tenga sentido por sí sola, pero no la reescribas.
Lógica de Oclusión (Anki):
Ocultamiento: Encierra el concepto clave con {{{{c1::Concepto::Pista}}}}.
Pista: La pista (después de los dos puntos) es OBLIGATORIA para dar contexto (ej: ::Métrica, ::Algoritmo, ::Fecha).
Listas: Si encuentras una enumeración importante, usa {{{{c1::A}}}}, {{{{c2::B}}}}, {{{{c3::C}}}}.

Instrucción de Formato de Salida (Estricto)
Tu respuesta final debe ser ÚNICAMENTE una lista de texto plano siguiendo este patrón exacto. No uses bloques de código (```), no uses JSON, y no agregues introducciones ni conclusiones.
Estructura obligatoria: 
P: [Aquí va el Estímulo / Pregunta / Oración con huecos / Término] 
R: [Aquí va la Respuesta / Solución / Definición / Contexto]""",

        "vocabulary": """Rol: Profesor de Inglés especializado en detectar terminología interesante en textos técnicos.

Objetivo: Leer el [Input_Texto_OCR] y extraer automáticamente una lista de los términos, verbos o conceptos más "novedosos" o sofisticados. Tu trabajo es crear pares de traducción directa para aprender cómo se dicen estos conceptos en inglés.

Entrada:
Input_Texto_OCR: {texto_ocr}

Reglas de Selección (Criterio de la IA):
Autonomía: Selecciona entre 10 y 15 términos que sean relevantes para el tema del texto.
Nivel: Ignora palabras básicas (como "el", "tener", "casa"). Busca sustantivos técnicos, verbos académicos o conectores lógicos útiles (ej: "trascendental", "estructurales", "atribuido", "función pública").
Formato: Proporciona el término en Inglés y su equivalente exacto en el texto en Español + su fonetico IPA.

Instrucción de Formato de Salida (Estricto)
Tu respuesta final debe ser ÚNICAMENTE una lista de texto plano siguiendo este patrón exacto. No uses bloques de código (```), no uses JSON, y no agregues introducciones ni conclusiones.
Estructura obligatoria: 
P: [Aquí va el Estímulo / Pregunta / Oración con huecos / Término] 
R: [Aquí va la Respuesta / Solución / Definición / Contexto]
(Deja una línea en blanco entre cada par P/R)"""
    }
    
    # Mapeo de tipo a API key
    TYPE_TO_API_INDEX = {
        "basic": 1,
        "multiple_choice": 2,
        "cloze": 3,
        "vocabulary": 4,
        # Niveles Bloom - distribuir entre las 4 APIs
        "level_1_cloze": 1,
        "level_2_relations": 2,
        "level_3_application": 3,
        "level_4_analysis": 4
    }
    
    # Modelos disponibles para fallback (en orden de preferencia)
    FALLBACK_MODELS = [
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite"
    ]

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, 
                 config_set: Optional[Dict] = None):
        """Inicializa el generador."""
        self.log_callback = log_callback or print
        self.config_set = config_set or {}
        
        # Usar modelo del config set o del .env
        self.model_name = self.config_set.get("model") or os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
        self.wait_time = self.config_set.get("wait_time", 80)
        self.replace_mode = self.config_set.get("replace_mode", False)
        self.active_types = self.config_set.get("active_types", {
            "basic": True, "multiple_choice": True, "cloze": True, "vocabulary": True
        })
        self.custom_prompts = self.config_set.get("prompts", {})
        
        self.api_keys = self._load_api_keys()
        self.ocr_api_key = os.getenv("GEMINI_API_KEY_OCR")
    
    def update_config(self, config_set: Dict):
        """Actualiza la configuración del generador."""
        self.config_set = config_set
        self.model_name = config_set.get("model") or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.wait_time = config_set.get("wait_time", 80)
        self.replace_mode = config_set.get("replace_mode", False)
        self.active_types = config_set.get("active_types", {
            "basic": True, "multiple_choice": True, "cloze": True, "vocabulary": True
        })
        self.custom_prompts = config_set.get("prompts", {})
        
        # Detectar qué set de tipos usar basado en las keys del active_types
        self._detect_card_type_set()
    
    def _load_api_keys(self) -> Dict[int, str]:
        """Carga las API keys desde variables de entorno."""
        keys = {}
        for i in range(1, 5):
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            if key:
                keys[i] = key
        return keys
    
    def _detect_card_type_set(self):
        """Detecta si estamos usando tipos normales o niveles Bloom."""
        # Si tiene keys de nivel, es set de Bloom
        if any(k.startswith("level_") for k in self.active_types.keys()):
            self.card_type_set = "bloom"
        else:
            self.card_type_set = "normal"
    
    def _log(self, message: str):
        """Registra un mensaje."""
        if self.log_callback:
            self.log_callback(message)
    
    def extract_text_from_images(self, image_paths: List[str]) -> str:
        """Extrae texto de todas las imágenes. Usa Gemini Vision, con Tesseract como fallback."""
        if not self.ocr_api_key:
            self._log("❌ API Key OCR no configurada en .env (GEMINI_API_KEY_OCR)")
            return ""
        
        # Cargar todas las imágenes primero
        self._log(f"📷 Cargando {len(image_paths)} imágenes...")
        images = []
        for idx, path in enumerate(image_paths, 1):
            self._log(f"   📷 {idx}/{len(image_paths)}: {os.path.basename(path)}")
            try:
                img = Image.open(path)
                images.append((path, img))
            except Exception as e:
                self._log(f"   ❌ Error cargando imagen: {e}")
        
        if not images:
            self._log("❌ No se pudieron cargar imágenes")
            return ""
        
        # Lista de modelos a intentar (primero el configurado, luego los fallbacks)
        models_to_try = [self.model_name] + [m for m in self.FALLBACK_MODELS if m != self.model_name]
        
        genai.configure(api_key=self.ocr_api_key)
        
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                
                self._log(f"🚀 OCR con modelo: {model_name}...")
                
                # Construir el contenido: prompt + todas las imágenes
                content = [self.OCR_PROMPT] + [img for _, img in images]
                
                response = model.generate_content(content)
                
                if response and response.text:
                    text = response.text
                    self._log(f"✅ OCR completado: {len(text)} caracteres extraídos")
                    return text
                else:
                    self._log("⚠️ Respuesta vacía, probando siguiente modelo...")
                    continue
                    
            except Exception as e:
                error_str = str(e).lower()
                
                # Detectar error de copyright - ir directo a Tesseract
                if "copyrighted" in error_str or "finish_reason" in error_str:
                    self._log(f"⚠️ Rechazado por copyright, usando Tesseract...")
                    return self._extract_with_tesseract(images)
                
                # Detectar error de cuota - probar siguiente modelo
                if "quota" in error_str or "429" in error_str or "resource" in error_str:
                    self._log(f"⚠️ Cuota excedida en {model_name}, probando siguiente modelo...")
                    continue
                
                # Otro error - probar siguiente modelo
                self._log(f"⚠️ Error con {model_name}: {e}")
                continue
        
        # Si todos los modelos fallaron, usar Tesseract
        self._log(f"⚠️ Todos los modelos Gemini fallaron, usando Tesseract...")
        return self._extract_with_tesseract(images)
    
    def _extract_with_tesseract(self, images: List[tuple]) -> str:
        """Extrae texto usando Tesseract OCR como fallback."""
        if not TESSERACT_AVAILABLE:
            self._log("❌ Tesseract no disponible. Instala: pip install pytesseract")
            self._log("   También necesitas instalar Tesseract OCR en tu sistema:")
            self._log("   https://github.com/UB-Mannheim/tesseract/wiki")
            return ""
        
        try:
            # Primero intentar con la ruta del .env
            tesseract_path = os.getenv("TESSERACT_PATH", "")
            
            if tesseract_path and os.path.exists(tesseract_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                self._log(f"   📍 Usando Tesseract desde .env: {tesseract_path}")
            else:
                # Rutas comunes en Windows
                tesseract_paths = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                    r"C:\Tesseract-OCR\tesseract.exe"
                ]
                
                found = False
                for path in tesseract_paths:
                    if os.path.exists(path):
                        pytesseract.pytesseract.tesseract_cmd = path
                        self._log(f"   📍 Tesseract encontrado en: {path}")
                        found = True
                        break
                
                if not found:
                    self._log("❌ No se encontró Tesseract. Configura TESSERACT_PATH en .env")
                    return ""
            
            self._log(f"🔍 Extrayendo texto con Tesseract OCR...")
            
            all_text = []
            for idx, (path, img) in enumerate(images, 1):
                self._log(f"   📄 Procesando imagen {idx}/{len(images)}...")
                
                # Extraer texto (español + inglés)
                text = pytesseract.image_to_string(img, lang='spa+eng')
                
                if text.strip():
                    all_text.append(f"--- Imagen {idx}: {os.path.basename(path)} ---")
                    all_text.append(text.strip())
                    all_text.append("")
            
            combined_text = "\n".join(all_text)
            
            if combined_text.strip():
                self._log(f"✅ Tesseract OCR completado: {len(combined_text)} caracteres extraídos")
                return combined_text
            else:
                self._log("❌ Tesseract no pudo extraer texto")
                return ""
                
        except Exception as e:
            self._log(f"❌ Error en Tesseract OCR: {e}")
            return ""

    def check_api_connection(self, api_index: int = 1) -> bool:
        """Verifica la conexión con una API de Gemini."""
        try:
            if api_index == 0:  # OCR API
                api_key = self.ocr_api_key
                label = "OCR"
            else:
                api_key = self.api_keys.get(api_index)
                label = f"API {api_index}"
            
            if not api_key:
                self._log(f"❌ {label} no configurada")
                return False
            
            genai.configure(api_key=api_key)
            models = list(genai.list_models())
            self._log(f"✅ {label} conectada ({len(models)} modelos)")
            return True
        except Exception as e:
            self._log(f"❌ Error {label}: {e}")
            return False
    
    def check_all_apis(self) -> Dict[str, bool]:
        """Verifica todas las APIs (OCR + 4 flashcards)."""
        results = {}
        
        # Verificar OCR API
        results["ocr"] = self.check_api_connection(0)
        
        # Verificar APIs de flashcards
        for i in range(1, 5):
            results[f"api_{i}"] = self.check_api_connection(i)
        
        return results
    
    def generate_flashcards_single(self, texto_ocr: str, card_type: str) -> Dict[str, Any]:
        """Genera flashcards de un tipo específico usando su API asignada, con fallback de modelos."""
        api_index = self.TYPE_TO_API_INDEX.get(card_type, 1)
        api_key = self.api_keys.get(api_index)
        
        if not api_key:
            return {"success": False, "error": f"API Key {api_index} no configurada", "type": card_type}
        
        # Configurar con la API key específica para este tipo
        genai.configure(api_key=api_key)
        
        # Usar prompt personalizado si existe, sino buscar en los defaults
        base_prompt = self.custom_prompts.get(card_type)
        if not base_prompt:
            # Buscar en DEFAULT_PROMPTS primero, luego en DEFAULT_PROMPTS2
            base_prompt = DEFAULT_PROMPTS.get(card_type) or DEFAULT_PROMPTS2.get(card_type, "")
        
        if not base_prompt:
            self._log(f"⚠️ [{card_type.upper()}] No se encontró prompt para este tipo")
            return {"success": False, "error": f"No prompt found for {card_type}", "type": card_type}
        
        prompt = base_prompt.format(texto_ocr=texto_ocr)
        
        # Lista de modelos a intentar
        models_to_try = [self.model_name] + [m for m in self.FALLBACK_MODELS if m != self.model_name]
        
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                
                self._log(f"🤖 [{card_type.upper()}] API {api_index} | Modelo: {model_name}...")
                response = model.generate_content(prompt)
                
                if response and response.text:
                    self._log(f"✅ [{card_type.upper()}] Respuesta recibida ({len(response.text)} chars)")
                    return {
                        "success": True,
                        "type": card_type,
                        "content": response.text,
                        "api_index": api_index,
                        "model_used": model_name
                    }
                else:
                    self._log(f"⚠️ [{card_type.upper()}] Respuesta vacía, probando siguiente modelo...")
                    continue
                    
            except Exception as e:
                error_str = str(e).lower()
                
                # Detectar error de cuota - probar siguiente modelo
                if "quota" in error_str or "429" in error_str or "resource" in error_str:
                    self._log(f"⚠️ [{card_type.upper()}] Cuota excedida en {model_name}, probando siguiente...")
                    continue
                
                # Otro error - probar siguiente modelo
                self._log(f"⚠️ [{card_type.upper()}] Error con {model_name}: {e}")
                continue
        
        # Si todos los modelos fallaron
        self._log(f"❌ [{card_type.upper()}] Todos los modelos fallaron")
        return {"success": False, "error": "Todos los modelos fallaron por cuota", "type": card_type}

    def generate_all_flashcards_parallel(self, texto_ocr: str) -> Dict[str, Dict[str, Any]]:
        """
        Genera los tipos de flashcards activos.
        NOTA: Se ejecutan secuencialmente porque genai.configure() es global
        y no es thread-safe. Cada tipo usa su propia API key.
        """
        results = {}
        
        # Filtrar solo los tipos activos (soporta tanto tipos normales como niveles Bloom)
        active_types = [t for t, active in self.active_types.items() if active]
        
        self._log("\n" + "="*50)
        self._log(f"🚀 INICIANDO GENERACIÓN DE FLASHCARDS ({len(active_types)} tipos activos)")
        self._log("="*50)
        
        if not active_types:
            self._log("⚠️ No hay tipos de flashcards activos")
            return results
        
        # Procesar secuencialmente para evitar conflictos de API key
        for card_type in active_types:
            result = self.generate_flashcards_single(texto_ocr, card_type)
            results[card_type] = result
        
        self._log("\n✅ GENERACIÓN COMPLETADA")
        return results
    
    def generate_all_flashcards_sequential(self, texto_ocr: str) -> Dict[str, Dict[str, Any]]:
        """
        Genera flashcards de forma SECUENCIAL usando las APIs en orden.
        Procesa: API1 (tipo1) → API2 (tipo2) → API3 (tipo3) → API4 (tipo4)
        
        Este método es específico para el Modo Texto donde queremos usar
        las 4 APIs diferentes de forma ordenada.
        """
        results = {}
        
        # Filtrar solo los tipos activos
        active_types = [t for t, active in self.active_types.items() if active]
        
        self._log("\n" + "="*50)
        self._log(f"🚀 GENERACIÓN SECUENCIAL ({len(active_types)} tipos activos)")
        self._log("="*50)
        
        if not active_types:
            self._log("⚠️ No hay tipos de flashcards activos")
            return results
        
        # Ordenar tipos por su API asignada para procesamiento secuencial
        # Esto asegura que usamos API1 → API2 → API3 → API4 en orden
        sorted_types = sorted(active_types, key=lambda t: self.TYPE_TO_API_INDEX.get(t, 1))
        
        self._log(f"📋 Orden de procesamiento:")
        for card_type in sorted_types:
            api_idx = self.TYPE_TO_API_INDEX.get(card_type, 1)
            self._log(f"   API{api_idx}: {card_type}")
        
        # Procesar cada tipo secuencialmente
        for idx, card_type in enumerate(sorted_types, 1):
            api_idx = self.TYPE_TO_API_INDEX.get(card_type, 1)
            self._log(f"\n[{idx}/{len(sorted_types)}] Procesando {card_type} con API{api_idx}...")
            
            result = self.generate_flashcards_single(texto_ocr, card_type)
            results[card_type] = result
            
            # Pequeña pausa entre llamadas para evitar rate limiting
            if idx < len(sorted_types):
                time.sleep(2)
        
        self._log("\n✅ GENERACIÓN SECUENCIAL COMPLETADA")
        return results
    
    def _parse_tsv_to_flashcards(self, tsv_content: str) -> List[Dict[str, str]]:
        """Convierte contenido TSV a lista de flashcards."""
        flashcards = []
        lines = tsv_content.strip().split('\n')
        
        for line in lines:
            if '\t' in line:
                parts = line.split('\t', 1)
                if len(parts) == 2:
                    flashcards.append({
                        "front": parts[0].strip(),
                        "back": parts[1].strip()
                    })
        
        return flashcards

    def _import_to_anki_with_retry(self, anki_manager, deck_name: str, 
                                    flashcards: list, card_type: str,
                                    max_retries: int = 2) -> tuple:
        """
        Importa flashcards a Anki con reintentos automáticos.
        Si falla, intenta abrir Anki y reintenta.
        Si todos los intentos fallan, guarda las flashcards para importar después.
        
        Args:
            anki_manager: Instancia de AnkiSyncManager
            deck_name: Nombre del mazo
            flashcards: Lista de flashcards
            card_type: Tipo de tarjeta
            max_retries: Número máximo de reintentos (default: 2)
            
        Returns:
            tuple: (success, message, count)
        """
        anki_not_installed = False
        last_error = ""
        
        for attempt in range(max_retries + 1):
            # Intentar importar
            success, msg, count = anki_manager.sync_flashcards_to_anki(
                deck_name, flashcards, card_type
            )
            
            if success:
                return success, msg, count
            
            last_error = msg
            
            # Detectar si Anki no está instalado
            if "not found" in msg.lower() or "installation" in msg.lower():
                anki_not_installed = True
                self._log(f"   ⚠️ Anki no parece estar instalado en este equipo")
                break
            
            # Si falló y quedan reintentos
            if attempt < max_retries:
                self._log(f"   ⚠️ Intento {attempt + 1} fallido: {msg}")
                self._log(f"   🔄 Intentando abrir Anki...")
                
                # Intentar abrir Anki
                anki_success, anki_msg = anki_manager.ensure_anki_running()
                
                if anki_success:
                    self._log(f"   ✅ {anki_msg}")
                    self._log(f"   ⏳ Esperando 10 segundos para que Anki se estabilice...")
                    time.sleep(10)
                    self._log(f"   🔄 Reintentando importación (intento {attempt + 2}/{max_retries + 1})...")
                else:
                    # Verificar si es porque no está instalado
                    if "not found" in anki_msg.lower():
                        anki_not_installed = True
                        self._log(f"   ❌ Anki no está instalado: {anki_msg}")
                        break
                    
                    self._log(f"   ❌ No se pudo abrir Anki: {anki_msg}")
                    self._log(f"   ⏳ Esperando 10 segundos antes de reintentar...")
                    time.sleep(10)
        
        # Todos los intentos fallaron - guardar para después
        self._save_pending_flashcards(deck_name, flashcards, card_type, last_error)
        
        if anki_not_installed:
            return False, f"Anki no instalado. Flashcards guardadas en {PENDING_FLASHCARDS_FILE}. Instala Anki desde https://apps.ankiweb.net/", 0
        
        return False, f"Fallido después de {max_retries + 1} intentos. Guardado en {PENDING_FLASHCARDS_FILE}", 0
    
    def _save_pending_flashcards(self, deck_name: str, flashcards: list, 
                                  card_type: str, error: str):
        """Guarda flashcards pendientes para importar después."""
        try:
            # Cargar pendientes existentes
            pending = []
            if os.path.exists(PENDING_FLASHCARDS_FILE):
                with open(PENDING_FLASHCARDS_FILE, 'r', encoding='utf-8') as f:
                    pending = json.load(f)
            
            # Añadir nuevo lote
            pending.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "deck_name": deck_name,
                "card_type": card_type,
                "flashcards": flashcards,
                "error": error,
                "count": len(flashcards)
            })
            
            # Guardar
            with open(PENDING_FLASHCARDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(pending, f, ensure_ascii=False, indent=2)
            
            self._log(f"   💾 {len(flashcards)} flashcards guardadas en {PENDING_FLASHCARDS_FILE}")
            
        except Exception as e:
            self._log(f"   ❌ Error guardando flashcards pendientes: {e}")
    
    def import_pending_flashcards(self, anki_manager) -> Dict[str, Any]:
        """
        Importa las flashcards pendientes guardadas anteriormente.
        
        Returns:
            Dict con resultados de la importación
        """
        if not os.path.exists(PENDING_FLASHCARDS_FILE):
            self._log("ℹ️ No hay flashcards pendientes de importar")
            return {"success": True, "message": "No pending flashcards", "imported": 0}
        
        try:
            with open(PENDING_FLASHCARDS_FILE, 'r', encoding='utf-8') as f:
                pending = json.load(f)
            
            if not pending:
                return {"success": True, "message": "No pending flashcards", "imported": 0}
            
            self._log(f"\n📥 IMPORTANDO {len(pending)} LOTES PENDIENTES...")
            
            total_imported = 0
            still_pending = []
            
            for item in pending:
                deck_name = item.get("deck_name", "Default")
                card_type = item.get("card_type", "basic")
                flashcards = item.get("flashcards", [])
                
                self._log(f"   📦 {deck_name} ({len(flashcards)} flashcards)...")
                
                success, msg, count = anki_manager.sync_flashcards_to_anki(
                    deck_name, flashcards, card_type
                )
                
                if success:
                    self._log(f"   ✅ Importadas {count} flashcards")
                    total_imported += count
                else:
                    self._log(f"   ❌ Falló: {msg}")
                    still_pending.append(item)
            
            # Actualizar archivo con los que siguen pendientes
            if still_pending:
                with open(PENDING_FLASHCARDS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(still_pending, f, ensure_ascii=False, indent=2)
                self._log(f"\n⚠️ {len(still_pending)} lotes siguen pendientes")
            else:
                # Eliminar archivo si ya no hay pendientes
                os.remove(PENDING_FLASHCARDS_FILE)
                self._log(f"\n✅ Todas las flashcards pendientes importadas")
            
            return {
                "success": True,
                "message": f"Imported {total_imported} flashcards",
                "imported": total_imported,
                "still_pending": len(still_pending)
            }
            
        except Exception as e:
            self._log(f"❌ Error importando pendientes: {e}")
            return {"success": False, "message": str(e), "imported": 0}
    
    def get_pending_count(self) -> int:
        """Retorna la cantidad de lotes pendientes de importar."""
        try:
            if os.path.exists(PENDING_FLASHCARDS_FILE):
                with open(PENDING_FLASHCARDS_FILE, 'r', encoding='utf-8') as f:
                    pending = json.load(f)
                return len(pending)
        except:
            pass
        return 0

    def process_section(self, section_title: str, image_paths: List[str], 
                       converter, anki_manager, deck_prefix: str) -> Dict[str, Any]:
        """
        Procesa una sección completa: OCR → 4 APIs → Conversión → Importación Anki.
        """
        self._log(f"\n{'='*60}")
        self._log(f"📁 PROCESANDO SECCIÓN: {section_title}")
        self._log(f"{'='*60}")
        self._log(f"   📷 Imágenes: {len(image_paths)}")
        
        # Paso 1: Extraer texto con Gemini Vision OCR
        self._log("\n📖 PASO 1: EXTRACCIÓN OCR CON GEMINI VISION")
        texto_ocr = self.extract_text_from_images(image_paths)
        
        if not texto_ocr.strip():
            self._log("❌ No se pudo extraer texto de las imágenes")
            return {"success": False, "error": "No text extracted", "section": section_title}
        
        # Paso 2: Generar flashcards con las 4 APIs
        self._log("\n🤖 PASO 2: GENERACIÓN CON GEMINI (4 APIs en paralelo)")
        api_results = self.generate_all_flashcards_parallel(texto_ocr)
        
        # Paso 3: Convertir e importar a Anki
        self._log("\n📥 PASO 3: CONVERSIÓN E IMPORTACIÓN A ANKI")
        import_results = {}
        
        type_labels = {
            "basic": "Basic",
            "multiple_choice": "Multiple Choice", 
            "cloze": "Cloze",
            "vocabulary": "Vocabulary",
            # Niveles Bloom
            "level_1_cloze": "Nivel 1 - Cloze",
            "level_2_relations": "Nivel 2 - Relaciones",
            "level_3_application": "Nivel 3 - Aplicación",
            "level_4_analysis": "Nivel 4 - Análisis"
        }
        
        for card_type, result in api_results.items():
            if not result.get("success"):
                self._log(f"   ⚠️ [{card_type}] Saltando - Error en generación")
                import_results[card_type] = {"success": False, "error": result.get("error")}
                continue
            
            content = result.get("content", "")
            deck_name = f"{deck_prefix} - {type_labels[card_type]}"
            
            try:
                # Convertir a formato TSV
                tsv_content = converter.convert(content, card_type)
                
                if not tsv_content:
                    self._log(f"   ⚠️ [{card_type}] No se pudieron parsear flashcards")
                    import_results[card_type] = {"success": False, "error": "Parse failed"}
                    continue
                
                # Parsear flashcards para Anki
                flashcards = self._parse_tsv_to_flashcards(tsv_content)
                
                if not flashcards:
                    self._log(f"   ⚠️ [{card_type}] Lista de flashcards vacía")
                    import_results[card_type] = {"success": False, "error": "Empty flashcards"}
                    continue
                
                # Importar a Anki con reintentos
                success, msg, count = self._import_to_anki_with_retry(
                    anki_manager, deck_name, flashcards, card_type
                )
                
                if success:
                    self._log(f"   ✅ [{card_type}] {count} flashcards importadas a '{deck_name}'")
                    import_results[card_type] = {"success": True, "count": count, "deck": deck_name}
                else:
                    self._log(f"   ❌ [{card_type}] Error: {msg}")
                    import_results[card_type] = {"success": False, "error": msg}
                    
            except Exception as e:
                self._log(f"   ❌ [{card_type}] Excepción: {e}")
                import_results[card_type] = {"success": False, "error": str(e)}
        
        return {
            "success": True,
            "section": section_title,
            "ocr_length": len(texto_ocr),
            "results": import_results
        }

    def process_all_sections(self, sections: List[Dict], converter, anki_manager,
                            progress_callback: Optional[Callable[[str, int, int], None]] = None) -> List[Dict]:
        """
        Procesa todas las secciones secuencialmente con espera de 1 minuto entre cada una.
        """
        results = []
        total = len(sections)
        
        for idx, section in enumerate(sections, 1):
            title = section.get("title", f"Sección {idx}")
            image_paths = section.get("image_paths", [])
            
            if progress_callback:
                progress_callback(title, idx, total)
            
            # Procesar sección
            result = self.process_section(
                section_title=title,
                image_paths=image_paths,
                converter=converter,
                anki_manager=anki_manager,
                deck_prefix=title
            )
            results.append(result)
            
            # Esperar tiempo configurado antes de la siguiente sección (excepto la última)
            if idx < total:
                wait = self.wait_time
                self._log(f"\n⏳ Esperando {wait} segundos antes de procesar la siguiente sección...")
                for remaining in range(wait, 0, -10):
                    self._log(f"   ⏱️ {remaining} segundos restantes...")
                    time.sleep(10)
                self._log("   ✅ Continuando con la siguiente sección")
        
        return results


def test_generator():
    """Función de prueba."""
    generator = GeminiFlashcardGenerator()
    
    print("Verificando todas las APIs...")
    results = generator.check_all_apis()
    
    for api, status in results.items():
        print(f"  {api}: {'✅' if status else '❌'}")


if __name__ == "__main__":
    test_generator()
