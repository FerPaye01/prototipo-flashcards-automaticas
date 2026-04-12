"""
Gestor de Sets de Configuración para generación de flashcards.
Permite guardar, cargar, exportar e importar configuraciones personalizadas.
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime

# Carpeta maestra para archivos generados
MASTER_FOLDER = "Flashcards Programa"

CONFIG_SETS_FILE = os.path.join(MASTER_FOLDER, "flashcard_config_sets.json")

DEFAULT_PROMPTS = {

    "basic": """Rol: Asesor experto en pedagogía cognitiva y diseño instruccional para niños.

Objetivo: Analizar el [Input_Texto_OCR] e identificar los Conceptos Clave. Para CADA concepto identificado, debes generar OBLIGATORIAMENTE un par de tarjetas consecutivas (Tarjeta A y Tarjeta B) siguiendo esta lógica:

1. Tarjeta A (El "Qué" - Estricta/Técnica):

• Objetivo: Recuperación Activa de la definición precisa o el dato exacto.

• Estilo: Pregunta directa y respuesta concisa.

2. Tarjeta B (El "Cómo/Por qué" - Estilo Feynman):

• Objetivo: Comprensión profunda y simplificación.

• Estilo: La pregunta debe pedir una explicación para un niño de 9 años o una analogía. La respuesta debe usar lenguaje cotidiano, evitando la jerga técnica usada en la Tarjeta A.

Entradas: Input_Texto_OCR: {texto_ocr}

Instrucción de Formato de Salida (Estricto): Tu respuesta debe ser una lista de texto plano. Separa los pares de tarjetas con una línea divisoria.

Estructura del Par: [Concepto: Nombre del Concepto] P: [Pregunta  (Estricta) de definición/dato preciso] R: [Respuesta técnica y corta]

P: [Pregunta tipo (Feynman): "¿Cómo le explicarías esto a un amigo?" o "Pon un ejemplo de la vida real de..."] R: [Explicación simplificada usando una analogía o vocabulario sencillo, máximo 2 frases]""",



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

Selección Autónoma: Identifica los conceptos clave (términos técnicos, métricas, nombres propios, causas-efectos, procesos). Ignora la paja.

Fidelidad: Extrae la oración original donde aparece el concepto. Recorta lo innecesario para que la frase tenga sentido por sí sola, pero no la reescribas.

Lógica de Oclusión (Anki):

Ocultamiento: Encierra el concepto clave con {{{{c1::Concepto::Pista}}}}.

Pista: La pista (después de los dos puntos) es OBLIGATORIA para dar contexto (ej: ::Métrica, ::Algoritmo, ::Fecha).

Listas: Si encuentras una enumeración importante, usa {{{{c1::A}}}}, {{{{c2::B}}}}, {{{{c3::C}}}}.



Instrucción de Formato de Salida (Estricto)

No uses bloques de código (```), no uses JSON, y no agregues introducciones ni conclusiones.

Estructura obligatoria: 

P: [Oración en español con huecos / Término] 

""",



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



DEFAULT_PROMPTS2 = {

    "level_1_cloze": """Rol: Editor de Diseño Instruccional experto en minería de textos y Anki.

Objetivos:
Analizar el [Input_Texto_OCR] completo. Tu tarea es identificar TODOS los conceptos técnicos, datos fácticos, métricas o definiciones más críticas del texto y convertirlos en tarjetas de memorización "Cloze" (huecos).

Entradas:
Input_Texto_OCR: {texto_ocr}

Reglas de Procesamiento:
1. Selección Atómica: Identifica términos técnicos, constantes numéricas y nombres de autores. Ignora la paja retórica.
2. Fidelidad Estricta: Extrae la oración original donde aparece el concepto. Recorta lo innecesario para que la frase sea una oración simple (Sujeto+Verbo+Predicado) pero mantén la terminología exacta.
3. Citas: Si la frase original menciona un autor o año (ej: "Según Knuth (1978)..."), MANTENLO en la tarjeta.

Lógica de Oclusión (Anki):
- Ocultamiento: Encierra el concepto clave con {{{{c1::Concepto::Pista}}}}.
- Pista Obligatoria: La pista (después de los dos puntos) es MANDATORIA para dar contexto (ej: ::Métrica, ::Algoritmo, ::Autor).
- Listas: Si hay una enumeración vital, usa {{{{c1::A}}}}, {{{{c2::B}}}}, {{{{c3::C}}}}.

Instrucción de Formato de Salida (Estricto):
No uses bloques de código.
Estructura obligatoria:
P: [Oración en español con huecos procesados]
(Deja una línea en blanco entre tarjetas)""",


    "level_2_relations": """Rol: Arquitecto de Sistemas de Conocimiento.

Objetivo: Generar flashcards de Nivel 2 (Entender) basadas en el [Input_Texto_OCR]. El usuario ya memorizó los términos (Nivel 1); ahora debe comprender sus relaciones sistémicas.

Entradas:
Input_Texto_OCR: {texto_ocr}

Reglas de Generación (Prohibido Definir):
No generes preguntas de "¿Qué es?". Usa exclusivamente estos patrones de relación:
1. Análisis Comparativo: "¿Cuál es la diferencia crítica entre [Concepto A] y [Concepto B] mencionada en el texto?" o "¿En qué coinciden X y Y?"
2. Causalidad Sistémica: "¿Qué efecto inmediato tiene [Evento X] sobre [Componente Y]?"
3. Traducción/Interpretación: "El texto afirma [Cita corta]. ¿Qué implica esto para el sistema en términos simples?"

Formato de Respuesta:
- Concisión: La respuesta debe ser de 1 o 2 oraciones máximo.
- Analogía Feynman: Si el concepto es muy abstracto, puedes añadir una brevísima analogía al final de la respuesta.

Instrucción de Formato de Salida (Estricto):
P: [Pregunta Relacional]
R: [Explicación concisa]
(Deja una línea en blanco entre pares)""",

    "level_3_application": """Rol: Entrenador Técnico de Simulaciones.

Objetivo: Generar flashcards de Nivel 3 (Aplicar). El usuario debe resolver Micro-Escenarios usando la información del [Input_Texto_OCR]. No preguntes teoría, fuerza la práctica.

Entradas:
Input_Texto_OCR: {texto_ocr}

Reglas de Generación (Procedimental):
Crea situaciones donde se deba aplicar una regla, fórmula o criterio de selección.
1. El Compilador Mental: "Dados los datos [X, Y] presentes en el texto, ¿cuál sería el resultado de aplicar [Fórmula/Regla]?"
2. Troubleshooting: "El sistema presenta el síntoma [Z]. Basado en el texto, ¿qué herramienta o paso corrige esto?"
3. Selección de Herramienta: "Para lograr el objetivo [A] con la restricción [B], ¿qué método del texto es el correcto?"

Instrucción de Formato de Salida (Estricto):
- Matemáticas: Usa formato LaTeX \\( ... \\)
P: [Escenario / Datos / Problema]
R: [Solución Exacta / Herramienta Única]
(Deja una línea en blanco entre pares)""",


    "level_4_analysis": """Rol: Diseñador Senior de Exámenes de Certificación (Psicometría).

Objetivos: Generar preguntas de opción múltiple de alta dificultad para discriminar conocimiento experto de superficial.

Entradas:
Input_Texto_OCR: {texto_ocr}

Ingeniería de Distractores (MANDATORIO):
Para cada pregunta, genera 3 distractores diseñados para poner a prueba la atención:
1. El Espejo Sintáctico: Misma gramática que la correcta, pero cambia una variable clave técnica.
2. La Invención Plausible: Inventa un término que suene altamente técnico y creíble, pero que sea falso (Trampa de Alucinación).
3. Verdad Mal Atribuida: Un concepto real y correcto del texto, pero que NO responde a esta pregunta específica (Trampa de Contexto).

Instrucción de Formato de Salida (Estricto):
Tu respuesta final debe ser ÚNICAMENTE una lista de texto plano.
Estructura obligatoria:
P: [Enunciado complejo o escenario]
a) [Opción]
b) [Opción]
c) [Opción]
d) [Opción]
R: [Letra Correcta] - [Justificación breve: Por qué es la correcta y por qué la "Verdad Mal Atribuida" es incorrecta aquí]
(Deja una línea en blanco entre cada par P/R)"""
}

# Set de configuración por defecto
DEFAULT_CONFIG_SET = {
    "name": "Por Defecto",
    "description": "Configuración estándar con los 4 tipos de flashcards",
    "model": "gemini-3-flash-preview",
    "wait_time": 60,
    "replace_mode": False, 
    "active_types": {
        "basic": True,
        "multiple_choice": True,
        "cloze": True,
        "vocabulary": True
    },
    "prompts": DEFAULT_PROMPTS.copy(),
    "created_at": "",
    "updated_at": ""
}

# Set de configuración por niveles de Bloom
DEFAULT_CONFIG_SET_LEVELS = {
    "name": "Niveles Bloom",
    "description": "4 niveles cognitivos: Cloze (recordar), Relaciones (entender), Aplicación (aplicar), Análisis (analizar)",
    "model": "gemini-3-flash-preview",
    "wait_time": 80,
    "replace_mode": False,
    "active_types": {
        "level_1_cloze": True,
        "level_2_relations": True,
        "level_3_application": True,
        "level_4_analysis": True
    },
    "prompts": DEFAULT_PROMPTS2.copy(),
    "created_at": "",
    "updated_at": ""
}


class ConfigSetsManager:
    """Gestor de sets de configuración."""
    
    def __init__(self):
        self.config_sets: Dict[str, dict] = {}
        self.active_set_name: str = "Por Defecto"
        self._load_config_sets()
    
    def _load_config_sets(self):
        """Carga los sets de configuración desde el archivo."""
        try:
            if os.path.exists(CONFIG_SETS_FILE):
                with open(CONFIG_SETS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config_sets = data.get("sets", {})
                    self.active_set_name = data.get("active_set", "Por Defecto")
        except Exception as e:
            print(f"Error cargando config sets: {e}")
        
        # Asegurar que existe el set por defecto
        if "Por Defecto" not in self.config_sets:
            default = DEFAULT_CONFIG_SET.copy()
            default["prompts"] = DEFAULT_PROMPTS.copy()
            default["active_types"] = DEFAULT_CONFIG_SET["active_types"].copy()
            default["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            default["updated_at"] = default["created_at"]
            self.config_sets["Por Defecto"] = default
        
        # Asegurar que existe el set de Niveles Bloom
        if "Niveles Bloom" not in self.config_sets:
            levels = DEFAULT_CONFIG_SET_LEVELS.copy()
            levels["prompts"] = DEFAULT_PROMPTS2.copy()
            levels["active_types"] = DEFAULT_CONFIG_SET_LEVELS["active_types"].copy()
            levels["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            levels["updated_at"] = levels["created_at"]
            self.config_sets["Niveles Bloom"] = levels
        
        self._save_config_sets()
    
    def _save_config_sets(self):
        """Guarda los sets de configuración en el archivo."""
        try:
            data = {
                "active_set": self.active_set_name,
                "sets": self.config_sets
            }
            with open(CONFIG_SETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error guardando config sets: {e}")
    
    def get_set_names(self) -> List[str]:
        """Retorna la lista de nombres de sets disponibles."""
        return list(self.config_sets.keys())
    
    def get_active_set(self) -> dict:
        """Retorna el set de configuración activo."""
        return self.config_sets.get(self.active_set_name, DEFAULT_CONFIG_SET)
    
    def set_active_set(self, name: str) -> bool:
        """Establece el set activo."""
        if name in self.config_sets:
            self.active_set_name = name
            self._save_config_sets()
            return True
        return False
    
    def create_set(self, name: str, config: Optional[dict] = None) -> bool:
        """Crea un nuevo set de configuración."""
        if name in self.config_sets:
            return False
        
        new_set = config if config else DEFAULT_CONFIG_SET.copy()
        new_set["name"] = name
        new_set["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_set["updated_at"] = new_set["created_at"]
        
        # Asegurar que tiene prompts
        if "prompts" not in new_set:
            new_set["prompts"] = DEFAULT_PROMPTS.copy()
        
        self.config_sets[name] = new_set
        self._save_config_sets()
        return True
    
    def update_set(self, name: str, config: dict) -> bool:
        """Actualiza un set existente."""
        if name not in self.config_sets:
            return False
        
        config["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        config["name"] = name
        self.config_sets[name] = config
        self._save_config_sets()
        return True
    
    def delete_set(self, name: str) -> bool:
        """Elimina un set (no permite eliminar 'Por Defecto')."""
        if name == "Por Defecto" or name not in self.config_sets:
            return False
        
        del self.config_sets[name]
        
        # Si era el activo, cambiar al por defecto
        if self.active_set_name == name:
            self.active_set_name = "Por Defecto"
        
        self._save_config_sets()
        return True
    
    def duplicate_set(self, source_name: str, new_name: str) -> bool:
        """Duplica un set existente con un nuevo nombre."""
        if source_name not in self.config_sets or new_name in self.config_sets:
            return False
        
        new_set = self.config_sets[source_name].copy()
        new_set["prompts"] = self.config_sets[source_name]["prompts"].copy()
        new_set["active_types"] = self.config_sets[source_name]["active_types"].copy()
        new_set["name"] = new_name
        new_set["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_set["updated_at"] = new_set["created_at"]
        
        self.config_sets[new_name] = new_set
        self._save_config_sets()
        return True
    
    def export_set(self, name: str) -> Optional[str]:
        """Exporta un set como string JSON."""
        if name not in self.config_sets:
            return None
        
        try:
            return json.dumps(self.config_sets[name], ensure_ascii=False, indent=2)
        except Exception:
            return None
    
    def export_set_to_file(self, name: str, filepath: str) -> bool:
        """Exporta un set a un archivo JSON."""
        if name not in self.config_sets:
            return False
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.config_sets[name], f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def import_set(self, json_str: str) -> tuple:
        """
        Importa un set desde un string JSON.
        Retorna (success, message)
        """
        try:
            config = json.loads(json_str)
            
            # Validar estructura básica
            if "name" not in config:
                return False, "El JSON no contiene un nombre de set"
            
            name = config["name"]
            
            # Si ya existe, añadir sufijo
            original_name = name
            counter = 1
            while name in self.config_sets:
                name = f"{original_name} ({counter})"
                counter += 1
            
            config["name"] = name
            
            # Asegurar campos requeridos
            if "prompts" not in config:
                config["prompts"] = DEFAULT_PROMPTS.copy()
            if "active_types" not in config:
                config["active_types"] = {"basic": True, "multiple_choice": True, 
                                          "cloze": True, "vocabulary": True}
            if "model" not in config:
                config["model"] = "gemini-2.5-flash-lite-preview-06-17"
            if "wait_time" not in config:
                config["wait_time"] = 80
            if "replace_mode" not in config:
                config["replace_mode"] = False
            
            config["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            config["updated_at"] = config["created_at"]
            
            self.config_sets[name] = config
            self._save_config_sets()
            
            return True, f"Set '{name}' importado correctamente"
            
        except json.JSONDecodeError:
            return False, "El texto no es un JSON válido"
        except Exception as e:
            return False, f"Error importando: {e}"
    
    def import_set_from_file(self, filepath: str) -> tuple:
        """
        Importa un set desde un archivo JSON.
        Retorna (success, message)
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                json_str = f.read()
            return self.import_set(json_str)
        except Exception as e:
            return False, f"Error leyendo archivo: {e}"
    
    def get_default_prompt(self, card_type: str) -> str:
        """Retorna el prompt por defecto para un tipo de tarjeta."""
        # Buscar primero en DEFAULT_PROMPTS, luego en DEFAULT_PROMPTS2
        if card_type in DEFAULT_PROMPTS:
            return DEFAULT_PROMPTS[card_type]
        elif card_type in DEFAULT_PROMPTS2:
            return DEFAULT_PROMPTS2[card_type]
        return ""
    
    def reset_prompt_to_default(self, set_name: str, card_type: str) -> bool:
        """Restaura el prompt de un tipo al valor por defecto."""
        if set_name not in self.config_sets:
            return False
        
        if card_type in DEFAULT_PROMPTS:
            self.config_sets[set_name]["prompts"][card_type] = DEFAULT_PROMPTS[card_type]
            self.config_sets[set_name]["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            self._save_config_sets()
            return True
        elif card_type in DEFAULT_PROMPTS2:
            self.config_sets[set_name]["prompts"][card_type] = DEFAULT_PROMPTS2[card_type]
            self.config_sets[set_name]["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            self._save_config_sets()
            return True
        return False
