# **Arquitectura y Optimización de Sistemas de Aprendizaje Activo: Metodologías Avanzadas de Destilación Pedagógica y Priorización Cognitiva**

## **El dilema de la densidad cognitiva y la sobreproducción de reactivos**

El desarrollo de sistemas automáticos de generación de preguntas (AQG) basados en modelos de lenguaje de gran tamaño (LLMs) y representaciones vectoriales ha transformado la ingeniería del aprendizaje y la tutoría inteligente.1 Sin embargo, la conversión lineal de material docente —como transcripciones de clases, lecturas técnicas o videos extensos— en unidades de práctica activa (flashcards) presenta un desafío crítico de escalabilidad y sobrecarga cognitiva.4 Un procesamiento lineal estandarizado genera un promedio de 4 a 9 flashcards por cada 1 a 3 minutos de transcripción.4 Aplicado a un video de dos horas de duración, este método produce entre 160 y 720 tarjetas, un volumen inviable para el repaso diario bajo un esquema clásico de repetición espaciada.4  
La reducción de ruido mediante la eliminación de duplicados semánticos basados en embeddings resuelve la redundancia léxica y sintáctica, pero resulta ciega ante el valor estratégico de la información.9 El agrupamiento (clustering) semántico tradicional mitiga la repetición literal de conceptos, pero preserva reactivos técnicamente correctos y únicos que carecen de impacto práctico.10 En contextos de alta exigencia —como exámenes competitivos, hackatones, entrevistas técnicas o la formulación de marcos teóricos—, la memorización de datos efímeros o hechos aislados no genera transferencia de aprendizaje ni habilidades para la resolución de problemas en el mundo real.12  
La desmotivación y el abandono de los sistemas de estudio activo ocurren cuando la carga cognitiva extrínseca —el esfuerzo mental invertido en navegar, formatear y repasar tarjetas irrelevantes o de baja dificultad conceptual— supera el beneficio pedagógico percibido o germane load, el cual está orientado a la construcción de esquemas mentales sólidos.6  
La optimización de un generador de flashcards avanzado exige trascender la mera síntesis de información.16 El objetivo primordial debe ser maximizar la densidad cognitiva útil por tarjeta, asegurando la menor cantidad posible de reactivos con la mayor tasa de aplicabilidad futura y retención a largo plazo.8

## **Análisis comparativo de enfoques en plataformas comerciales y de investigación**

Para resolver el problema del volumen excesivo de tarjetas, los sistemas comerciales y los proyectos de investigación han evolucionado desde la captura pasiva de notas hacia arquitecturas de filtrado y priorización activa.17

| Plataforma / Paper | Enfoque de Priorización | Mecanismo de Reducción de Volumen | Manejo de Granularidad | Limitaciones Técnicas |
| :---- | :---- | :---- | :---- | :---- |
| **SuperMemo (Incremental Reading)** 8 | Cola de prioridad dinámica (0% a 100%) asignada por el usuario o heredada de extractos parentales.7 | Auto-posposición del exceso de material pendiente, descartando activamente ítems de baja prioridad en flujos sobrecargados.7 | Descomposición manual o guiada de textos en fragmentos (extractos) y conversión secuencial a clozes.8 | Curva de aprendizaje extremadamente empinada y alta dependencia de la intervención manual del usuario.8 |
| **Anki Ecosystem** 20 | Algoritmo SM-2 modificado enfocado en la probabilidad de olvido; la prioridad es reactiva al historial de respuestas.11 | Ninguno nativo en la fase de generación; la reducción del volumen de creación depende de la moderación manual del usuario.20 | Formato atómico (un concepto por tarjeta) impulsado por directrices de diseño del usuario.11 | Carece de filtros conceptuales automáticos; el usuario sufre el cuello de botella de la creación manual.20 |
| **Quizlet & RemNote** 4 | Generación automática basada en plantillas asociadas a conceptos clave destacados por el usuario en sus notas.4 | Filtrado por coincidencia léxica directa y selección de términos clave definidos en glosarios.4 | Mapeo directo entre la toma de notas jerárquica y la creación instantánea de flashcards en un único flujo.20 | Propensión a generar tarjetas de simple memorización o definición literal, ignorando niveles cognitivos complejos.11 |
| **NotebookLM (Google)** 20 | Anclaje estricto a las fuentes proporcionadas por el usuario para evitar alucinaciones.20 | Extracción selectiva de guías de estudio y síntesis conceptual guiada por el modelo fundacional.5 | Generación de resúmenes estructurados y tarjetas basadas únicamente en secciones explícitas del texto.20 | Ciego a las señales acústicas de la clase y a la frecuencia de preguntas externas fuera del documento subido.23 |
| **MemoAI** 12 | Habilidades de IA orientadas: recuperación de hechos clínicos, viñetas de casos y análisis de exámenes previos.12 | Segmentación orientada a objetivos específicos del examen de certificación.12 | Tarjetas adaptadas a perfiles de alta densidad (vignettes complejas frente a preguntas de evocación directa).12 | Requiere bases de datos estructuradas de exámenes previos para guiar el filtrado semántico.12 |
| **ReQUESTA Framework** 24 | Planificación multiagente basada en metas explícitas de diversidad cognitiva (Bloom).24 | Orquestación híbrida de agentes para unificar, simplificar y reducir distractores inconsistentes.26 | Segmentación espacial de chunks de texto para mantener la coherencia contextual e inferencial.26 | Incremento significativo en la latencia de inferencia y coste de llamadas a APIs de LLMs.28 |

## **Heurísticas pedagógicas para la destilación del conocimiento**

La distinción entre información formalmente correcta y cognitivamente valiosa se fundamenta en principios consolidados de la psicología cognitiva y las ciencias de la educación.14 Para maximizar la densidad de aprendizaje útil, los sistemas automáticos deben estructurar la priorización semántica empleando heurísticas de diseño instruccional que filtren el material irrelevante y acentúen los puntos críticos de transferencia conceptual.11

### **La taxonomía de Bloom y el diseño de dificultades deseables**

Los sistemas AQG estándar operan principalmente en los niveles inferiores de la taxonomía de Bloom (Recordar y Comprender).31 Para inducir una retención robusta, es indispensable estructurar los reactivos bajo el principio de "dificultades deseables".14 Esto implica retar al estudiante a recuperar información de manera esforzada, lo cual incrementa la fuerza de almacenamiento (storage strength) a largo plazo, a pesar de que la facilidad de recuperación inmediata (retrieval strength) disminuya transitoriamente.34  
El framework *DeepQuestion* demuestra que la reconfiguración de preguntas simples en problemas de aplicación del mundo real mediante técnicas de conversión a escenarios (Question-to-Scenario o Q2S) y de diseño de instrucciones inversas (Question-to-Instruction o Q2I) aumenta drásticamente la discriminación y la profundidad diagnóstica del reactivo, forzando la resolución adaptativa y la transferencia de conocimiento.30

### **Conceptos umbral (Threshold Concepts) y cuellos de botella conceptuales**

Ciertos conceptos dentro de una disciplina actúan como "conceptos umbral".37 Se caracterizan por ser transformadores (cambian de manera irreversible la comprensión del dominio), integradores (revelan la interrelación oculta entre saberes aislados) y limitantes (su incomprensión bloquea todo avance posterior en el plan de estudios).37  
La identificación de estos nodos críticos permite depurar las flashcards de soporte o complementarias y concentrar el esfuerzo del usuario en los puntos de articulación teórica de alta rentabilidad intelectual.16

### **El principio de Pareto (20/80) y la minimización de la carga cognitiva**

Aproximadamente el 20% de los principios centrales de un tema explican el 80% de sus aplicaciones e implicaciones prácticas.19 El sistema debe identificar este núcleo conceptual mediante el modelado de dependencias.38 Para preservar la viabilidad atencional, se debe aplicar la teoría de la reducción de la carga cognitiva extrínseca.11  
Esto exige que las flashcards mantengan un formato de respuesta única y directa (principio de información mínima), relegando la complejidad adicional, los matices históricos o las variaciones marginales a footers o notas aclaratorias de lectura opcional, evitando sobrecargar la memoria de trabajo del alumno durante el proceso de recuperación activa.11

┌────────────────────────────────────────────────────────┐  
│                   DISEÑO DE LA TARJETA                 │  
├────────────────────────────────────────────────────────┤  
│ PREGUNTA: Crisp prompt con una sola variable \[11\]   │  
├────────────────────────────────────────────────────────┤  
│ RESPUESTA: Definición atómica, núcleo del esquema \[11\]│  
├────────────────────────────────────────────────────────┤  
│ FOOTNOTE: Información complementaria y contextual      │  
│           (No interfiere en la recuperación activa     │  
│           pero mitiga vacíos de comprensión) \[11\]  │  
└────────────────────────────────────────────────────────┘

## **Modelado estructural y centralidad conceptual basada en grafos**

La evaluación objetiva de la relevancia de un concepto dentro de un corpus educativo requiere un análisis de red.9 La construcción de un Grafo de Conocimiento Educativo (EduKG) o Grafo de Conocimiento del Curso (CKG) organiza el contenido textual o las transcripciones en un mapa topológico.9 En este grafo, los nodos representan conceptos discretos, y las aristas denotan relaciones semánticas de pertenencia, asociación o dependencia de prerrequisitos.9

### **Extracción de relaciones de prerrequisito semántico**

Para determinar el flujo jerárquico de conceptos, se implementan redes neuronales sobre grafos (GNN) con capas de atención que analizan pares de conceptos ![][image1] para clasificarlos en tres categorías: ![][image2] es prerrequisito de ![][image3], ![][image2] es consecuencia (outcome) de ![][image3], o no existe relación jerárquica directa entre ambos.39  
En paralelo, se utiliza el enfoque *Graph-Guided Concept Selection* (G2ConS) para resolver el problema de la contaminación semántica de los embeddings de bloques de texto (chunks) tradicionales.10 Dado que un párrafo de 500 palabras suele contener múltiples conceptos cruzados, se construyen embeddings específicos para cada concepto a nivel de oración.10 Para un concepto ![][image4], se aíslan todas las oraciones del corpus en las que aparece, denotadas por ![][image5], y se calcula su representación vectorial ![][image6] como el promedio de sus embeddings oracionales 10:  
![][image7]  
Donde ![][image8] representa la función de codificación semántica basada en un transformador de oraciones.10

### **Puntuación por centralidad y PageRank Personalizado**

Una vez construido el grafo con los conceptos umbral y de soporte, se calcula su centralidad utilizando una versión adaptada y personalizada del algoritmo PageRank.41 El PageRank convencional asigna pesos de importancia estocástica basados en la interconectividad de la red.41 En el contexto educativo, se introduce una matriz de adyacencia estocástica ![][image9] que modela las relaciones de prerrequisito y co-ocurrencia semántica calificada entre los nodos.42 Para incorporar sesgos de relevancia académica externos, se parametriza el vector de personalización o de "teletransporte" ![][image10], de modo que no sea uniforme, sino proporcional a indicadores de interés estratégico.42  
El vector de centralidad de PageRank Personalizado ![][image11] se computa resolviendo el sistema lineal 42:  
![][image12]  
Donde $\\alpha \\in $ representa el factor de amortiguación (configurado típicamente en ![][image13]), el cual mitiga el efecto de callejones sin salida (dead-ends) y trampas de bucles (spider-traps) que distorsionan las puntuaciones de importancia estructural en redes acíclicas dirigidas.42 Los nodos que exhiben las puntuaciones más elevadas de centralidad topológica representan los puntos críticos o "conceptos puente" que sostienen la arquitectura lógica del dominio de conocimiento y son seleccionados prioritariamente para la generación de flashcards.9

## **Análisis retórico y prosódico de la transcripción de audio**

El procesamiento de transcripciones de audio provenientes de clases magistrales u otras fuentes educativas presenta el desafío de depurar el lenguaje oral coloquial, el cual difiere sustancialmente del lenguaje escrito académico.47 Sin embargo, la señal acústica y la estructura discursiva del orador contienen señales pedagógicas explícitas que indican qué secciones del contenido poseen la mayor densidad de información o valor de examen.23

### **Segmentación acústica y estándares de transcripción**

Para preservar la semántica del discurso sin incorporar ruidos que afecten la calidad de la inferencia, se preprocesa el audio mediante un esquema híbrido de transcripción.23 Se utiliza un estándar de Transcripción Verbatim Limpia (Clean Verbatim o CV).47 Este estándar elimina sonidos puramente dubitativos o de hesitación acústica (como *"eh"*, *"uh"*, *"erm"*) 47, pero conserva marcadores de discurso, rellenos estructurales y muletillas que reflejan el énfasis intencional y la postura retórica del instructor.47

### **Análisis prosódico y detección de énfasis del docente**

El framework STREAM integra un motor de análisis acústico que procesa paralelamente el flujo de audio para extraer parámetros de prosodia, detectando las fluctuaciones que el docente realiza de manera inconsciente o deliberada para estructurar su exposición 23:

* **Entonación y tono (Pitch):** Variaciones abruptas en la frecuencia fundamental de la voz (![][image14]) delimitan la introducción de nuevos conceptos o la transición hacia principios nodales de la materia.23  
* **Velocidad de articulación (Speak-rate):** Una ralentización significativa de la velocidad del habla indica típicamente la enunciación de definiciones abstractas, dictado de fórmulas o conclusiones evaluables.23  
* **Estructura de pausas:** Silencios prolongados antes o después de una frase actúan como marcadores acústicos de atención, permitiendo que el estudiante procese cognitivamente la información.23  
* **Intensidad vocal y estrés:** Picos de presión sonora localizados en términos clave denotan prioridad instruccional.23

### **Extracción de marcadores léxicos y análisis retórico del transcrito**

Paralelamente, se ejecuta un análisis retórico de la transcripción para catalogar "marcadores léxicos de énfasis" mediante búsqueda de patrones sintácticos y expresiones típicas de instrucción.23 El sistema asigna un peso de relevancia incremental a los segmentos de texto asociados a oraciones que contienen expresiones categóricas tales como: *"esto es fundamental"*, *"es crucial comprender que"*, *"presten atención a esto"*, *"esta pregunta es recurrente en exámenes"*, o *"lo más importante aquí es"*.23  
Estas ponderaciones prosódicas y retóricas actúan como moduladores de entrada para el cálculo de la Ganancia de Información Esperada (EIG) en el proceso de selección de reactivos candidatas.48 Si un bloque de contenido posee una alta densidad de señales de énfasis físico por parte del instructor, se incrementa el peso del vector de personalización de ese concepto en el cálculo del PageRank, forzando la extracción prioritaria de tarjetas sobre ese nodo.23

## **Arquitectura híbrida del sistema multiagente de destilación**

Para instrumentar estas heurísticas pedagógicas y análisis topológicos de forma escalable, se diseña un pipeline multiagente híbrido que integra componentes algorítmicos basados en reglas con agentes de razonamiento profundo impulsados por LLMs.24 El sistema opera bajo un paradigma de "sobregeneración inicial seguida de destilación pedagógica rigurosa".26

┌────────────────────────────────────────────────────────────────────────────────────────┐  
│                        FASE I: INGESTIÓN Y ANÁLISIS ACÚSTICO                           │  
│                                                                                        │  
│ \[Audio de Entrada\] ──► Engine ASR (Clean Verbatim)  ─────────┐                  │  
│                    ──► Prosody Extraction (Pitch/Speak-rate)  ├─► Transcripción  │  
│                                                                     │   Enriquecida    │  
│ ──► OCR & Visual Segment Align  ───────┘                  │  
└───────────────────────────────────────────────────┬────────────────────────────────────┘  
                                                    │  
                                                    ▼  
┌────────────────────────────────────────────────────────────────────────────────────────┐  
│                        FASE II: MODELADO TOPOLÓGICO DE LA RED                          │  
│                                                                                        │  
│ 1\. Extracción de conceptos a nivel de oración (G2ConS).                        │  
│ 2\. Construcción de relaciones de prerrequisito (GNN Edge Attention).       │  
│ 3\. Cálculo de centralidad mediante PageRank Personalizado (v biased by emphasis).│  
└───────────────────────────────────────────────────┬────────────────────────────────────┘  
                                                    │  
                                                    ▼  
┌────────────────────────────────────────────────────────────────────────────────────────┐  
│                        FASE III: PIPELINE MULTIAGENTE (ReQUESTA)                       │  
│                                                                                        │  
│ Preprocessor Agent (Segmentación limpia de Chunks de Texto)                     │  
│                                                   │                                    │  
│                                                   ▼                                    │  
│ Planner Agent (Establece distribución según Taxonomía de Bloom) \[26, 32\]          │  
│                                                   │                                    │  
│       ┌───────────────────────────┼───────────────────────────┐                        │  
│       ▼                           ▼                           ▼                        │  
│ Recall Generator           Scenario Generator (Q2S)    Instruction Gen (Q2I)           │  
│ (Conceptos Atómicos)       (Casos Prácticos)           (Diseño Inverso)                 │  
│                                                      │  
│       └───────────────────────────┬───────────────────────────┘                        │  
│                                   │                                                    │  
│                                   ▼                                                    │  
│ Evaluator Agent / Teacher Judge (Loop de Refinamiento y Puntuación) \[26, 32\]      │  
│                                   │                                                    │  
│                                   ▼                                                    │  
│ Formatter Agent & Option-Shortening Module (Ajuste Estructural)                 │  
└───────────────────────────────────────────────────┬────────────────────────────────────┘  
                                                    │  
                                                    ▼  
                                   

### **1\. Preprocesador (Preprocessor Agent)**

Un agente basado en reglas que procesa la transcripción enriquecida utilizando spaCy para segmentar el texto en unidades contextuales coherentes (chunks).26 El preprocesador asocia a cada chunk los metadatos de tiempo, fuentes bibliográficas, correlación de diapositivas y las métricas prosódicas agregadas.23

### **2\. Planificador (Planner Agent)**

Un agente LLM de alta capacidad de razonamiento que evalúa el corpus completo y el grafo de conocimiento estructurado.26 Su función es definir el plan estratégico de la sesión, especificando cuáles conceptos umbral y cuellos de botella conceptuales deben abordarse, y determinando la distribución óptima de tarjetas en función de los diferentes niveles de la taxonomía de Bloom.26

### **3\. Generadores Especializados (Generator Agents)**

En lugar de utilizar una sola instrucción masiva, el sistema divide la creación de reactivos en tres agentes independientes que operan en paralelo para garantizar la diversidad cognitiva 24:

* **Recall Generator:** Diseña flashcards simplificadas enfocadas en definiciones y principios unívocos.26  
* **Scenario Generator (Q2S):** Implementa el método de conversión a escenarios.30 Toma un concepto abstracto, introduce ruidos contextuales, ráfagas de datos y variables de simulación real, y formula una pregunta orientada a evaluar la aplicación del principio en un caso de estudio complejo.30  
* **Instruction Generator (Q2I):** Estructura problemas de diseño inverso.30 Formula instrucciones donde el estudiante debe deconstruir una respuesta dada o proponer las variables iniciales que conducirían de forma exacta a un resultado físico o lógico predeterminado.35

### **4\. Evaluador / Profesor Juez (Evaluator Agent / Teacher Judge)**

Este agente actúa como un filtro crítico de control de calidad.26 El LLM asume el rol de un docente experto y evalúa recursivamente cada par de pregunta-respuesta candidato contra una rúbrica rigurosa de 24 criterios de calidad pedagógica y formal 28:

* **Fidelidad de Grado de Complejidad:** ¿El reactivo exige verdaderamente razonamiento de orden superior (aplicar, analizar) o es una pregunta de memorización disfrazada? 32  
* **Aislamiento Atómico:** ¿La tarjeta respeta el principio de información mínima, o contiene múltiples variables dispersas que sobrecargan la memoria de trabajo? 11  
* **Plausibilidad de Distractores:** Si el formato incluye alternativas de opción múltiple, ¿son todas sintácticamente paralelas, plausibles e inmunes a descarte por contradicciones gramaticales obvias? 26  
* **Relevancia de Aplicación:** ¿La pregunta evalúa un concepto umbral estratégico o es mero ruido de memorización factual trivial? 11

Si el reactivo no supera la rúbrica con una puntuación mínima admisible, el evaluador genera un reporte de fallos y lo devuelve en un ciclo de corrección (loop) iterativo al agente generador correspondiente para su reconstrucción.26

### **5\. Formateador y Acortador de Opciones (Formatter & Option-Shortening Module)**

Este componente final basado en reglas estandariza el formato del deck para su importación (ej. Anki TSV o formatos de bases de datos de grafos).26 Integra un módulo de acortamiento de opciones constituido por cuatro agentes colaborativos: un analizador sintáctico que detecta redundancias léxicas entre las opciones, un determinador de longitud basado en reglas de conteo de palabras, un generador de candidatos de simplificación, y un selector de candidatos fundamentado en la preservación estricta de la distancia semántica original.26

## **Métricas de evaluación de calidad de flashcards**

Para calibrar un sistema de generación y destilación pedagógica, es fundamental evaluar la calidad conceptual y la eficiencia atencional de los decks generados mediante métricas específicas.6

| Métrica | Definición Conceptual y Criterio de Medición | Fórmula o Indicador de Cálculo | Impacto en el Aprendizaje de Alto Rendimiento |
| :---- | :---- | :---- | :---- |
| **Utilidad Pedagógica** 32 | Evaluación cualitativa de la relevancia conceptual del reactivo frente al syllabus oficial y los requerimientos del examen.32 | Clasificación Likert (1-5) evaluada por expertos o agentes de IA refinados para correlacionar con currículos estandarizados.32 | Evita la deserción atencional del estudiante al eliminar preguntas sobre datos irrelevantes o anecdóticos.6 |
| **Probabilidad de Retención** 7 | Estimación de la fuerza de almacenamiento generada tras el primer esfuerzo de recuperación deliberada de la tarjeta.34 | Inversamente proporcional a la facilidad de respuesta inmediata: ![][image15].34 | Fomenta la retención a largo plazo mediante la inducción de dificultades deseables controladas.14 |
| **Utilidad de Transferencia** 13 | Capacidad del reactivo para preparar al alumno en la resolución de problemas abstractos en contextos disímiles.14 | Puntuación basada en la divergencia de dominio entre el texto fuente de entrenamiento y el escenario de la viñeta.30 | Prepara directamente al estudiante para hackatones, entrevistas técnicas y resolución de retos inéditos.12 |
| **Densidad Semántica** 10 | Relación entre la concentración de conceptos nucleares evaluados y la longitud del texto empleado en la tarjeta.11 | ![][image16].9 | Minimiza la carga cognitiva extrínseca reduciendo el tiempo de lectura durante los repasos diarios.11 |
| **Apalancamiento Conceptual** 9 | Medida del impacto multiplicador de comprender un concepto sobre el desbloqueo de aprendizajes subsiguientes.38 | Grado de salida (out-degree) ponderado del nodo concepto en el Grafo de Conocimiento del Curso (CKG).9 | Permite una planificación de repaso ágil concentrando esfuerzos en los cuellos de botella teóricos.9 |
| **Eficiencia Cognitiva** 8 | Ratio del rendimiento de aprendizaje obtenido por cada minuto de tiempo de estudio invertido.8 | ![][image17].15 | Optimiza la rentabilidad del tiempo de estudio evitando el agotamiento mental por sobreproducción de tarjetas.6 |

## **Prototipo de implementación de referencia en Python**

El siguiente desarrollo en Python implementa de forma integrada el pipeline propuesto.24 Utiliza embeddings de oraciones para estructurar el modelo *G2ConS* 10, construye un grafo de conceptos de co-ocurrencia semántica para calcular la centralidad por *PageRank Personalizado* condicionado al énfasis acústico y de marcadores retóricos 9, y ejecuta un flujo multiagente que evalúa y califica pedagógicamente las flashcards candidatas aplicando criterios estructurados de la taxonomía de Bloom.26

Python  
import numpy as np  
import networkx as nx  
import re  
from typing import List, Dict, Any, Tuple

\# Simulación de un modelo de codificación de embeddings a nivel de oración (G2ConS)   
def encode\_sentence\_embedding(text: str) \-\> np.ndarray:  
    \# Se genera un vector sintético determinista basado en el contenido léxico para simular el codificador  
    hash\_val \= sum(ord(char) \* (idx \+ 1) for idx, char in enumerate(text))  
    np.random.seed(hash\_val % 2\*\*32)  
    vector \= np.random.randn(128)  
    return vector / np.linalg.norm(vector)

\# Representación de un concepto educativo del grafo de conocimiento   
class EducationalConcept:  
    def \_\_init\_\_(self, name: str, sentences: List\[str\], speech\_emphasis: float):  
        self.name \= name.lower().strip()  
        self.sentences \= sentences  \# Oraciones del corpus asociadas al concepto   
        self.speech\_emphasis \= speech\_emphasis  \# Puntuación prosódica y retórica calculada (STREAM)   
        self.embedding \= self.\_compute\_sentence\_level\_embedding()

    def \_compute\_sentence\_level\_embedding(self) \-\> np.ndarray:  
        \# Implementación de la metodología G2ConS de embeddings para conceptos libres de contaminación   
        if not self.sentences:  
            return np.zeros(128)  
        embeddings \= \[encode\_sentence\_embedding(s) for s in self.sentences\]  
        return np.mean(embeddings, axis=0)

\# Estructura de datos para un ítem de flashcard candidato   
class CandidateFlashcard:  
    def \_\_init\_\_(self, target\_concept: str, question: str, answer: str, claimed\_bloom\_level: str):  
        self.target\_concept \= target\_concept.lower().strip()  
        self.question \= question  
        self.answer \= answer  
        self.claimed\_bloom\_level \= claimed\_bloom\_level  \# Nivel jerárquico reclamado en el diseño 

\# Motor de análisis topológico y cálculo de prioridad pedagógica \[38, 42\]  
class KnowledgeNetworkRanker:  
    def \_\_init\_\_(self, concepts: List\[EducationalConcept\]):  
        self.concepts \= {c.name: c for c in concepts}  
        self.graph \= nx.DiGraph()

    def build\_dependency\_graph(self, similarity\_threshold: float \= 0.50):  
        \# Cada concepto en el EduKG se añade como un nodo inicializando su peso según su énfasis de audio \[9, 23\]  
        for name, concept in self.concepts.items():  
            self.graph.add\_node(name, weight=concept.speech\_emphasis)

        \# Análisis de pares de conceptos para mapear relaciones basadas en distancia de embeddings \[10, 39\]  
        names \= list(self.concepts.keys())  
        for i in range(len(names)):  
            for j in range(i \+ 1, len(names)):  
                c1 \= self.concepts\[names\[i\]\]  
                c2 \= self.concepts\[names\[j\]\]  
                  
                \# Similitud de coseno entre los embeddings a nivel de oración de G2ConS   
                similarity \= float(np.dot(c1.embedding, c2.embedding))  
                if similarity \> similarity\_threshold:  
                    \# Se simula la precedencia temporal o jerárquica del plan de estudios   
                    \# En producción se valida mediante extracción de dependencias por GNN   
                    self.graph.add\_edge(names\[i\], names\[j\], weight=similarity)

    def calculate\_personalized\_pagerank(self) \-\> Dict\[str, float\]:  
        if len(self.graph.nodes) \== 0:  
            return {}  
          
        \# Construcción del vector de personalización 'v' condicionado al énfasis prosódico/retórico   
        total\_emphasis \= sum(c.speech\_emphasis for c in self.concepts.values())  
        personalization\_vector \= {}  
        for name, concept in self.concepts.items():  
            if total\_emphasis \> 0:  
                personalization\_vector\[name\] \= concept.speech\_emphasis / total\_emphasis  
            else:  
                personalization\_vector\[name\] \= 1.0 / len(self.concepts)  
                  
        \# Resolución matemática del PageRank Personalizado para localizar conceptos umbral \[37, 42\]  
        pagerank\_scores \= nx.pagerank(  
            self.graph,  
            alpha=0.85,  \# Factor de amortiguación para evitar spider-traps \[43, 44\]  
            personalization=personalization\_vector,  
            weight='weight'  
        )  
        return pagerank\_scores

\# Agente Evaluador y Profesor Juez (Teacher Judge Agent) \[26, 32\]  
class TeacherJudgeAgent:  
    def \_\_init\_\_(self):  
        \# Rúbrica heurística automatizada para evaluar la calidad didáctica \[11, 32\]  
        self.rules \= {  
            "atomic\_constraint": "Una flashcard eficaz debe aislar una única variable lógica para evitar fatiga.",  
            "bloom\_fidelity": "El reactivo debe forzar un esfuerzo de recuperación coherente con su nivel cognitivo.\[32, 34\]",  
            "context\_noise\_check": "En el nivel de aplicación, se debe validar que el escenario no sea una simple repetición léxica."  
        }

    def evaluate\_item(self, card: CandidateFlashcard, centrality\_score: float) \-\> Dict\[str, Any\]:  
        \# Simulación de la evaluación cognitiva de un LLM aplicando la rúbrica sobre el reactivo \[26, 32\]  
        pedagogical\_score \= 0.0  
        evaluation\_logs \=  
        is\_approved \= True

        \# Heurística 1: Ponderar la centralidad del concepto en la topología de la asignatura   
        if centrality\_score \> 0.20:  
            pedagogical\_score \+= 0.40  
            evaluation\_logs.append("Aprobado: El concepto es un nodo umbral o puente con alto apalancamiento.\[37, 38\]")  
        else:  
            pedagogical\_score \+= 0.15  
            evaluation\_logs.append("Sugerencia: Concepto de soporte secundario; volumen restringido de tarjetas.\[9, 19\]")

        \# Heurística 2: Penalización por sobrecarga en la memoria de trabajo   
        word\_count\_answer \= len(card.answer.split())  
        if word\_count\_answer \> 25:  
            pedagogical\_score \-= 0.20  
            evaluation\_logs.append("Advertencia: Respuesta demasiado extensa. Afecta negativamente la carga cognitiva extrínseca.")  
        else:  
            pedagogical\_score \+= 0.20

        \# Heurística 3: Validación del rigor del nivel de Bloom reclamado   
        if card.claimed\_bloom\_level in \["Applying", "Analyzing", "Evaluating"\]:  
            \# El nivel de aplicación exige escenarios prácticos (Q2S); se verifica que no sea una mera definición   
            if any(indicator in card.question.lower() for indicator in \["definir", "qué es", "cuál es el significado"\]):  
                is\_approved \= False  
                pedagogical\_score \-= 0.30  
                evaluation\_logs.append("Rechazado: Inconsistencia en nivel de Bloom. El reactivo alega nivel de aplicación pero pide mera evocación de definición.")  
            else:  
                pedagogical\_score \+= 0.35  
                evaluation\_logs.append("Aprobado: El diseño implementa correctamente una dificultad deseable contextualizada.\[30, 34\]")  
        else:  
            \# Preguntas básicas de evocación (Recall) tienen menor peso estratégico de cara al examen \[32, 33\]  
            pedagogical\_score \+= 0.10  
            evaluation\_logs.append("Aprobado: Tarjeta estándar de asimilación léxica de baja complejidad.")

        \# Clasificación final del reactivo   
        if pedagogical\_score \>= 0.65 and is\_approved:  
            classification \= "Core (Esencial)"  
        elif pedagogical\_score \>= 0.45 and is\_approved:  
            classification \= "Supporting (Soporte)"  
        elif pedagogical\_score \>= 0.25 and is\_approved:  
            classification \= "Optional (Opcional)"  
        else:  
            classification \= "Trivia/Noise (Descartado)"  
            is\_approved \= False

        return {  
            "approved": is\_approved,  
            "final\_pedagogical\_score": max(0.0, min(1.0, pedagogical\_score)),  
            "classification": classification,  
            "logs": evaluation\_logs  
        }

\# Pipeline integrado de destilación de alto impacto   
class HighImpactDistillationPipeline:  
    def \_\_init\_\_(self, concepts: List\[EducationalConcept\], candidates: List\[CandidateFlashcard\]):  
        self.ranker \= KnowledgeNetworkRanker(concepts)  
        self.candidates \= candidates  
        self.judge \= TeacherJudgeAgent()

    def execute\_pipeline(self) \-\> List\]:  
        \# Fase I: Construcción del grafo de conocimiento y PageRank Personalizado   
        self.ranker.build\_dependency\_graph()  
        pagerank\_scores \= self.ranker.calculate\_personalized\_pagerank()

        distilled\_deck \=

        \# Fase II: Evaluación iterativa multiagente y asignación de valor pedagógico \[26, 32\]  
        for card in self.candidates:  
            concept\_name \= card.target\_concept  
            centrality \= pagerank\_scores.get(concept\_name, 0.0)

            evaluation \= self.judge.evaluate\_item(card, centrality)

            if evaluation\["approved"\]:  
                distilled\_deck.append({  
                    "concept": card.target\_concept,  
                    "question": card.question,  
                    "answer": card.answer,  
                    "bloom\_level": card.claimed\_bloom\_level,  
                    "centrality": centrality,  
                    "utility\_score": evaluation\["final\_pedagogical\_score"\],  
                    "classification": evaluation\["classification"\],  
                    "logs": evaluation\["logs"\]  
                })

        \# Fase III: Ordenación por prioridad cognitiva (cola de prioridad de SuperMemo/MemoAI) \[7, 12\]  
        distilled\_deck.sort(key=lambda x: x\["utility\_score"\], reverse=True)  
        return distilled\_deck

\# Ejemplo de ejecución con transcripción enriquecida de una lección técnica   
if \_\_name\_\_ \== "\_\_main\_\_":  
    \# Ingestión de conceptos educacionales enriquecidos acústicamente \[9, 23\]  
    raw\_concepts \=",  
                "Las llamadas a funciones recursivas se administran en la pila de ejecución del sistema operativo."  
            \],  
            speech\_emphasis=1.2  \# Marcador acústico moderado de pitch   
        ),  
        EducationalConcept(  
            name="Algoritmo DFS (Depth-First Search)",  
            sentences=",  
                "Para implementar DFS de forma iterativa y controlar el estado de exploración es mandatorio utilizar una pila."  
            \],  
            speech\_emphasis=2.5  \# El orador repitió este principio dos veces con entonación elevada   
        ),  
        EducationalConcept(  
            name="Ordenamiento Topológico (Topological Sort)",  
            sentences=,  
            speech\_emphasis=0.8  \# Concepto avanzado de cierre sin picos acústicos anómalos  
        )  
    \]

    \# Flashcards candidatas generadas en la fase inicial de sobreproducción   
    raw\_candidates \=  
        CandidateFlashcard(  
            target\_concept="Algoritmo DFS (Depth-First Search)",  
            question="Se requiere diseñar el motor de navegación para un vehículo autónomo que debe mapear un laberinto profundo con pasillos estrechos de salida única. ¿Qué estructura de datos de soporte utiliza el algoritmo DFS para rastrear la ruta activa y cómo impacta en el consumo de memoria del vehículo?",  
            answer="Utiliza una pila (LIFO) de forma implícita (recursiva) o explícita (iterativa). El consumo de memoria se limita a O(D), donde D es la profundidad máxima del laberinto, siendo sumamente eficiente en túneles lineales estrechos frente a un enfoque por anchura (BFS).",  
            claimed\_bloom\_level="Applying"  
        ),  
        \# Tarjeta 2: Tarjeta defectuosa que alega nivel de aplicación pero pide definición literal   
        CandidateFlashcard(  
            target\_concept="Ordenamiento Topológico (Topological Sort)",  
            question="Definir qué es un ordenamiento topológico en un grafo acíclico y enunciar su significado básico.",  
            answer="Es una ordenación lineal de los vértices tal que para cada arista dirigida u \-\> v, el nodo u precede al nodo v en la secuencia.",  
            claimed\_bloom\_level="Applying"  \# Fallará la validación debido a inconsistencia estructural léxica \[32\]  
        ),  
        \# Tarjeta 3: Tarjeta estándar de evocación directa que excede los límites recomendados de palabras   
        CandidateFlashcard(  
            target\_concept="Pila (Stack)",  
            question="¿Cuáles son las operaciones elementales de una pila y qué implican en el manejo de memoria en tiempo de ejecución?",  
            answer="Las operaciones fundamentales son Push, que añade un elemento a la cima, y Pop, que remueve el elemento superior. En tiempo de ejecución, un desbordamiento de pila (Stack Overflow) ocurre catastróficamente si las funciones recursivas no alcanzan un caso base, provocando que el espacio reservado para la pila de ejecución en el sistema operativo agote su espacio contiguo direccionable.",  
            claimed\_bloom\_level="Understanding"  \# Será degradada o penalizada por sobrecarga de la memoria de trabajo   
        )  
    \]

    \# Ejecución del pipeline de destilación y priorización   
    pipeline \= HighImpactDistillationPipeline(concepts=raw\_concepts, candidates=raw\_candidates)  
    deck\_final \= pipeline.execute\_pipeline()

    print(f"--- RESULTADO DE LA DESTILACIÓN PEDAGÓGICA MULTIAGENTE (ReQUESTA \+ STREAM) \---")  
    print(f"Tarjetas Candidatas de Entrada: {len(raw\_candidates)}")  
    print(f"Tarjetas Aprobadas para el Deck Final: {len(deck\_final)}\\n")

    for idx, card in enumerate(deck\_final, 1):  
        print(f"RANGO \#{idx} | CONCEPTO: '{card\['concept'\].upper()}'")  
        print(f"  Pregunta: {card\['question'\]}")  
        print(f"  Respuesta: {card\['answer'\]}")  
        print(f"  Categoría Pedagógica: {card\['classification'\]} (Puntuación de Utilidad: {card\['utility\_score'\]:.2f})")  
        print(f"  Centralidad Topológica en EduKG (PageRank): {card\['centrality'\]:.4f}")  
        print(f"  Historial de Inferencia del Agente Evaluador:")  
        for log in card\['logs'\]:  
            print(f"    \- {log}")  
        print("-" \* 100)

## **Conclusiones e ingeniería de aprendizaje de alta fidelidad**

El diseño e implementación de sistemas automáticos de generación de flashcards exige un cambio de paradigma hacia la ingeniería del aprendizaje basada en el valor cognitivo de la información.1 La resolución definitiva de la sobreproducción de reactivos de bajo impacto estratégico no reside en refinar la segmentación léxica de textos o en expandir el agrupamiento básico de embeddings.9 Por el contrario, requiere el desarrollo de capas lógicas de análisis pedagógico y estructural antes, durante y después del proceso de generación de preguntas.24  
La integración de la topología de la asignatura mediante Grafos de Conocimiento Educativo (EduKGs) y el modelado de centralidades personalizadas mediante algoritmos como PageRank permiten aislar matemáticamente los conceptos umbral, distinguiendo la arquitectura teórica medular de los datos anecdóticos marginales.9 En paralelo, la decodificación de las intenciones del docente a través de metadatos prosódicos y retóricos en las transcripciones acústicas añade una dimensión de prioridad contextual crucial que enriquece la semántica pura del texto plano.23  
Finalmente, la orquestación de sistemas multiagente (como ReQUESTA) —donde un agente de planificación estructura los reactivos distribuyéndolos sistemáticamente a lo largo de la taxonomía de Bloom, y un agente docente evalúa de manera autocrítica la viabilidad de cada tarjeta aplicando rúbricas formales de carga cognitiva— garantiza que el producto final sea un deck compacto, coherente y sumamente denso en valor instruccional.11 Al sacrificar deliberadamente el volumen cuantitativo de tarjetas para maximizar el esfuerzo cognitivo controlado (dificultad deseable), se mitiga el agotamiento del usuario, se consolida la retención real a largo plazo y se dota al estudiante de herramientas lógicas reales para encarar de forma exitosa los desafíos del entorno académico y profesional contemporáneo.6

#### **Obras citadas**

1. (PDF) Comprehensive Review: Transforming Self-Education through Automatic Question Generation Technology \- ResearchGate, fecha de acceso: mayo 27, 2026, [https://www.researchgate.net/publication/400493080\_Comprehensive\_Review\_Transforming\_Self-Education\_through\_Automatic\_Question\_Generation\_Technology](https://www.researchgate.net/publication/400493080_Comprehensive_Review_Transforming_Self-Education_through_Automatic_Question_Generation_Technology)  
2. A Systematic Review and Bibliometric Analysis of Automated Multiple-Choice Question Generation \- MDPI, fecha de acceso: mayo 27, 2026, [https://www.mdpi.com/2504-2289/10/1/35](https://www.mdpi.com/2504-2289/10/1/35)  
3. A literature review of research on question generation in education \- PMC \- NIH, fecha de acceso: mayo 27, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC12453861/](https://pmc.ncbi.nlm.nih.gov/articles/PMC12453861/)  
4. AI Flashcard Generator — Create Flashcards in Seconds \- Quizgecko, fecha de acceso: mayo 27, 2026, [https://quizgecko.com/flashcard-generator](https://quizgecko.com/flashcard-generator)  
5. How to Study with AI in 2026 (Without Cheating or Wasting Time) | Laxu AI, fecha de acceso: mayo 27, 2026, [https://laxuai.com/blog/how-to-study-with-ai](https://laxuai.com/blog/how-to-study-with-ai)  
6. Balancing AI Automation and Agency for Self-Regulated Learning in SmartFlash \- arXiv, fecha de acceso: mayo 27, 2026, [https://arxiv.org/pdf/2602.14431](https://arxiv.org/pdf/2602.14431)  
7. SuperMemo: Priority queue \- Super Memory, fecha de acceso: mayo 27, 2026, [https://super-memory.com/help/priority.htm](https://super-memory.com/help/priority.htm)  
8. what is incremental reading? \- Soki, fecha de acceso: mayo 27, 2026, [https://www.soki.ai/insights/what-is-incremental-reading](https://www.soki.ai/insights/what-is-incremental-reading)  
9. Automatic Construction of Educational Knowledge Graphs: A Word Embedding-Based Approach \- MDPI, fecha de acceso: mayo 27, 2026, [https://www.mdpi.com/2078-2489/14/10/526](https://www.mdpi.com/2078-2489/14/10/526)  
10. Graph-Guided Concept Selection for Efficient Retrieval-Augmented Generation \- arXiv, fecha de acceso: mayo 27, 2026, [https://arxiv.org/html/2510.24120v1](https://arxiv.org/html/2510.24120v1)  
11. How to Make Flashcards Students Will Actually Want to Study | Brainscape Academy, fecha de acceso: mayo 27, 2026, [https://www.brainscape.com/academy/teachers-make-flashcards-students-want-study/](https://www.brainscape.com/academy/teachers-make-flashcards-students-want-study/)  
12. How I use AI skills to generate multiple flashcard decks from the same source material — workflow breakdown : r/MemoAI \- Reddit, fecha de acceso: mayo 27, 2026, [https://www.reddit.com/r/MemoAI/comments/1sfv65p/how\_i\_use\_ai\_skills\_to\_generate\_multiple/](https://www.reddit.com/r/MemoAI/comments/1sfv65p/how_i_use_ai_skills_to_generate_multiple/)  
13. \[2505.24532\] DeepQuestion: Systematic Generation of Real-World Challenges for Evaluating LLMs Performance \- arXiv, fecha de acceso: mayo 27, 2026, [https://arxiv.org/abs/2505.24532](https://arxiv.org/abs/2505.24532)  
14. Desirable Difficulties: Bjork's 5 Principles \- Structural Learning, fecha de acceso: mayo 27, 2026, [https://www.structural-learning.com/post/desirable-difficulties](https://www.structural-learning.com/post/desirable-difficulties)  
15. Flashcards Take Too Long to Make \- Mindomax, fecha de acceso: mayo 27, 2026, [https://www.mindomax.com/flashcards-take-too-long-to-make](https://www.mindomax.com/flashcards-take-too-long-to-make)  
16. AI Flashcards Template: Generate Study Decks Fast \- CogniGuide, fecha de acceso: mayo 27, 2026, [https://www.cogniguide.app/flashcards/flashcards-template](https://www.cogniguide.app/flashcards/flashcards-template)  
17. Best AI Tools for Active Recall (Not Just Summaries) | NoteFren Blog, fecha de acceso: mayo 27, 2026, [https://notefren.app/blog/best-ai-tools-for-active-recall-not-summaries](https://notefren.app/blog/best-ai-tools-for-active-recall-not-summaries)  
18. Active Recall & Flashcards: Complete Student Study Guide \- Claude, fecha de acceso: mayo 27, 2026, [https://claude.ai/public/artifacts/d4e61670-43bd-4a31-9787-2f6848d0f5d7](https://claude.ai/public/artifacts/d4e61670-43bd-4a31-9787-2f6848d0f5d7)  
19. From Spaced Repetition Systems to Open Recommender Systems \- DEV Community, fecha de acceso: mayo 27, 2026, [https://dev.to/experilearning/from-spaced-repetition-systems-to-open-recommender-systems-25ab](https://dev.to/experilearning/from-spaced-repetition-systems-to-open-recommender-systems-25ab)  
20. Best AI Flashcard Generators for Students (Ranked by Subject) \- Vertech Academy, fecha de acceso: mayo 27, 2026, [https://www.vertechacademy.com/blog/best-ai-flashcard-generators-students](https://www.vertechacademy.com/blog/best-ai-flashcard-generators-students)  
21. SuperMemo: Incremental reading \- Super Memory, fecha de acceso: mayo 27, 2026, [https://super-memory.com/archive/help15/read.htm](https://super-memory.com/archive/help15/read.htm)  
22. Current status of “incremental reading” in Anki? (With Zotero question) \- Reddit, fecha de acceso: mayo 27, 2026, [https://www.reddit.com/r/Anki/comments/1rh7hgs/current\_status\_of\_incremental\_reading\_in\_anki/](https://www.reddit.com/r/Anki/comments/1rh7hgs/current_status_of_incremental_reading_in_anki/)  
23. STREAM: A Semantic Transformation and Real-Time Educational ..., fecha de acceso: mayo 27, 2026, [https://www.preprints.org/manuscript/202510.2065](https://www.preprints.org/manuscript/202510.2065)  
24. Cognitively Diverse Multiple-Choice Question Generation: A Hybrid Multi-Agent Framework with Large Language Models \- arXiv, fecha de acceso: mayo 27, 2026, [https://arxiv.org/pdf/2602.03704](https://arxiv.org/pdf/2602.03704)  
25. \[2602.03704\] Cognitively Diverse Multiple-Choice Question Generation: A Hybrid Multi-Agent Framework with Large Language Models \- arXiv, fecha de acceso: mayo 27, 2026, [https://arxiv.org/abs/2602.03704](https://arxiv.org/abs/2602.03704)  
26. ReQUESTA: A Hybrid Agentic Framework for Generating Cognitively Diverse Multiple-Choice Questions \- EdTech Archives, fecha de acceso: mayo 27, 2026, [https://edtecharchives.org/conference\_proceeding/2551/25167](https://edtecharchives.org/conference_proceeding/2551/25167)  
27. Cognitively Diverse Multiple-Choice Question Generation: A Hybrid Multi-Agent Framework with Large Language Models \- ResearchGate, fecha de acceso: mayo 27, 2026, [https://www.researchgate.net/publication/400415482\_Cognitively\_Diverse\_Multiple-Choice\_Question\_Generation\_A\_Hybrid\_Multi-Agent\_Framework\_with\_Large\_Language\_Models](https://www.researchgate.net/publication/400415482_Cognitively_Diverse_Multiple-Choice_Question_Generation_A_Hybrid_Multi-Agent_Framework_with_Large_Language_Models)  
28. Orchestrating LLM Agents for Scientific Research: A Pilot Study of Multiple Choice Question (MCQ) Generation and Evaluation \- arXiv, fecha de acceso: mayo 27, 2026, [https://arxiv.org/html/2602.18891v1](https://arxiv.org/html/2602.18891v1)  
29. Cognitively Diverse Multiple-Choice Question Generation: A Hybrid Multi-Agent Framework with Large Language Models \- MDPI, fecha de acceso: mayo 27, 2026, [https://www.mdpi.com/2079-9292/15/6/1209](https://www.mdpi.com/2079-9292/15/6/1209)  
30. DeepQuestion: Systematic Generation of Real-World Challenges for Evaluating LLMs Performance \- arXiv, fecha de acceso: mayo 27, 2026, [https://arxiv.org/html/2505.24532v2](https://arxiv.org/html/2505.24532v2)  
31. LLMs meet Bloom's Taxonomy: A Cognitive View on Large Language Model Evaluations \- Alexandria (UniSG), fecha de acceso: mayo 27, 2026, [https://www.alexandria.unisg.ch/server/api/core/bitstreams/15f9b7bf-0d70-4191-a708-44bec18ada64/content](https://www.alexandria.unisg.ch/server/api/core/bitstreams/15f9b7bf-0d70-4191-a708-44bec18ada64/content)  
32. Evaluating cognitive depth of AI-generated multiple-choice ..., fecha de acceso: mayo 27, 2026, [https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0341317](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0341317)  
33. Generate Customized Study Flashcards with Artificial Intelligence | Science Project, fecha de acceso: mayo 27, 2026, [https://www.sciencebuddies.org/science-fair-projects/project-ideas/ArtificialIntelligence\_p036/artificial-intelligence/flashcard\_llm](https://www.sciencebuddies.org/science-fair-projects/project-ideas/ArtificialIntelligence_p036/artificial-intelligence/flashcard_llm)  
34. Desirable Difficulties: Why Effortful Learning Outlasts Easy Learning | Glasp, fecha de acceso: mayo 27, 2026, [https://glasp.co/articles/desirable-difficulties](https://glasp.co/articles/desirable-difficulties)  
35. DeepQuestion: Systematic Generation of Real-World Challenges for Evaluating LLMs Performance \- arXiv, fecha de acceso: mayo 27, 2026, [https://arxiv.org/pdf/2505.24532](https://arxiv.org/pdf/2505.24532)  
36. DeepQuestion: Systematic Generation of Real-World Challenges for Evaluating LLMs Performance \- arXiv, fecha de acceso: mayo 27, 2026, [https://arxiv.org/html/2505.24532v1](https://arxiv.org/html/2505.24532v1)  
37. (PDF) AutoMap User's Guide 2013 \- ResearchGate, fecha de acceso: mayo 27, 2026, [https://www.researchgate.net/publication/307883009\_AutoMap\_User's\_Guide\_2013](https://www.researchgate.net/publication/307883009_AutoMap_User's_Guide_2013)  
38. Structuring Competency-Based Courses Through Skill Trees \- ResearchGate, fecha de acceso: mayo 27, 2026, [https://www.researchgate.net/publication/391120919\_Structuring\_Competency-Based\_Courses\_Through\_Skill\_Trees](https://www.researchgate.net/publication/391120919_Structuring_Competency-Based_Courses_Through_Skill_Trees)  
39. Graph Neural Network for Concept Prerequisites | PDF \- Scribd, fecha de acceso: mayo 27, 2026, [https://www.scribd.com/document/954238966/A-Graph-Neural-Network-Model-for-Concept-Prerequisite-Relation-Extraction](https://www.scribd.com/document/954238966/A-Graph-Neural-Network-Model-for-Concept-Prerequisite-Relation-Extraction)  
40. The Teacher's Cognitive Load: Designing Lessons Without Burning Out \- Structural Learning, fecha de acceso: mayo 27, 2026, [https://www.structural-learning.com/post/teacher-cognitive-load-lesson-design](https://www.structural-learning.com/post/teacher-cognitive-load-lesson-design)  
41. PageRank \- Wikipedia, fecha de acceso: mayo 27, 2026, [https://en.wikipedia.org/wiki/PageRank](https://en.wikipedia.org/wiki/PageRank)  
42. PageRank Beyond the Web \- CS@Purdue, fecha de acceso: mayo 27, 2026, [https://www.cs.purdue.edu/homes/dgleich/publications/Gleich%202015%20-%20prbeyond.pdf](https://www.cs.purdue.edu/homes/dgleich/publications/Gleich%202015%20-%20prbeyond.pdf)  
43. Let's learn A-Z of Knowledge Graphs: one step at a time |Part 4- Pagerank & more about graph traversal | by Preeti Singh Chauhan | Medium, fecha de acceso: mayo 27, 2026, [https://medium.com/@preeti.chauhan8/lets-learn-a-z-of-knowledge-graphs-one-step-at-a-time-part-4-pagerank-more-about-graph-c8b94a5b5ce](https://medium.com/@preeti.chauhan8/lets-learn-a-z-of-knowledge-graphs-one-step-at-a-time-part-4-pagerank-more-about-graph-c8b94a5b5ce)  
44. PageRank and diffusion on large graphs \- Computer Science, fecha de acceso: mayo 27, 2026, [https://cseweb.ucsd.edu/\~atsiatas/pr\_diffusion.pdf](https://cseweb.ucsd.edu/~atsiatas/pr_diffusion.pdf)  
45. Graph-Based Ranking Algorithms in Text Mining \- GeeksforGeeks, fecha de acceso: mayo 27, 2026, [https://www.geeksforgeeks.org/nlp/graph-based-ranking-algorithms-in-text-mining/](https://www.geeksforgeeks.org/nlp/graph-based-ranking-algorithms-in-text-mining/)  
46. What Are Entity Resolved Knowledge Graphs? \- Senzing, fecha de acceso: mayo 27, 2026, [https://senzing.com/entity-resolved-knowledge-graphs/](https://senzing.com/entity-resolved-knowledge-graphs/)  
47. Transcription Guidelines (2025) Taxonomy, Language-Specific Features, and Positioning in Research & Practice \- ResearchGate, fecha de acceso: mayo 27, 2026, [https://www.researchgate.net/publication/398078310\_Transcription\_Guidelines\_2025\_Taxonomy\_Language-Specific\_Features\_and\_Positioning\_in\_Research\_Practice](https://www.researchgate.net/publication/398078310_Transcription_Guidelines_2025_Taxonomy_Language-Specific_Features_and_Positioning_in_Research_Practice)  
48. Towards More Effective Automatic Question Generation: A Hybrid Approach for Extracting Informative Sentences, fecha de acceso: mayo 27, 2026, [https://thesai.org/Downloads/Volume16No9/Paper\_20-Towards\_More\_Effective\_Automatic\_Question\_Generation.pdf](https://thesai.org/Downloads/Volume16No9/Paper_20-Towards_More_Effective_Automatic_Question_Generation.pdf)  
49. Open-domain clarification question generation without question examples \- ACL Anthology, fecha de acceso: mayo 27, 2026, [https://aclanthology.org/2021.emnlp-main.44.pdf](https://aclanthology.org/2021.emnlp-main.44.pdf)  
50. TwinStar: A Novel Design for Enhanced Test Question Generation Using Dual-LLM Engine, fecha de acceso: mayo 27, 2026, [https://www.mdpi.com/2076-3417/15/6/3055](https://www.mdpi.com/2076-3417/15/6/3055)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEQAAAAaCAYAAAAOl/o1AAADlUlEQVR4Xu2YW8iOWRTH/5oxzRjDzGCkyEcaTY41qCkXwohyqHGIKBcu3CgXinL1llyaJjlcoVESJjeTBkkONyZTUzKUwwUxFzSUmppIZv2s9/2+513t5/AeXOD71f/iW+vp3Xuvtfdae39SP/20wwd1vQsMMH0Rja0w0LRX/kNl8O1I06hgf1PB/Fw+1lfBPij8nYV1bDINjY4qsMD9pgPREfjEdNX0yvTcdN900jRafb/RTSaansrHe1TXGnngZ5jO932ahKD8pjaCstx01zQhOurww4vlE/rR1FO3wQbTDdMZ04u6rVO+NB2VB2KZ6eOM76LphDxQv2TseVwxbVW1nf8atuF1Uy3YG5D5mnxyl5pdr2GgHXL/X8HXDt/Ik/NSHuwISftbPt7G4Eux2vTM9G105HHBdErNWcjCwEwgb/cAR+aBqk2wCJLDeAS4KKPb5cEfHh057JbPb1x0pPhXPkCKSfIJUpyKICDX1EIWEhCAn0w35QW7COZ7SMVBy/KDfB1LoyMFHy6KRvlge1QtsnSAFfKi2y6T5XWhFuwpmO+UaCyARJH4ndGRgg9TmSUIBKOVTHRCTZ6c1Fw6hYTdMx2JjhR8GO8TQD1ggjOjowSCt9Y0LzoKoBZQExiv3eDTWukmKQbLayUqhH6eF5BtqpYx6sxh9V2SOP+3TVt6vyinkUHGK2OXaWE0GitNT6KxTuWAQF5AOKdVAlKTB68TPjWdU7WA8N2YaCzhM9NlVQwIPXpaNKqvhqSykYWB6DKdUpMHpKgwcydqZec1aOxAglkKk+DMp+Bc4t9nGpKxc9S+N/2esQGdhtbGkcm2zuwO+C5jj3Bj5jkwV821ZJj8nXUwY2uwWf4td42fg6/BbPktutI9iV3Aj+WBj4Vwc+TtcMz0WN594s6g33Plpl3H4shkeP8sCfbIHfl4D+UL5O3EzXWV0o9Hst+oEXlHFzstndZeCgsou/WxUxbId9Ic5d9qgckXHbOygLBoru/stvVqfjflMV5+JOZHh3yu3MRPq/g49sLW/0/Fi2gFMjrCNNX0YfAxIRbbbWgABCTuWGBX/CN/01SCQnXc9KsqRrAAssFtkElwtiMEPwapGzBm3nuM58BZ+bFqiVmmW9HYBvyXKnXWOZI90dgFOC7UHQpnZKy8rrUN25me/TbwtbzlrzP9Ke9EWT6SX+LeG+bIO8cfpunNrvcTOg+7InU8++mny/wPpYKhZb6vZaAAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAZCAYAAADe1WXtAAABMElEQVR4Xu2UvytGYRTHv5JBfiUig3pXEgqLMpuYmPwBFiaDDCazxWwxKINVGQzKhNVqYFAymCiD+JweV49zf75ei3o/9RnuObdzn+d0zpWaFNCCfTiEnVG8DTui50pYsRN8xw98wDesYTvu40rychmTeI8vCoU9OwofucZel8tkGp/wGWddLmEGXxVOWokrhVNsKfuUhvX2TnVc3Qre4IBPRFhR+/iIT2SxqtDHKZ9ohAPV0fwq2Pyd46Hye5mHzes6jvtEUtROW8YRdkfPE/iIi1HsmzU8VRjsPGo47INF2Mu2MXM+8UWPwob52CXuqqBttpK3SvdnFC9w2cU3cBPPVPIfaFWYwSVcwMGf6RS2CGM+2CjH2KX07X5Nv8K6zivc7E+wSdnDbYV5bfLf+ATXcCyFG2qdfQAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABYAAAAbCAYAAAB4Kn/lAAABdElEQVR4Xu2USyuEYRSAj1BEJHJZqLFRlEshJfILWLGysLThD9ha+wcsLOSysJPLSo0VZSFkwcbCxkIpysLlOc7M1zenubxmZjlPPU3OmTkd73vOK1IhkCpsxS5sjMVrsSH2dzBacBy/8Aef8RMTWI8buJD+ciideIDfOIDVqbh+XuEJvuFQKh7EMD7hO866nLIm9h9cYovL5WQUX/AVJ1wuzRh+iB1FMNrJDbb7RAy9xAvs84lc9IgVXvYJhxaeE7vAIJbEznXEJ0plS/55ISHo4J/httj8FsMgrogtTkS6sHZdiF1scrEasaZOJXM7/9BLO5b8l5LAbh8shP5AV3bKJ1I046EPwiruiW1kr8tF6LvwKHZecfoxifMurkxiG97ijMtFTOOD2Dzf4ybe4blk76ZO7Hx1RPUZyDuq+tDoVukSLGJHZjor+sppx9p52dC51/nXBSsrQcdQDHoMZd1YLXiE+7juciWhxa5xR2zGK+TmF2joO9bmoYcJAAAAAElFTkSuQmCC>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAaCAYAAABYQRdDAAABM0lEQVR4Xu2SQSuEYRCAR6jVkizZlFLO4uakveJgD1IOfoALDhz2F/gDm3JRbiQue5McuCkH5a6oLblqc6DwjPe1O+9bny/taet76qmd2Wmab94RycjoLArYGycjBiW9psk4PuMbLpn8Ft7jhI+/cB97mhUJ9OGpuMZ1PMFuHMJbfMCir9WmV9jv40QWsYR7+IkLPr8ursm2j5UKVk2sq9jEaZMLeBQ3mU6oHOIHzv0WwC6umXgGX7BscgE6lZ0i/nTlGCdNnIo2XTbxK55J+ChHmDNxKtp0w//WXWl8Lu4hlVkJH2hH3I4vMW/yAQf4jjW8xlVs4J2467holf5Mq191I61BEtFJxnDYxzqx7nRU3JnFPOFUnGwX3fmA/HFS/2VE3HnN40r0X1voTXfFyYwO4RuPii+P3ivPggAAAABJRU5ErkJggg==>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABwAAAAZCAYAAAAiwE4nAAABgklEQVR4Xu2VPyhHURTHv0IR5U8iGTzlz2BAshiVYmCQQdkMyGBgYlIGgxiUTfxYLBaTxWaS2aIUk0GSVYnv6ZzrvnfzW97vvQx86tPvds/t3XvOee/+gH9+gXraSsvCQNbs0Ff6aX7QLVoZX5QFkskSPaEzdJYW4Dce/16ZAb30mT6GAfJEL2hdGCgFyUaykFKGNCKHPkq5XOlkg9yRcl1CN3yjc7Q6sSJHtuk7fMaZ9k5ooVXBXERvoBtuJCIlMkKvoR94SETvoaWuSYbS4T6FpjAQ45gehJNpWYGWrCEMGBX0jI6GgbQMwF9h53QYWtouuktf6LKt7YD2sh3+xlmA9lnm7uiEzctLVvQaHIJ/G51yd+4j2dd+c5K2wWe/Z/E16LOEU9pt4x8ZhL87p1H8dHLbHNmv9P2WTkE337S5THGbCHLIB9oHLfc69CCddNHWlIw8cBXaVynbFT2k8xZza8ZsnBnNtNzG8icdR/orWUfBfG70QN/e2jCQJy77P8YXFflBMHxFN/wAAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADEAAAAaCAYAAAAe97TpAAAC20lEQVR4Xu2WTahNURTH/0IRnnxEojwyUSIJKSMMKPkuAwzFQBQxMHolAwORzxIKIR8T+Y7BzUgZKVLKgJSBgRiIJP7/1jn3rrPeOeee691r8Lq/+vfuWXu/vc9ae621D9Bl8DCUmhCNbWJ4NHQCbXKa2h8H2sRTalo0tsoK6gos2hE5cJa6kPzuBFupl9T0ONAKh6kd0ZiwkXpHzYoDbUTBuUmdS363zAjqGrUgDiS8ovqisQMsob5RG+JAFdZQF6khcYCMpu7DHP0fKBt+RmMVjlHbozFBp3MwGh1VnFNwqqbIQup7NBbRQx2gPlC/qU+wozzuJ5Et1KpgE2oAu6n31ENqrBsbSd2iRiXP+6jL1LD6jGKmwNZsOnc19YU6A+v7D6hxsBb3DNkOoYLPq5XNsJarCP9B1lHN9yl4lKrBUrMZmlOjxgR7hsXUXVi0UnwhKRI1NDa8lNg8vdQu2EvqhR+hsZ4ieBvWsj0n3G+l13L3HMnbs442uE6tdDadwGz3PA8NJ5QyN1CyIKxryaGUybB2PNXZhJpHiuYoxYoodWIi9RrZm1EO+GNWDZxCo1OVLag6eE7Ncbal1C9kc1qBmumey9C+V1G8Zz1KfoJeOkUpodSY72xyQqeTh+xqBj5/98JqxKP+37RQE9Ka0LsWoo3Pw15YEboD61Qnqa/IHrtQwXpHPdroTfJXqCG8hTmRnqRue3UmsYlaB9uj6CV1YuqUTVFhf6aeUB9h/3QE+V+oM5AtysgyWEtUCsiB9bC17iVS5xufzFUDUUqrLvMuViEH1fIroc6iS+wQihcUSgPVkTYvYhIsRf3Fp2cFJa6toCili1DAdLqVSDtVbIV5/EC2ow0EfVa8oOaif52k6dkX7IUoskqr2Arz0NdlvFv+BZ2ULkFdoHvCmNiJ/t2zlLXUtmgsYREs5/V3ICi91FAij2F3R0y/tqM7RZ8anUAB7bgDXboMNv4CBdlsHBQyhYcAAAAASUVORK5CYII=>

[image7]: <data:image/png;base64,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>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACIAAAAaCAYAAADSbo4CAAACEElEQVR4Xu2WP0hVURzHf1KCYSL+AZUEaVMLHCTBVQxcilC0JcWtQHBoKNpCcBQkmgSJFkVoERECI8JFNxEsIXDQxUFcghwC0+/3nXt6xy/v3XveQ6f8wAe8v9/1vt8553fuuWbXXD6VsFaDAVn5S6EVfoY9mghgEctwUBOxVMD3sFcTAWvwhQYL0Aa34ZAmYmiEK/COJhJYKPO3NFGEZ3BXgzF0wwVYpYmEe3BAgylwiTbNDaAkPsB+DSY0WXmjuw+fazCLr/CuBhNY4KkGI6iDn+BNTSgtcAYewj/wCO7APrs4pa/hr+A6Fj7ju7n+K8okPIavzDUgf4z/+BT+hmP5W+0j3A+uS4G/0aFBz0NzW9WPmhWHu4VFnSV/34bfEhW+V7hNuWyPJef5a0V6j+u1aBffF9wx4W55Z3GFdJlbMt77UnIe5h5pkHAH7JlrJE/Y2X7bsW9IWiGc0SdwCtZLznMCH2iQsEG53vwBwofN5dO5ZeNUzybXnEF2PosvB/YbZ7wgPCvewBvmbpqHnXALfoHN+VtzcMY4slLhcvN51ZoI2YAHcB3+hD/giLniFBbLkZUKN8C0BgtRA5fgsCYE3yeZLyaBuyXtEP1H1kEXwlO32Ju3EP40jzokfX/EjLQBvtVgCjwkufRR8MWV9pGjjMNVy/4C43dIzH1lw+kehROaCGg3t/WvrIhr/g/OAe2sUL1MJgDeAAAAAElFTkSuQmCC>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAaCAYAAAC+aNwHAAAA20lEQVR4XmNgGAXoQBOIpwHxLCB+BMUboHwQngTEbkDMCtOADkSAOACIy4H4HxDXAXEIFCcD8X4g/g/Ep2EacAFPIH4AxNJo4oxAPIUBYggLmhwccAPxHgaIK9ABSNMaBogB4mhycKAExM+B2AZdggHiogcMEANArsEK/Biw2wDSUAaVu4UmhwJaGbD7sRKI/wLxMSCWQZODA1A0vmWAxABZIJoBYvsDNHGiwRwGiAGgkCYZCDJAEgjIgHQ0OaJAKQNE81MgVkeTwwv0gfgTA0QzMgaJj4JRQB8AABhXLSG7tX8wAAAAAElFTkSuQmCC>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAaCAYAAABhJqYYAAAAm0lEQVR4XmNgGAX0BoxAzIwmxoHGBwN5ID4CxFegbBAQg/IVYYpAgAeIVwCxGRB/A+IiqDhI0RMg9oTywQDEMQViTiB+AMTSSHKSQCyOxIcDYyCezwBxOwxoMuBwdzoQR6OJofPhYCEQ6yPxQc5aisRHAQ1ArANlCwHxciDWhsuiARkgfsgAseEkEDuhSmMCYQaI71nRJUYB/QAAWh0QRxedrfYAAAAASUVORK5CYII=>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAZCAYAAAAFbs/PAAAAo0lEQVR4XmNgGAWDEXAAsRgQM+PgwwE/EIcDMSMULwXi3UAsCsTTgfg/QikEZDBAFIIATIMfEEsC8UMGNA0g65KR+IJAfBqIlRggmvWhGCcwBuKvDBD34wQgSVYgZgHiNUD8D0kOJB6FxAeHwhUg9gViaSB+AMRPkOTNgXgDEh/uBJA7QZ7/y4DQIAHEm4HYBsqHA5DnhKE0CIACAmv4j4LBAQAbdBTuzvh2TQAAAABJRU5ErkJggg==>

[image12]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAABACAYAAACnZCtBAAAEvUlEQVR4Xu3d26ttUxwH8CEU5X5N6AgvblFKKaVEePBEyO2VhAcelKfzN5AXkSTJ5UEhQtnhgTygSIk6JEpJFLnkMr6NNTvTOGtfztprr7Xk86lfa8+x59przvmyvo3fmHOXAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMCcHVjr2H5wxRzcDwAAbNdBtR6p9UStr2p9ONlO3Vfr1L27LlWC0GOT116O8Yh+cEluqfVRPwgAsB0H1Lqu1lu13q9142Q79WOtPyf7LNu1tc7sB6sTa/1e65r+F0uSQPns5BUAYG5Or/Vtrcu78ZNqfVnr/m58Oy6sdVg/uIm7av3QjaU9elRpf+vvsjqBLQ6t9erkFQBgLq4uLfSc3I1fUuuPWvd249sxS2Bbq/VyPzixioEtfqt1cT8IAKyWY2o9VeubWt/Xum3yc9aI7Rrtt1POLm1Waq3Wp7Uu/ddv/22ttNDT+6y08aElOo9zmiWw5RgSKqdZZGDLrN71tfbUeqe01ud6MjP5/Gj7nlof13ql1pGlHfdrta4Y7QMALFhmhG4oLewk5Lxe6/jSwsV6Lcbzyt71YxvVccMb1pEWYmbGhpZcgsXQUkzbMzcajKUdmv0HCSYXlLY27M7R+Czn1JslsP1c2vumWWRge6606zgE2ITV4VxunrwO1mq9Pdp+uLR1bUP4PKW0IL3V6wYAzFkCzxmTn48ubTF/1onli/78yetOOae0UHHuaCxhJ6Enn521Vb2EiPVajoNZzilhJuvgxnVlaTcPjMdy48BGi/QzW5X9ptlqYJt2LH3lkSHTziPuKPuuS0vYeqC0GzX69+Wu2xx3nFbrkNJapOO/cXhpbWcAYMmGsJQv7EXYXVr4Gn/ecFPB46UFj7GEr/2ZIYutntPdpT0qZFzf1fq6G/uktNA3TYLiPALbtGPpKzNo02b/0sJ8t9bt3Xhm1RLAXuzGYxzYBrtLm/0cZM1gv24QAFigYdYo65j+Go3fVNZ/+OtDpYWPzaq/m3OQsLFW9g0vCTsJD+NZt0FCRwLTZm3WmOWcerO0RH8q6we6rQa27RgCah8a85lZkzbtbtC1Wl+MtnP8OY/MqkXa0gl1AMCSnFD2hog9pc0oDV4o+x9Ytiptucyi9W22hIW0SfvAMeyf9Wh9S683r3OaJbBlfV1/ToNFBLbMgu0pbTZyLLN264WutIzfGG0PoW+8/eRoGwBYsMy4fFDrpdLCUu4OfKa0maydluCVcJYF7++V9tk5notKezhuFrrHo2XfmbuNzOucZglsCYcPdmNDUOtrp4Jbzv+X0tqmn5fWdk679tdab5bWNh3LA4ev6sZys0GuW0LeZd3vAIAlSItwaBPmiz0zVHldhOHz8mDZscywbbbubCPzOKdZAtvTZf+D4U7IteuvYa5xrkMvwTgt5F7Gpo0DAPynDf/uadpasVWUGzvy2A4AgP+VXaU9A27VnVZWYzYQAGApzirtAbSr7Nay+Q0cAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABs5B+WH9uJIjo2+gAAAABJRU5ErkJggg==>

[image13]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACUAAAAZCAYAAAC2JufVAAACJUlEQVR4Xu2Vv0tVYRzGHymlSFBpkByKIoQWU9SGCHEoSqKgloYWcREiBBf9A8Q9HBpEiYaGRMIhQpe4NAUNLoViRT8QwyFEwSVBfR6/vtyv7znn3pvidj7w4XLe8573Puf98T1ATs7xUk+v0/PxjQo4Ra/R2vgGqaJNcSM5GzfETNGfdJK+pT0H7mZzgg7QVfqabtAJesb1UdACnaHjsP/4TO+7Pgnu0P6o7Qudpaejdk8d/UjvRe036Iq7Vqh3sEBjsP4+dAJN7Qt6M2ov0L/0StTuOUd/0adRezv97a4VSrNUMQ30E2wgz0u6g+QseBrpd/qP9rl2hdTyBP47VHjbrFDDUbtHs/wM1k82w2b8B73t+oVQd+lz2BLqQGWiMJv7v55KQgVa6CKK4eZhAQMKNeeuRS8dgb1YgquwE3OYUBrwEf0Dm6E3KAZbcv3S0P8t04vxDXGU5WuDlQIFEyHkOuzZUlyi20gesD2yNvor2MAPo3aP9oae1RgeFdE12LIp6CDsJHs0GZkH6SSdRrJYFpC+1zyazQKSVVxB9FJqD4VTAWpcH427Batpqajcf4AVw4COeVgWoTcK+yW83WVYkVQFD0U2LKFKReAWLFhAfTURJSu6WKDv6WM6Sodgn5DABVjt0SnzJ6uTfoPtSz2jk/eVtro+CvoENrP6xKi/9l3qyfNU0y5YqAfRvXLo2Q7Ys/rVdRoaV326YR/wnJycnHLsAp9xbhFvnR/KAAAAAElFTkSuQmCC>

[image14]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAaCAYAAABYQRdDAAABSklEQVR4Xu2UvyuFURjHH0VhuZFFFqtBd0BSFmVgsGC7iz/AbvEnWBillIEMlAz+BWXxLxhYRFEGg/h+Oudcj+N173uvDOp+6tPpec77Pufn+5p1+GsW5W4Jt+VoeKU543JVnskbuRbj5LF8ky9yIrxSnh25L7vyDgsDMeBwlm/ImHyQ1bwjwgwPZW/e0YiafJcDLjdkYUtgTm65vlKwdIp6FuRRlisNs7uyUDQdzqZ8khvuuZZIS6dwYkpeyxGX4wCnLaxq0uUL2bNQlJNPzMoD2e1yK/JCDsaWuBC/dGacYIbc30RFXsrlGNMSk/8GV+jZml9stuM2tsBK7uyHK3hiYZansj/r8yzZ14FpicnXmZGvFgp6+Q8UUapoqzAY2+SLPsr5+hNtwGd8b58rYYZ81uTbpk+ey/UY0xKT/zX8ULj4PXlHh3/CBwL5REkNV2B8AAAAAElFTkSuQmCC>

[image15]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAJwAAAAZCAYAAADExUcmAAACLklEQVR4Xu2ZvWsUURTFj6ig+I1FCFqIkEJTWEiwXAuTKuksBEsLQ0qDX39EQGIjYkBbbYRgF8LrAiqksbRRUME6aQQT7+HO28y8zJsdZQtnOT84sHPvu7MLe7jvCxBCCCGEEF3khulrjd6anpuWTTP90U5aswYfG3Vnb6gQVc6Zbpq+m3ZN68UzdQtuoF+mXiyA18yjvuaB6ZPpqelkLBAiJcDN8zCJkzPw3DvTkSJ2HM01O/Dc3TQhBAnIm4fmYu6LabwUC0W8rmYbnnuVJoQgAXnznIDnPsC7HRlkuH/pcAdMZwvlOGwaS4OiewTkzTMBzy2WYk2GoykY52biVJLL0TN9htdR901HS/nzptem3/C1o+g4Af5Hb2Fv98nPjG2YDvZHOmXDfYRvLlbg0y5NQdO1hcaaTmIv4O9ehRv+Mfb/BtFhAv5uzZXrcDTPS7gB25ruCqrdjHBafQ9//w/494kRImA4hiNT8C53PYnnmEsDBdfgmw+uB8WIETA8w10q4veSeI6c4biJeAZ/lzrciBEwPMPx6IRxrsPawCn1UBo0JuFrSXY5HijTgGJE2ISb5A3adRPeNsSapSTH9Vhce10sYoO6HY1+rPTMHW55l8vbDuoRquNEx+B0RnOkuloelFBXUz4UJvGIg7cTC/Bu1cSs6Ru8o/00PUHVWJfhu+X4fUJU4BEGTcv72NtJLkc81G062D2NqrGFEEIIIYQQQgghRC0X4Ecz4j/gDxYWlkI2V456AAAAAElFTkSuQmCC>

[image16]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAARYAAAAaCAYAAABy+HOAAAAC3ElEQVR4Xu3dS6hNURwG8E9SXnlEHjGgpCRJZGBgIAOSiQyUyS0DRiYIZXAnkhGGlMTQowyIZLBCGRgYKYlCoggZMFAe/89/7bPXWWeffU/n6N7u3d+vvm577XXuYHfPv73XWntdQERERERERAawwLLQMiUeT40RkQbaanmb5ablQpJ9rd6dWEgOWT5a3ll+WM5brlp2Jv1EpEGWWHZb3lv+WB7E4yKnLd8sR1DejRR4zMLzKmmbZjkG/10qLCINF+DF4GjWTrPg51hE0uKyzfLbMpS00SSosIgI6gsLFUXkk2V1bLsM/8xQPE7dhgqLSOMF1BeWpfAxFPYZjm38yWOOy+S2W1bljSLSLAH1hWUmyj73YxvvXHgHw7bXlnPwwWDNBonIPwG9F5Z0sHaX5WdsT7Mo6VOF4zCb0D5QPFJ2WGbwwyIyPgT0XlietJ9qmQcfV7mH9kcmEWmogPrCMt/yDN7nUmybjc4paCpmhViA5mbnRKRBAuoLy3rLd/jMEGeIiLNC3WZ+PljeWBbnJ0SkOQLqC8tZ+Hk+5vCxiFhYuvVnUeEdDu90qky33ELn2Exd0qluERkHnsK/vMOWybFtjmWt5Qr8sWZZbC8U61j42RRX3361rMvaRaQh+CiT3xmk+WV5hOqxFBaWU5aDlueWizEvLVuSfiIiPeN0cTH9uwHltPDmVg8REREREREREREREREREZGecc3LZ8sNy374u0Un4NtbTmSPLS8sJ+Fre7gnzV34aw0HMPqvOFyDr0XieqN+7IXvwbM8a18Df8O92+sc/ViJ9mt3B+W1GwvcHJ7XrlhZzvffuOVq1XquM/D1XiFrHwk/F1CuZJcaxT64K7J2Xvhuy//HAveN+Z82Wo6jXLVM3LcmLSajXViIRaXfwnId/uXak5+Ab/yVFhZ+EfvFa/cF7deOL7gOer0OY7BtNh6i/Jvl72Ex5X+iqMJ+IW/sQcAELCx/AaRiqffspHJHAAAAAElFTkSuQmCC>

[image17]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAASIAAAAaCAYAAAAT4FHCAAADzUlEQVR4Xu2dT6hMURzHf/Inf/M3EvWQ2CAliojCQmKBRMpGYuFZSJSVjYUkKxYKWSj5s0L+ZHGjEJKEZEexYGGDQuL3feecN2d+c2bm3nnPe2Pm+6lvM/ecc9/ce+ae7z3nzu+cJ0IIIYQQQgghpMUYo5qsGm/SR5ltQggpY77qdE6hbAqYzxfVH9VX1SdVp2qYapHqaakoIYRUMkW1SfVDnJE8UG3xadAO1VWft8/vExig2q76Ka7ciCjvlCpTvVe9i9IJIaQqMAuYzUGb4dmjuiDOfMBq1W9xBrYsFDJgiPZYaESEkJykjAhDqxX+daHqmmqkz8vElb+iGuTTUuDv0YgIIblIGdFU1T1xz4AmiusRTfB5v8SV3+W3q7FU9domEkJIimBEeLCMB9MvxA29kA4jsqDsN9UCm1EQDPWWSOmZVB6t7dqTENJyBCNCrweN/ZBPoxERQvqM1NAsDKuCEQ0VFysEUPa7uGdHhBDSK6SMCAaU+VeAn+/RUwIoC23w29WYpLptEwkhJEXKiGJgKI+k1APaLa78R9XMUCgBfvY/bBMjhquuS8nY8uhz156EkJajnhEdEGc6M/z2YHEPtbHPxVDI0KG6K7WNihBCuvkgzlSOizOZAOKG5vi8J6qxUR4iqc/5vOlROpimuq/aaNIJIaSCdVI59KmmVPDiQNVmcflvVGfE9ZTwfnlUjhBCCCGEEEIIIYQQQgghhJDWJSwPi1/PAAIUw/tWAnPi/jVY4QBrOPXFZ/UG/8txNor9hTgvqJetNrEHhDaG6wPEbeyYuFUy2pZZqoeqt6ojqpuqNapbkp4k21/MU520iQVYJW75W0zwzQNiqxDCgAXhME8PdbSyrESaDtUJcZ+FFTKbAVzgqDvUoQUL42GychFmq26Iu2awcmfm9dxv45pqBvAdXladtxk5Wa86KpXni2sik9L5PlPNFRf0i2sFaZhlEAwHxG1sr1S2MQQL4zhH++22AhV1ScoDH8Fi1StpLiPCMY6ziQXBCgO4SIqAfapFqVsQNJrZxCYAd1300GwPF1H2MOhGQb2kjB0xbc1EI0aEm8hZKe8thvO1K1Vsi97bOkEbeyn52hgCjrFuGKZhtRVYDC012RX/rQPLiMSVhBn7jRgT9sG+RUE3Nr6jpEDDt19wLVJGhMZZ6/h6w4hwHkWOMw84bvzdsIpCTPiuap0XQH69Oq5F3OjQ+9jvX3d2l3Dnjc8ZIvmHgDimescOQh3UwxpRtXoLYCiHoN/YYEBsRPH5xitXWCNCG0OQsCXVxnD93JGe3Rz6lb/kS8p2UFefJQAAAABJRU5ErkJggg==>