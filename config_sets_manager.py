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

# Instrucción adicional que se inyecta al prompt cuando el usuario activa "Usar Fuente Completa"
SOURCE_CONTEXT_INSTRUCTION = """

--- FUENTE DE CONSULTA COMPLETA (SOLO REFERENCIA) ---
A continuación se adjunta la transcripción/extracción completa del material original.
Usa esta fuente ÚNICAMENTE como referencia para:
- Resolver abreviaciones, acrónimos o siglas que aparezcan en el segmento actual.
- Entender sinónimos, analogías o simplificaciones que se refieran al mismo concepto.
- Comprender el contexto general del tema para generar flashcards más precisas y coherentes.
- Identificar la terminología correcta cuando el segmento use variaciones o referencias indirectas.

REGLA ESTRICTA: NO generes flashcards de contenido que NO esté presente en el segmento actual (Input_Texto_OCR).
La fuente es solo contexto de consulta, el segmento actual es tu único material de trabajo.

Fuente_Original:
{fuente_original}
--- FIN DE FUENTE DE CONSULTA ---
"""

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

DEFAULT_PROMPTS3 = {

    "atomic_extraction": """Rol: Ingeniero de Conocimiento Atómico para Sistemas de Repetición Espaciada (SRS).

Objetivo: Analizar el [Input_Texto_OCR] y extraer la información técnica, procedimental y factual. Debes destilar esta información en flashcards ATÓMICAS (formato Pregunta/Respuesta), eliminando toda la paja gramatical y prohibiendo estrictamente el uso de las oraciones originales del texto.

Entradas:
Input_Texto_OCR: {texto_ocr}

Reglas de Síntesis Estricta (MANDATORIAS):

    Principio de Mínima Información: Cada tarjeta debe evaluar UN SOLO vector de conocimiento. Si un concepto tiene 3 pasos, genera 3 tarjetas.

    Cero Contexto Original (Anti-Patrones): Destruye la redacción literaria del autor original. Usa lenguaje telegráfico, viñetas cortas, dos puntos (:) y flechas (->). Tu objetivo es aislar la variable técnica.

    Cero Opción Múltiple o Escenarios Largos: Todo debe ser Recuperación Activa pura y directa.

Tipos de Tarjetas a Generar (Aplica según el contenido detectado):

A. Tarjeta de Dato/Término (La Esencia del Nivel 1):
Objetivo: Aislar variables técnicas puras sin el contexto del párrafo.

    P: [Categoría general o Sistema]: [Función específica o Atributo clave].

    R: [Término exacto, código, métrica o constante].
    (Ejemplo P: "Biología celular: Organelo responsable de síntesis de ATP." R: "Mitocondria")

B. Tarjeta de Diferencia/Contraste (La Esencia del Nivel 2):
Objetivo: Evitar la confusión entre conceptos similares midiendo solo una variable.

    P: [Concepto A] vs [Concepto B] respecto a -> [Variable específica].

    R: [Concepto A = Estado 1] | [Concepto B = Estado 2].
    (Ejemplo P: "TCP vs UDP respecto a -> Retransmisión de paquetes perdidos." R: "TCP = Sí | UDP = No")

C. Tarjeta de Ejecución/Procedimiento (La Esencia del Nivel 3):
Objetivo: Obligar a invocar la herramienta o comando exacto para un problema.

    P: [Entorno/Sistema/Lenguaje]: Objetivo a lograr -> Comando/Herramienta necesaria.

    R: [Sintaxis exacta o Nombre de la herramienta].
    (Ejemplo P: "Git: Comando para deshacer último commit conservando cambios en staging." R: "git reset --soft HEAD~1")

Instrucción de Formato de Salida (Estricto):
Tu respuesta final debe ser OBLIGATORIAMENTE una lista de texto plano. Separa los pares con una línea en blanco. Usa estrictamente el prefijo "P:" para la pregunta y "R:" para la respuesta."""

}

DEFAULT_PROMPTS4 = {
    "high_performance_architect": """Rol: Arquitecto de Aprendizaje de Alto Rendimiento e Ingeniero de Confiabilidad.

Objetivo: Analizar el [Input_Multimodal] (que puede provenir de OCR, transcripciones de video/audio, libros o código) y destilarlo en flashcards ATÓMICAS de alto impacto. Tu meta es transformar la teoría pasiva en ESCENARIOS DE RESOLUCIÓN DE PROBLEMAS, aplicando la Taxonomía de Bloom (Niveles 2 y 3).

Entradas:
Input_Multimodal: {texto_ocr}

Reglas de Síntesis Estricta (MANDATORIAS):
1. Limpieza de Ruido: Ignora saludos, muletillas, anécdotas del presentador o relleno literario. Extrae solo los vectores de conocimiento técnico, lógico o procedimental.
2. La Regla del "Caballo de Troya" (Cero Diccionarios): ESTRICTAMENTE PROHIBIDO generar tarjetas de Nivel 1 preguntando "¿Qué es [Concepto]?" o "¿Defina [Término]?". El concepto teórico debe ser la RESPUESTA a un problema o restricción planteada en la pregunta.
3. Principio Atómico: Un solo problema/decisión por tarjeta. Si un escenario requiere evaluar 3 variables distintas, genera 3 tarjetas separadas.
4. Lenguaje Telegráfico: Usa viñetas, flechas (->) y elimina artículos innecesarios.

Tipos de Tarjetas a Generar (Aplica según el contenido):

A. Tarjeta de Resolución / Edge Case (El Estándar - Nivel 3):
Objetivo: El anverso plantea un cuello de botella, un error, o una restricción (legal/técnica) basada en el texto. El reverso es el concepto o técnica que lo soluciona.
P: [Escenario hostil, falla o restricción extraída del texto]. ¿Solución/Concepto a aplicar?
R: [Término técnico, patrón o acción exacta].
(Ejemplo P: "El área legal bloquea el despliegue porque el dataset expone direcciones de víctimas. ¿Técnica de mitigación requerida?" -> R: "Data Masking (Enmascaramiento)").

B. Tarjeta de Contraste Operativo (Toma de Decisiones - Nivel 2):
Objetivo: Evaluar cuándo usar la Herramienta/Concepto A frente a la B ante un problema específico.
P: Objetivo: [Meta operativa]. Condición limitante: [Restricción del entorno]. ¿Elección arquitectónica: [A] o [B]?
R: [Opción correcta] -> [Razón telegráfica de 3 palabras].
(Ejemplo P: "Objetivo: Consultar base de datos. Condición: Se requiere respuesta automática y en tiempo real. ¿Interoperabilidad o Gestión Tradicional?" -> R: "Interoperabilidad -> Flujo sin fricción").

C. Excepción de Constante Pura (Nivel 1 Restringido):
Objetivo: ÚNICAMENTE para límites matemáticos absolutos, sintaxis inmutable, puertos de red o leyes físicas que no pueden abstraerse.
P: [Sistema/Entorno]: [Variable o límite estricto a recordar].
R: [Número, constante o código exacto].
(Ejemplo P: "PostgreSQL: Puerto de conexión por defecto." -> R: "5432").

Instrucción de Formato de Salida (Estricto):
Devuelve OBLIGATORIAMENTE una lista en texto plano.
Separa cada par con una línea en blanco.
Usa estrictamente el prefijo "P:" para la pregunta y "R:" para la respuesta.
NO agregues introducciones, confirmaciones ni conclusiones. Solo el output."""
}


DEFAULT_PROMPTS5 = {
    "exam_pareto": """Rol: Diseñador Senior de Exámenes de Certificación Profesional (AWS, Azure, OCI, Oracle, PMP, etc.).

═══════════════════════════════════════════════
⛔ PROTOCOLO DE FIDELIDAD — PROHIBICIÓN ABSOLUTA
═══════════════════════════════════════════════
Antes de generar cualquier flashcard, evalúa si el material contiene suficiente contenido educativo real.

❌ PROHIBIDO: No extrapoles contenido NO explícitamente observable en el material dado.
❌ PROHIBIDO: No completes huecos usando tu conocimiento general como LLM. Tu base de entrenamiento NO es una fuente válida.
❌ PROHIBIDO: No inventes ni inferras conceptos por asociación temática (ver "OSINERGMIN" no te autoriza a inventar flashcards sobre regulación energética).
❌ PROHIBIDO: Fechas aisladas, años de fundación, lugares geográficos sin contexto de aplicación práctica.
❌ PROHIBIDO: Preguntas tipo "¿En qué año se fundó X?" o "¿Dónde se creó Y?" — no sirven en exámenes de certificación.
❌ PROHIBIDO: Rellenar silencios, diapositivas de título, introducciones o despedidas con flashcards.
❌ PROHIBIDO: Generar flashcards si el contenido docente real es insuficiente.

✅ SI el material tiene menos de 3 conceptos aplicables y verificables → devuelve ÚNICAMENTE el texto: #SIN_CONTENIDO_SUFICIENTE
✅ Solo usa información explícita y verificable dentro del material proporcionado.
✅ Prefiere omitir antes que inferir.

══════════════════════════════════
📊 PRINCIPIO PARETO — PRIORIZACIÓN
══════════════════════════════════
No generes flashcards de todos los conceptos por igual.
Aplica razonamiento estadístico: identifica los conceptos que estadísticamente aparecen con más frecuencia en exámenes de certificación del tipo que corresponde al material.
Un buen principio desbloquea múltiples hechos. Un dato aislado solo memoriza uno.
Prioriza: mecanismos, componentes funcionales, casos de uso, criterios de elección, garantías del sistema.
Evita: trivia, datos administrativos, contexto histórico sin aplicación.

══════════════════════════════
🎯 DISTRIBUCIÓN ADAPTATIVA
══════════════════════════════
Adapta la distribución según lo que el material realmente contiene:
- Si el material es de herramientas/soluciones → más preguntas de escenario/decisión.
- Si el material es conceptual/teórico → más preguntas de principios y comprensión.
- Si el material es mixto → balancea según la proporción real del contenido.
No impongas una distribución fija si el material no lo permite.

══════════════════════════════════════
📐 FORMATO DE FLASHCARDS (Q&A Clásico)
══════════════════════════════════════
Tipo predominante: Pregunta de escenario o decisión → Respuesta que explica el principio y su aplicación.
Longitud de respuesta: Suficiente para entender el concepto (puede ser 1 oración directa o 2-3 si el principio lo requiere). NO sobre-expliques.
No uses Cloze. Solo Q&A clásico.
Fórmulas y Variables: Toda fórmula matemática, código en línea o variable aislada debe estar encerrada usando formato MathJax de Anki, empezando exactamente con \\( y terminando con \\). Ejemplo: \\( x^2 = 4 \\).

Ejemplos del estilo deseado:
P: En OCI, ¿qué permite a los clientes el modelo de precios de Créditos Universales?
R: Utilizar créditos prepagados para cualquier servicio en la nube elegible, otorgando flexibilidad total sin comprometerse a un servicio específico.

P: ¿Qué componente de red de la VCN de OCI proporciona a las instancias en subred privada acceso a Internet de salida sin exponer una IP pública?
R: Network Address Translation (NAT) Gateway. Permite el tráfico saliente desde instancias privadas sin permitir conexiones entrantes iniciadas desde Internet.

P: ¿Cuál es la diferencia funcional entre un NSG y una Security List en OCI Networking?
R: Los NSGs controlan el tráfico entre recursos específicos dentro de una VCN, mientras que las Security Lists aplican reglas a todas las instancias de una subred completa.

══════════════════════════
MATERIAL DE TRABAJO:
{texto_ocr}
══════════════════════════

INSTRUCCIÓN DE FORMATO DE SALIDA (Estricto):
Si hay contenido suficiente: devuelve SOLO pares P/R separados por una línea en blanco.
Si NO hay contenido suficiente: devuelve SOLO el texto: #SIN_CONTENIDO_SUFICIENTE
NO agregues introducciones, confirmaciones, resúmenes ni conclusiones."""
}


DEFAULT_PROMPTS6 = {
    "exam_faithful": """Rol: Extractor de Ideas Principales para Estudio de Certificación Profesional.

═══════════════════════════════════════════════
⛔ PROTOCOLO DE FIDELIDAD — PROHIBICIÓN ABSOLUTA
═══════════════════════════════════════════════
Antes de generar cualquier flashcard, evalúa si el material contiene suficiente contenido educativo real.

❌ PROHIBIDO: No extrapoles contenido NO explícitamente observable en el material dado.
❌ PROHIBIDO: No completes huecos usando tu conocimiento general como LLM. Tu base de entrenamiento NO es una fuente válida.
❌ PROHIBIDO: No inventes ni inferras conceptos por asociación temática.
❌ PROHIBIDO: Fechas aisladas, años de fundación, lugares geográficos sin contexto de aplicación práctica.
❌ PROHIBIDO: Preguntas tipo "¿En qué año se fundó X?" o "¿Dónde se creó Y?".
❌ PROHIBIDO: Rellenar silencios, diapositivas de título, introducciones o despedidas con flashcards.
❌ PROHIBIDO: Generar flashcards si el contenido docente real es insuficiente.

✅ SI el material tiene menos de 3 conceptos aplicables y verificables → devuelve ÚNICAMENTE el texto: #SIN_CONTENIDO_SUFICIENTE
✅ Solo usa información explícita y verificable dentro del material proporcionado.
✅ Prefiere omitir antes que inferir.

══════════════════════════════════════════════
🎯 OBJETIVO: EXTRACCIÓN COMPLETA Y FIEL
══════════════════════════════════════════════
Extrae TODAS las ideas principales y secundarias con valor de estudio real que estén presentes en el material.
No apliques priorización estadística (Pareto): si el material lo menciona y es relevante para un examen, inclúyelo.
Un concepto tiene valor si:
  - Explica un mecanismo, componente o proceso.
  - Establece una relación causal o comparativa.
  - Define un criterio de selección, limitación o garantía.
  - Permite al estudiante resolver un problema o tomar una decisión.
No tiene valor si es: dato administrativo, fecha sin contexto, nombre de ciudad, anécdota, saludo.

══════════════════════════════════════════════
📐 FORMATO DE FLASHCARDS (Q&A Clásico)
══════════════════════════════════════════════
Usa preguntas directas y respuestas completas que obliguen a recrear el concepto.
Longitud de respuesta: la necesaria para entender la idea (no sobre-expliques, no sub-expliques).
No uses Cloze. Solo Q&A clásico.
Fórmulas y Variables: Toda fórmula matemática, código en línea o variable aislada debe estar encerrada usando formato MathJax de Anki, empezando exactamente con \\( y terminando con \\). Ejemplo: \\( x^2 = 4 \\).

Ejemplos del estilo deseado:
P: ¿Cuál es el propósito principal de un Grupo de Seguridad de Red (NSG) en OCI?
R: Controlar el flujo de tráfico entre recursos específicos dentro de una VCN, aplicando reglas de seguridad a nivel de recurso individual en lugar de subred completa.

P: En el análisis conceptual de un juego, ¿qué cuatro preguntas clave debe responder el diseñador para definir la experiencia del jugador?
R: ¿Quién es el personaje?, ¿Qué acciones realiza?, ¿Qué metas u objetivos logra?, y ¿Qué emociones o sentimientos experimenta el jugador?

P: ¿Por qué el Network Load Balancer es preferible al Standard Load Balancer para tráfico TCP de baja latencia?
R: Porque opera en la Capa 4 del modelo OSI, lo que le permite procesar tráfico TCP y UDP con menor overhead que el Standard Load Balancer que opera en Capa 7 (HTTP/HTTPS).

══════════════════════════
MATERIAL DE TRABAJO:
{texto_ocr}
══════════════════════════

INSTRUCCIÓN DE FORMATO DE SALIDA (Estricto):
Si hay contenido suficiente: devuelve SOLO pares P/R separados por una línea en blanco.
Si NO hay contenido suficiente: devuelve SOLO el texto: #SIN_CONTENIDO_SUFICIENTE
NO agregues introducciones, confirmaciones, resúmenes ni conclusiones."""
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

# Set de configuración de Extracción Atómica
DEFAULT_CONFIG_SET_ATOMIC = {
    "name": "Extracción Atómica",
    "description": "Flashcards atómicas P/R: Dato/Término, Diferencia/Contraste, Ejecución/Procedimiento",
    "model": "gemini-3-flash-preview",
    "wait_time": 60,
    "replace_mode": False,
    "active_types": {
        "atomic_extraction": True
    },
    "prompts": DEFAULT_PROMPTS3.copy(),
    "created_at": "",
    "updated_at": ""
}

# Set de configuración de Alto Rendimiento
DEFAULT_CONFIG_SET_HIGH_PERFORMANCE = {
    "name": "Alto Rendimiento",
    "description": "Transforma teoría en escenarios de resolución de problemas (Taxonomía de Bloom Nivel 2 y 3).",
    "model": "gemini-3-flash-preview",
    "wait_time": 60,
    "replace_mode": False,
    "active_types": {
        "high_performance_architect": True
    },
    "prompts": DEFAULT_PROMPTS4.copy(),
    "created_at": "",
    "updated_at": ""
}

# Set de configuración de Examen Pareto
DEFAULT_CONFIG_SET_EXAM_PARETO = {
    "name": "Examen Pareto",
    "description": "Flashcards estilo certificación. Solo contenido explícito del material. Priorización estadística tipo Pareto. Sin inferencias ni relleno.",
    "model": "gemini-3-flash-preview",
    "wait_time": 60,
    "replace_mode": False,
    "active_types": {
        "exam_pareto": True
    },
    "prompts": DEFAULT_PROMPTS5.copy(),
    "created_at": "",
    "updated_at": ""
}

# Set de configuración de Examen Fiel
DEFAULT_CONFIG_SET_EXAM_FAITHFUL = {
    "name": "Examen Fiel",
    "description": "Extracción completa de ideas principales para examen. Fidelidad absoluta al material. Sin Pareto. Sin inferencias ni relleno con conocimiento del LLM.",
    "model": "gemini-3-flash-preview",
    "wait_time": 60,
    "replace_mode": False,
    "active_types": {
        "exam_faithful": True
    },
    "prompts": DEFAULT_PROMPTS6.copy(),
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
        
        # Asegurar que existe el set de Extracción Atómica
        if "Extracción Atómica" not in self.config_sets:
            atomic = DEFAULT_CONFIG_SET_ATOMIC.copy()
            atomic["prompts"] = DEFAULT_PROMPTS3.copy()
            atomic["active_types"] = DEFAULT_CONFIG_SET_ATOMIC["active_types"].copy()
            atomic["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            atomic["updated_at"] = atomic["created_at"]
            self.config_sets["Extracción Atómica"] = atomic
            
        # Asegurar que existe el set de Alto Rendimiento
        if "Alto Rendimiento" not in self.config_sets:
            high_perf = DEFAULT_CONFIG_SET_HIGH_PERFORMANCE.copy()
            high_perf["prompts"] = DEFAULT_PROMPTS4.copy()
            high_perf["active_types"] = DEFAULT_CONFIG_SET_HIGH_PERFORMANCE["active_types"].copy()
            high_perf["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            high_perf["updated_at"] = high_perf["created_at"]
            self.config_sets["Alto Rendimiento"] = high_perf
        
        # Asegurar que existe el set de Examen Pareto
        if "Examen Pareto" not in self.config_sets:
            exam_pareto = DEFAULT_CONFIG_SET_EXAM_PARETO.copy()
            exam_pareto["prompts"] = DEFAULT_PROMPTS5.copy()
            exam_pareto["active_types"] = DEFAULT_CONFIG_SET_EXAM_PARETO["active_types"].copy()
            exam_pareto["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            exam_pareto["updated_at"] = exam_pareto["created_at"]
            self.config_sets["Examen Pareto"] = exam_pareto
        
        # Asegurar que existe el set de Examen Fiel
        if "Examen Fiel" not in self.config_sets:
            exam_faithful = DEFAULT_CONFIG_SET_EXAM_FAITHFUL.copy()
            exam_faithful["prompts"] = DEFAULT_PROMPTS6.copy()
            exam_faithful["active_types"] = DEFAULT_CONFIG_SET_EXAM_FAITHFUL["active_types"].copy()
            exam_faithful["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            exam_faithful["updated_at"] = exam_faithful["created_at"]
            self.config_sets["Examen Fiel"] = exam_faithful
        
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
        # Buscar en todos los diccionarios por defecto
        if card_type in DEFAULT_PROMPTS:
            return DEFAULT_PROMPTS[card_type]
        elif card_type in DEFAULT_PROMPTS2:
            return DEFAULT_PROMPTS2[card_type]
        elif card_type in DEFAULT_PROMPTS3:
            return DEFAULT_PROMPTS3[card_type]
        elif card_type in DEFAULT_PROMPTS4:
            return DEFAULT_PROMPTS4[card_type]
        elif card_type in DEFAULT_PROMPTS5:
            return DEFAULT_PROMPTS5[card_type]
        elif card_type in DEFAULT_PROMPTS6:
            return DEFAULT_PROMPTS6[card_type]
        return ""
    
    def reset_prompt_to_default(self, set_name: str, card_type: str) -> bool:
        """Restaura el prompt de un tipo al valor por defecto."""
        if set_name not in self.config_sets:
            return False
        
        for prompt_dict in [DEFAULT_PROMPTS, DEFAULT_PROMPTS2, DEFAULT_PROMPTS3, 
                            DEFAULT_PROMPTS4, DEFAULT_PROMPTS5, DEFAULT_PROMPTS6]:
            if card_type in prompt_dict:
                self.config_sets[set_name]["prompts"][card_type] = prompt_dict[card_type]
                self.config_sets[set_name]["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                self._save_config_sets()
                return True
        return False
