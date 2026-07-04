# Documentación Técnica: Filtrado de Embeddings, Métricas QYI y Configuración de Examen Fiel

Este documento proporciona una especificación técnica formal y objetiva de los mecanismos de filtrado semántico, evaluación pedagógica y estructuración de exámenes implementados en el sistema de flashcards. Su propósito es servir como referencia de auditoría para la evaluación de desempeño y correctitud del sistema.

---

## 1. Metodología de Filtrado por Embeddings (Deduplicación Semántica)

El motor de deduplicación semántica (`DeduplicationEngine`) tiene como objetivo identificar y agrupar flashcards conceptualmente redundantes. 

### A. Infraestructura y Mapeo Vectorial
* **Modelos Utilizados**: Soporta un pool de modelos de embedding configurables (por defecto `gemini-embedding-2` y `text-embedding-004`), con una dimensión vectorial estándar de 768 dimensiones.
* **Estrategia de Rotación y Tolerancia**: Para mitigar límites de cuota (HTTP 429) o fallos de servicio (HTTP 503), el motor implementa una matriz de reintento que rota secuencialmente a través de las llaves API disponibles y los modelos definidos.
* **Persistencia en Caché**: Los vectores resultantes se almacenan en memoria referenciados por el identificador único de la tarjeta (`_id`). Esto garantiza que ninguna tarjeta sea procesada por el servicio de embeddings más de una vez por sesión de análisis.

### B. Cálculo de Similitud Coseno
La afinidad semántica entre dos tarjetas $i$ y $j$ se calcula mediante la similitud coseno entre sus vectores de embedding representativos:

$$\text{Similitud}(u, v) = \frac{u \cdot v}{\|u\| \|v\|} = \frac{\sum_{k=1}^{n} u_k v_k}{\sqrt{\sum_{k=1}^{n} u_k^2} \sqrt{\sum_{k=1}^{n} v_k^2}}$$

### C. Lógica de Ponderación Dual e Interferencia
El sistema evalúa la redundancia tanto en las preguntas (anversos) como en las respuestas (reversos) asignando los siguientes pesos específicos:
* **Peso del Anverso ($W_F$)**: $0.6$
* **Peso del Reverso ($W_B$)**: $0.4$

Para cada par de tarjetas, se determinan tres valores de similitud:
1. $S_{\text{front}}$: Similitud coseno entre los embeddings de las preguntas.
2. $S_{\text{back}}$: Similitud coseno entre los embeddings de las respuestas (si ambas existen).
3. $S_{\text{combined}}$: Combinación lineal ponderada:

$$S_{\text{combined}} = 0.6 \cdot S_{\text{front}} + 0.4 \cdot S_{\text{back}}$$

### D. Criterio de Decisión OR
Una tarjeta $j$ se clasifica como duplicada de una tarjeta base $i$ si se cumple **cualquiera** de las siguientes condiciones (operador lógico OR):

$$\left(S_{\text{front}} \ge \theta\right) \lor \left(S_{\text{back}} \ge \theta\right) \lor \left(S_{\text{combined}} \ge \theta\right)$$

Donde $\theta$ representa el umbral de deduplicación (por defecto $\theta = 0.88$). Las tarjetas que cumplen este criterio se agrupan en clusters de interferencia, aislando una única tarjeta representativa y marcando las demás como duplicadas para su revisión o descarte.

---

## 2. Metodología de Calidad Pedagógica (Métrica QYI) y Grafo EduKG

El indicador de calidad y rendimiento pedagógico (**Quality and Yield Index - QYI**) evalúa la aptitud educativa de un conjunto de tarjetas generadas a partir de un texto fuente.

### A. Formulación Matemática de QYI
El valor QYI global se calcula como una combinación lineal ponderada de tres sub-índices normalizados en el rango $[0.0, 1.0]$:

$$\text{QYI} = \alpha \Phi_Q + \beta \Phi_Y + \gamma \Phi_C$$

Bajo la configuración estándar del sistema, los coeficientes se establecen en:
* $\alpha = 0.3$ (Peso del sub-índice de calidad fáctica)
* $\beta = 0.4$ (Peso del sub-índice de yield instruccional)
* $\gamma = 0.3$ (Peso del sub-índice de cobertura topológica)

#### 1. Sub-índice de Calidad Fáctica ($\Phi_Q$)
Representa el promedio de las puntuaciones de calidad individual ($Q_i$) otorgadas a las $M$ tarjetas evaluadas:

$$\Phi_Q = \frac{1}{M} \sum_{i=1}^{M} Q_i$$

Donde $Q_i \in [0.0, 1.0]$ se obtiene normalizando la evaluación del agente evaluador (escala original de 0 a 10).

#### 2. Sub-índice de Yield Instruccional ($\Phi_Y$)
Mide la eficiencia del conjunto de tarjetas para capturar los puntos neurálgicos del tema sin generar ruido cognitivo. Se define como la proporción de tarjetas clasificadas como de "Alto Impacto" ($m^*$) respecto al total de tarjetas ($M$):

$$\Phi_Y = \frac{m^*}{M}$$

#### 3. Sub-índice de Cobertura Topológica ($\Phi_C$)
Mide si las tarjetas de alto impacto cubren los conceptos estructuralmente más importantes del contenido. Se calcula utilizando las puntuaciones de PageRank obtenidas sobre el Grafo de Conocimiento Educativo (EduKG):

$$\Phi_C = \frac{1}{m^*} \sum_{i=1}^{M} \mathbb{I}(Y_i) \cdot \text{Percentil}(\text{PR}(\text{Concepto}_i))$$

Donde:
* $\mathbb{I}(Y_i)$ es una función indicadora que vale $1$ si la tarjeta $i$ es de alto impacto, y $0$ en caso contrario.
* $\text{PR}(\text{Concepto}_i)$ es el valor de PageRank del concepto asociado a la tarjeta $i$.
* $\text{Percentil}(x)$ calcula la posición relativa (rango percentil empírico) del valor de PageRank frente a todos los nodos del grafo para evitar sesgos de escala:

$$\text{Percentil}(\text{PR}_k) = \frac{1}{|V|} \sum_{v \in V} \mathbb{I}(\text{PR}_v \le \text{PR}_k)$$

### B. Construcción y Análisis del Grafo de Conocimiento Educativo (EduKG)
La topología del conocimiento se modela mediante la clase `EduKGRanker` usando la biblioteca `networkx`:
1. **Nodos ($V$)**: Representan los conceptos clave identificados en el texto original.
2. **Aristas ($E$)**: Se añaden conexiones dirigidas basadas en relaciones lógicas explícitas o, de manera supletoria, aristas no dirigidas basadas en co-ocurrencia semántica (conceptos que aparecen en el mismo párrafo). El peso de la arista incrementa en $1.0$ con cada co-ocurrencia.
3. **Conversión y PageRank**: El grafo de co-ocurrencia se convierte a un grafo no dirigido para capturar tanto conceptos puente (alta centralidad de intermediación) como conceptos específicos de alta densidad de enlaces. Sobre este grafo se ejecuta el algoritmo de PageRank con un factor de amortiguación (damping factor) $\text{alpha} = 0.85$.

### C. Configuración del Agente Watchdog
La calidad $Q_i$, el nivel cognitivo de la taxonomía de Bloom (1: Recordar, 2: Entender, 3: Aplicar, 4: Analizar/Evaluar) y la pertenencia a alto impacto ($Y_i$) de cada tarjeta son dictaminados de forma automatizada por un LLM configurado como evaluador pedagógico ("Profesor Juez"), utilizando el siguiente prompt estandarizado:

> **Rol**: Profesor Juez experto en pedagogía cognitiva.
> **Instrucción**: Evalúa las flashcards generadas a partir del texto proporcionado. Para cada flashcard, asigna:
> 1. Calidad (0-10): Precisión fáctica y claridad.
> 2. Nivel Bloom (1-4): 1=Recordar, 2=Entender, 3=Aplicar, 4=Analizar/Evaluar.
> 3. Alto Impacto (S/N): ¿Es una pregunta esencial que cubre un concepto clave?
> 
> *Salida requerida*: Únicamente una lista en formato JSON: `[{"id": 0, "calidad": 8, "bloom": 2, "impacto": "S"}, ...]`

* **Acción ante Umbral de Aprobación**:
  * $\text{QYI} \ge 0.80$: Estado **Excelente** (mazo apto para exportación directa).
  * $0.60 \le \text{QYI} < 0.80$: Estado **Mejorable** (sugerencia de revisión).
  * $\text{QYI} < 0.60$: Estado **Baja Calidad** (las tarjetas se retienen en la sala de espera para regeneración o descarte).

---

## 3. Especificación del Prompt "Examen Fiel (QYA)"

El set de configuración de generación de flashcards bajo el modo "Examen Fiel" (`exam_faithful`) está diseñado específicamente para contextos de evaluación y certificación formal. A diferencia de otros modos heurísticos, restringe severamente las capacidades creativas del modelo de lenguaje para evitar alucinaciones, favoreciendo la exactitud y la fidelidad documental.

### A. Texto Íntegro del Prompt de Sistema

```text
Rol: Extractor de Ideas Principales para Estudio de Certificación Profesional.

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
Fórmulas y Variables: Toda fórmula matemática, código en línea o variable aislada debe estar encerrada usando formato MathJax de Anki, empezando exactamente con \( y terminando con \). Ejemplo: \( x^2 = 4 \).

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
NO agregues introducciones, confirmaciones, resúmenes ni conclusiones.
```

### B. Análisis de Directivas de Control en "Examen Fiel"
1. **Límite de Densidad Conceptual**: La directiva `SI el material tiene menos de 3 conceptos aplicables y verificables → devuelve #SIN_CONTENIDO_SUFICIENTE` actúa como un interruptor de seguridad de umbral de información, impidiendo que el motor genere tarjetas de baja utilidad o redundantes sobre secciones de texto vacías o meramente administrativas.
2. **Cero Inferencia**: La exclusión de extrapolaciones y la prohibición explícita de usar el conocimiento interno de entrenamiento del LLM reduce las discrepancias fácticas al 0%, limitando la generación estrictamente al contexto empírico suministrado (`{texto_ocr}`).
3. **Formateo Matemático (MathJax)**: El requerimiento de usar las etiquetas de escape de Anki `\\(` y `\\)` para variables y ecuaciones facilita el renderizado uniforme por el motor de tarjetas WebKit de Anki.
