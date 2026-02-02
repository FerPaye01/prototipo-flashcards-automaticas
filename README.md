# 📚 Flashcards to Anki Converter - Documentación Completa

Sistema automatizado de generación de flashcards usando Gemini AI con importación directa a Anki.

## 📋 Tabla de Contenidos

1. [Descripción General](#descripción-general)
2. [Características Principales](#características-principales)
3. [Arquitectura del Sistema](#arquitectura-del-sistema)
4. [Instalación y Configuración](#instalación-y-configuración)
5. [Modos de Operación](#modos-de-operación)
6. [Sistema de Prompts](#sistema-de-prompts)
7. [Comunicación con Anki](#comunicación-con-anki)
8. [Sistema de Configuración](#sistema-de-configuración)
9. [Tipos de Tarjetas](#tipos-de-tarjetas)
10. [Sistema de Fallback](#sistema-de-fallback)
11. [Gestión de Imágenes](#gestión-de-imágenes)
12. [Modo Manual](#modo-manual)
13. [Procesamiento de Videos](#procesamiento-de-videos)
14. [Troubleshooting](#troubleshooting)
15. [Estructura del Proyecto](#estructura-del-proyecto)

---

## 📖 Descripción General

Este proyecto es una herramienta completa para la generación automatizada de flashcards educativas a partir de:
- **Imágenes** (capturas de pantalla, fotos de apuntes, diapositivas)
- **Videos** (clases grabadas, tutoriales, conferencias)
- **Texto manual** (entrada directa del usuario)

### Flujo de Trabajo Principal

```
Entrada (Imagen/Video/Texto)
    ↓
Extracción de Contenido (Gemini Vision OCR / Whisper)
    ↓
Generación de Flashcards (Gemini AI con prompts especializados)
    ↓
Conversión a Formato Anki (TSV)
    ↓
Importación Automática (AnkiConnect)
    ↓
Flashcards listas en Anki
```


## ✨ Características Principales

### 🤖 Generación Automática con IA
- **Gemini Vision OCR**: Extracción de texto de imágenes con alta precisión
- **Múltiples APIs en paralelo**: 5 APIs de Gemini (1 OCR + 4 generación)
- **Prompts especializados**: Diseñados por expertos en pedagogía cognitiva
- **Fallback automático**: Sistema de respaldo entre modelos Gemini

### 📝 Tipos de Flashcards
- **Basic**: Pregunta/Respuesta tradicional
- **Multiple Choice**: Opción múltiple con distractores inteligentes
- **Cloze**: Respuestas anidadas (fill-in-the-blank)
- **Vocabulary**: Traducción y fonética IPA

### 🎓 Niveles de Bloom (Set alternativo)
- **Nivel 1 - Cloze**: Recordar (hechos, definiciones)
- **Nivel 2 - Relaciones**: Entender (conexiones, causas)
- **Nivel 3 - Aplicación**: Aplicar (casos prácticos)
- **Nivel 4 - Análisis**: Analizar (evaluación crítica)

### 🖼️ Modo Automático - Imágenes
- **Secciones dinámicas**: Organiza imágenes por temas
- **Drag & Drop**: Arrastra imágenes directamente
- **Pegar desde portapapeles**: Win+Shift+S → Pegar
- **Indicadores visuales**: Estado de cada tipo de tarjeta por sección
- **Sesiones guardadas**: Recupera tu trabajo anterior

### 🎬 Modo Automático - Videos (En desarrollo)
- **Segmentación inteligente**: Divide videos largos automáticamente
- **Whisper transcription**: Transcripción local con timestamps
- **Detección de silencios**: Cortes en pausas naturales
- **Análisis de contenido**: Identifica cambios de tema
- **Configuración flexible**: Duración, overlap, métodos de segmentación

### 🔧 Sistema de Configuración
- **Sets personalizables**: Crea tus propias configuraciones
- **Prompts editables**: Modifica las instrucciones de IA
- **Importar/Exportar**: Comparte configuraciones en JSON
- **Tipos activos**: Activa solo los tipos que necesitas

### 💾 Gestión Inteligente
- **Flashcards pendientes**: Guarda tarjetas si Anki no está disponible
- **Reintentos automáticos**: Intenta abrir Anki y reintentar
- **Sesiones recuperables**: No pierdas tu progreso
- **Logs detallados**: Seguimiento completo del proceso


## 🏗️ Arquitectura del Sistema

### Componentes Principales

```
┌─────────────────────────────────────────────────────────────┐
│                  anki_import_interface.py                   │
│              (Interfaz Gráfica Principal)                   │
│  - Modo Normal (entrada manual)                            │
│  - Modo Automático Imágenes (secciones dinámicas)          │
│  - Modo Automático Videos (segmentación)                   │
└────────────┬────────────────────────────────────┬───────────┘
             │                                    │
    ┌────────▼────────┐                  ┌────────▼────────┐
    │ gemini_flashcard│                  │ video_processor │
    │   _generator.py │                  │      .py        │
    │                 │                  │                 │
    │ - OCR Vision    │                  │ - Whisper       │
    │ - 4 APIs Gen    │                  │ - Segmentación  │
    │ - Fallback      │                  │ - FFmpeg        │
    └────────┬────────┘                  └─────────────────┘
             │
    ┌────────▼────────┐
    │  flashcards_    │
    │  converter.py   │
    │                 │
    │ - Parse P/R     │
    │ - TSV Format    │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ anki_sync_      │
    │  manager.py     │
    │                 │
    │ - AnkiConnect   │
    │ - Crear Mazos   │
    │ - Importar      │
    └─────────────────┘
```

### Flujo de Datos Detallado

#### Modo Automático - Imágenes

```
1. Usuario carga imágenes en secciones
   ↓
2. gemini_flashcard_generator.extract_text_from_images()
   - Carga todas las imágenes de la sección
   - Envía a Gemini Vision con prompt OCR
   - Fallback a Tesseract si falla
   - Retorna texto extraído
   ↓
3. gemini_flashcard_generator.generate_all_flashcards_parallel()
   - Para cada tipo activo (basic, cloze, etc.):
     * Usa API key específica (API_1, API_2, etc.)
     * Envía texto + prompt especializado
     * Fallback entre modelos si falla
   - Retorna respuestas de cada tipo
   ↓
4. flashcards_converter.convert()
   - Parsea respuesta de Gemini (formato P:/R:)
   - Convierte a TSV (Front\tBack)
   - Maneja formatos especiales (Cloze, Multiple Choice)
   ↓
5. anki_sync_manager.sync_flashcards_to_anki()
   - Verifica conexión con AnkiConnect
   - Crea mazo si no existe
   - Importa tarjetas con modelo correcto
   - Reintentos automáticos si falla
   ↓
6. Actualización de UI
   - Indicadores visuales (✅/❌/⬜)
   - Contador de tarjetas importadas
   - Logs detallados
```


## 🔧 Instalación y Configuración

### Requisitos Previos

- **Python**: 3.8 o superior
- **Anki**: Versión 2.1.x o superior
- **AnkiConnect**: Add-on para Anki (código: 2055492159)
- **API Keys de Gemini**: 5 claves (1 OCR + 4 generación)

### Paso 1: Clonar el Repositorio

```bash
git clone <tu-repositorio>
cd PP001-api_gemini
```

### Paso 2: Crear Entorno Virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### Paso 3: Instalar Dependencias

```bash
# Dependencias principales
pip install -r requirements.txt

# Contenido de requirements.txt:
# google-generativeai  # API de Gemini
# python-dotenv        # Variables de entorno
# Pillow              # Procesamiento de imágenes
# requests            # Comunicación HTTP
# openai-whisper      # Transcripción de audio (videos)
# ffmpeg-python       # Procesamiento de video
```

### Paso 4: Instalar Anki y AnkiConnect

#### 4.1 Instalar Anki
1. Descarga desde: https://apps.ankiweb.net/
2. Instala siguiendo el asistente
3. Abre Anki al menos una vez

#### 4.2 Instalar AnkiConnect
1. En Anki: `Tools` → `Add-ons` → `Get Add-ons...`
2. Ingresa el código: `2055492159`
3. Reinicia Anki
4. Verifica que esté activo en `Tools` → `Add-ons`

#### 4.3 Configurar AnkiConnect (Opcional)
Si tienes problemas de conexión, edita la configuración:

1. `Tools` → `Add-ons` → Selecciona AnkiConnect → `Config`
2. Asegúrate que tenga:
```json
{
    "apiKey": null,
    "apiLogPath": null,
    "webBindAddress": "127.0.0.1",
    "webBindPort": 8765,
    "webCorsOriginList": [
        "http://localhost"
    ]
}
```

### Paso 5: Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```bash
# Copiar plantilla
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac
```

Edita `.env` con tus API keys:

```env
# ============================================
# GEMINI API KEYS
# ============================================
# Obtén tus claves en: https://makersuite.google.com/app/apikey

# API para OCR (extracción de texto de imágenes)
GEMINI_API_KEY_OCR=tu_api_key_ocr_aqui

# APIs para generación de flashcards (4 en paralelo)
GEMINI_API_KEY_1=tu_api_key_1_aqui
GEMINI_API_KEY_2=tu_api_key_2_aqui
GEMINI_API_KEY_3=tu_api_key_3_aqui
GEMINI_API_KEY_4=tu_api_key_4_aqui

# ============================================
# CONFIGURACIÓN DE GEMINI
# ============================================
# Modelo a usar (opciones: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash)
GEMINI_MODEL=gemini-2.0-flash

# ============================================
# TESSERACT OCR (Fallback opcional)
# ============================================
# Ruta al ejecutable de Tesseract (solo si lo instalaste)
# Windows: C:\Program Files\Tesseract-OCR\tesseract.exe
# Linux: /usr/bin/tesseract
TESSERACT_PATH=

# ============================================
# ANKI CONNECT
# ============================================
# URL de AnkiConnect (normalmente no necesitas cambiar esto)
ANKI_CONNECT_URL=http://localhost:8765
```

### Paso 6: Obtener API Keys de Gemini

#### Opción 1: Google AI Studio (Gratis)
1. Ve a: https://makersuite.google.com/app/apikey
2. Inicia sesión con tu cuenta de Google
3. Click en "Create API Key"
4. Copia la clave y pégala en `.env`
5. **Repite 5 veces** para tener 5 claves diferentes

#### Opción 2: Google Cloud (Pago)
1. Ve a: https://console.cloud.google.com/
2. Crea un proyecto nuevo
3. Habilita "Generative Language API"
4. Crea credenciales (API Key)
5. Copia y pega en `.env`

**Nota**: Puedes usar la misma API key en las 5 variables si solo tienes una, pero el procesamiento será más lento (secuencial en lugar de paralelo).

### Paso 7: Verificar Instalación

```bash
# Ejecutar la aplicación
python anki_import_interface.py
```

Deberías ver la interfaz gráfica. Verifica:
- ✅ Botón "Check Anki" muestra "Anki is running" (verde)
- ✅ En modo automático, botón "🔌 Chequear API" muestra todas las APIs conectadas


## 🎮 Modos de Operación

### Modo 1: Normal (Entrada Manual)

**Uso**: Cuando ya tienes el texto de las flashcards y solo necesitas convertirlo e importarlo.

#### Interfaz
- 4 cajitas de texto (una por tipo de tarjeta)
- Botones: Convert & Import, Export TSV, Clear All, Count Cards
- Selector de prefijo de mazo

#### Formato de Entrada

**Basic (Pregunta/Respuesta)**
```
P: ¿Qué es la fotosíntesis?
R: Proceso por el cual las plantas convierten luz solar en energía química.

P: ¿Cuál es la capital de Francia?
R: París
```

**Multiple Choice**
```
P: ¿Cuál es el lenguaje de programación más usado en 2024?
a) Java
b) Python
c) JavaScript
d) C++
R: b - Python es el más popular según índices TIOBE

P: ¿Qué significa HTML?
a) HyperText Markup Language
b) High Tech Modern Language
c) Home Tool Markup Language
d) Hyper Transfer Markup Language
R: a - HyperText Markup Language es el estándar para páginas web
```

**Cloze (Respuesta Anidada)**
```
P: La {{c1::fotosíntesis::proceso}} ocurre en los {{c2::cloroplastos::orgánulo}}.
R: Proceso biológico de las plantas

P: Python fue creado por {{c1::Guido van Rossum::autor}} en {{c2::1991::año}}.
R: Historia de Python
```

**Vocabulary (Vocabulario)**
```
P: Serendipity
R: Serendipia | /ˌser.ənˈdɪp.ə.ti/

P: Ephemeral
R: Efímero | /ɪˈfem.ər.əl/
```

#### Flujo de Trabajo
1. Pega tu texto en las cajitas correspondientes
2. Click en "Count Cards" para verificar cuántas se detectaron
3. Asegúrate que Anki esté abierto
4. Click en "Convert & Import to Anki"
5. Las tarjetas se importan automáticamente

#### Ventajas
- ✅ Rápido para texto ya preparado
- ✅ No consume API de Gemini
- ✅ Control total del formato

#### Desventajas
- ❌ Requiere formatear manualmente
- ❌ No extrae texto de imágenes
- ❌ No genera contenido automáticamente


### Modo 2: Automático - Imágenes

**Uso**: Generación automática de flashcards desde capturas de pantalla, fotos de apuntes, diapositivas, etc.

#### Características Principales

**Secciones Dinámicas**
- Organiza imágenes por temas/capítulos
- Cada sección genera su propio set de flashcards
- Títulos editables (click en ✏️)
- Indicadores de estado por tipo de tarjeta

**Métodos de Carga**
1. **Drag & Drop**: Arrastra imágenes al área gris
2. **Click para seleccionar**: Click en el área → Explorador de archivos
3. **Pegar desde portapapeles**: Botón "📋 Pegar" (Win+Shift+S)

**Formatos Soportados**
- PNG, JPG, JPEG, GIF, BMP, WEBP, TIFF, ICO
- Tamaño máximo: 25 MB por imagen
- Sin límite de imágenes por sección

#### Flujo de Trabajo Detallado

**Paso 1: Crear Secciones**
```
Click en "+ Añadir Sección"
→ Se crea "Sección 1"
→ Edita el título (ej: "Capítulo 1 - Introducción")
```

**Paso 2: Cargar Imágenes**
```
Opción A: Drag & Drop
- Arrastra archivos desde el explorador
- Suelta en el área gris de la sección

Opción B: Click para seleccionar
- Click en el área gris
- Selecciona múltiples archivos (Ctrl+Click)

Opción C: Pegar desde portapapeles
- Haz captura (Win+Shift+S en Windows)
- Click en "📋 Pegar"
- La imagen se guarda automáticamente
```

**Paso 3: Verificar Estado**
```
Click en "✓ Chequear Estado"
→ Muestra resumen de todas las secciones:
  - Número de imágenes
  - Tamaño total
  - Estado (listo/sin imágenes)
```

**Paso 4: Configurar (Opcional)**
```
Click en "⚙️ Configuración"
→ Selecciona set activo (Por Defecto / Niveles Bloom)
→ Activa/desactiva tipos de tarjetas
→ Edita prompts si necesitas
```

**Paso 5: Procesar**
```
Click en "🚀 Procesar Secciones"
→ Confirma el procesamiento
→ Espera mientras:
  1. Extrae texto de imágenes (OCR)
  2. Genera flashcards con IA
  3. Importa a Anki automáticamente
→ Observa indicadores visuales:
  ⬜ = Pendiente
  ✅ = Éxito (muestra cantidad)
  ❌ = Error
```

#### Indicadores Visuales

Cada sección muestra el estado de cada tipo de tarjeta:

**Set "Por Defecto"**
```
📝 ⬜    🔘 ⬜    🔲 ⬜    🔤 ⬜
Basic   Multiple Cloze   Vocab
```

**Set "Niveles Bloom"**
```
1️⃣ ⬜      2️⃣ ⬜      3️⃣ ⬜      4️⃣ ⬜
L1-Cloze  L2-Rel    L3-App    L4-Anal
```

Después de procesar:
```
📝 ✅ 12   🔘 ✅ 8    🔲 ✅ 15   🔤 ✅ 10
(12 cards) (8 cards) (15 cards) (10 cards)
```

#### Sistema de Sesiones

**Guardado Automático**
- Se guarda automáticamente antes de procesar
- Archivo: `flashcard_sessions.json`
- Mantiene últimas 10 sesiones

**Recuperar Sesión**
```
Click en "📂 Recuperar Sesión"
→ Selecciona sesión de la lista
→ Opciones:
  - 🔄 Reemplazar: Borra secciones actuales
  - ➕ Añadir: Agrega a las existentes
  - 🗑 Eliminar: Borra sesión guardada
```

**Contenido de Sesión**
- Títulos de secciones
- Rutas de imágenes
- Fecha y hora
- NO incluye: flashcards generadas (solo configuración)

#### Flashcards Pendientes

**¿Cuándo se guardan?**
- Cuando Anki no está abierto
- Cuando AnkiConnect falla
- Cuando hay error de conexión

**Archivo**: `pending_flashcards.json`

**Importar Pendientes**
```
Click en "📋 Importar Pendientes (X)"
→ Confirma importación
→ Asegúrate que Anki esté abierto
→ Se importan automáticamente
→ Se eliminan del archivo si tienen éxito
```

#### Tiempo de Procesamiento

**Por Sección**
- OCR: 10-30 segundos (depende de cantidad de imágenes)
- Generación: 10-20 segundos por tipo de tarjeta
- Importación: 1-5 segundos
- **Total**: ~1-2 minutos por sección

**Espera entre Secciones**
- 60 segundos por defecto (configurable)
- Evita límites de rate de la API
- Configurable en `wait_time` del set


### Modo 3: Automático - Videos (En Desarrollo)

**Uso**: Generación de flashcards desde videos de clases, tutoriales, conferencias.

#### Estado Actual
- ✅ Interfaz completa
- ✅ Carga y validación de videos
- ✅ Segmentación inteligente
- ✅ Transcripción con Whisper
- ⚠️ Extracción de contenido (pendiente)
- ⚠️ Generación de flashcards (pendiente)

#### Configuración de Segmentación

**Duración de Segmento**
- Rango: 1-10 minutos
- Default: 3 minutos
- Uso: Videos cortos → segmentos cortos, Videos largos → segmentos largos

**Overlap (Solapamiento)**
- Rango: 0-120 segundos
- Default: 30 segundos
- Uso: Evita cortar información importante entre segmentos

**Métodos de Segmentación**
1. **Fijo**: Corta cada X minutos (siempre activo)
2. **Detección de silencios**: Corta en pausas naturales (opcional)
3. **Análisis de transcripción**: Corta en cambios de tema (opcional)

**Idioma**
- Opciones: Español, Inglés, Francés, Alemán, Italiano, Portugués
- Usado por Whisper para transcripción

#### Límites de Video

**Formato**: MP4, AVI, MOV, MKV
**Tamaño máximo**: 2 GB
**Duración máxima**: 2 horas
**Resolución**: Sin límite (se procesa el contenido, no la calidad)

#### Flujo de Trabajo (Cuando esté completo)

```
1. Cargar video
   ↓
2. Validar formato/tamaño/duración
   ↓
3. Transcribir con Whisper (si está habilitado)
   ↓
4. Segmentar video según configuración
   ↓
5. Extraer contenido de cada segmento
   ↓
6. Generar flashcards por segmento
   ↓
7. Importar a Anki
```

#### Archivos Temporales

**Ubicación**: `temp_videos/session_YYYYMMDD_HHMMSS/`

**Contenido**:
- `segments/`: Videos segmentados (segment_001.mp4, segment_002.mp4, ...)
- `transcription.json`: Transcripción completa con timestamps
- `metadata.json`: Información de la sesión

**Limpieza**: Se eliminan automáticamente después de procesar


## 📝 Sistema de Prompts

Los prompts son las instrucciones que se envían a Gemini AI para generar flashcards. Están diseñados por expertos en pedagogía cognitiva siguiendo la Taxonomía de Bloom.

### Arquitectura de Prompts

Cada prompt tiene 4 componentes:

1. **Rol**: Define la personalidad y expertise de la IA
2. **Objetivos**: Qué debe lograr el prompt
3. **Instrucciones**: Reglas específicas de generación
4. **Formato de Salida**: Estructura exacta de la respuesta

---

## 📋 PROMPTS COMPLETOS

### Set 1: Por Defecto (4 tipos)

#### 1. Basic (Pregunta/Respuesta)

**PROMPT COMPLETO**:

```
Rol: Asesor experto en pedagogía cognitiva y diseño instruccional para niños.

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

P: [Pregunta tipo (Feynman): "¿Cómo le explicarías esto a un amigo?" o "Pon un ejemplo de la vida real de..."] R: [Explicación simplificada usando una analogía o vocabulario sencillo, máximo 2 frases]
```


#### 2. Multiple Choice (Opción Múltiple)

**PROMPT COMPLETO**:

```
Rol: Diseñador Senior de Exámenes de Certificación Técnica y Psicometría.

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
(Deja una línea en blanco entre cada par P/R)
```

#### 3. Cloze (Respuesta Anidada)

**PROMPT COMPLETO**:

```
Rol: Editor de Diseño Instruccional experto en minería de textos.

Objetivos:
Analizar el [Input_Texto_OCR] completo. Tu tarea es identificar los 10-15 conceptos técnicos, datos o definiciones más críticas del texto y convertirlos en tarjetas de memorización "Cloze" (huecos), priorizando la fidelidad al texto original.

Entradas:
Input_Texto_OCR: {texto_ocr}

Reglas de Procesamiento:
Selección Autónoma: Identifica los conceptos clave (términos técnicos, métricas, nombres propios, causas-efectos, procesos). Ignora la paja.
Fidelidad: Extrae la oración original donde aparece el concepto. Recorta lo innecesario para que la frase tenga sentido por sí sola, pero no la reescribas.
Lógica de Oclusión (Anki):
Ocultamiento: Encierra el concepto clave con {{c1::Concepto::Pista}}.
Pista: La pista (después de los dos puntos) es OBLIGATORIA para dar contexto (ej: ::Métrica, ::Algoritmo, ::Fecha).
Listas: Si encuentras una enumeración importante, usa {{c1::A}}, {{c2::B}}, {{c3::C}}.

Instrucción de Formato de Salida (Estricto)
No uses bloques de código (```), no uses JSON, y no agregues introducciones ni conclusiones.
Estructura obligatoria: 
P: [Oración en español con huecos / Término]
```

#### 4. Vocabulary (Vocabulario)

**PROMPT COMPLETO**:

```
Rol: Profesor de Inglés especializado en detectar terminología interesante en textos técnicos.

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
(Deja una línea en blanco entre cada par P/R)
```

---

### Set 2: Niveles de Bloom (4 niveles)

Basado en la Taxonomía de Bloom revisada, escalando en complejidad cognitiva.

#### Nivel 1: Cloze (Recordar)

**PROMPT COMPLETO**:

```
Rol: Editor de Diseño Instruccional experto en minería de textos y Anki.

Objetivos:
Analizar el [Input_Texto_OCR] completo. Tu tarea es identificar los 10-15 conceptos técnicos, datos fácticos, métricas o definiciones más críticas del texto y convertirlos en tarjetas de memorización "Cloze" (huecos).

Entradas:
Input_Texto_OCR: {texto_ocr}

Reglas de Procesamiento:
1. Selección Atómica: Identifica términos técnicos, constantes numéricas y nombres de autores. Ignora la paja retórica.
2. Fidelidad Estricta: Extrae la oración original donde aparece el concepto. Recorta lo innecesario para que la frase sea una oración simple (Sujeto+Verbo+Predicado) pero mantén la terminología exacta.
3. Citas: Si la frase original menciona un autor o año (ej: "Según Knuth (1978)..."), MANTENLO en la tarjeta.

Lógica de Oclusión (Anki):
- Ocultamiento: Encierra el concepto clave con {{c1::Concepto::Pista}}.
- Pista Obligatoria: La pista (después de los dos puntos) es MANDATORIA para dar contexto (ej: ::Métrica, ::Algoritmo, ::Autor).
- Listas: Si hay una enumeración vital, usa {{c1::A}}, {{c2::B}}, {{c3::C}}.

Instrucción de Formato de Salida (Estricto):
No uses bloques de código.
Estructura obligatoria:
P: [Oración en español con huecos procesados]
(Deja una línea en blanco entre tarjetas)
```

#### Nivel 2: Relaciones (Entender)

**PROMPT COMPLETO**:

```
Rol: Arquitecto de Sistemas de Conocimiento.

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
(Deja una línea en blanco entre pares)
```

#### Nivel 3: Aplicación (Aplicar)

**PROMPT COMPLETO**:

```
Rol: Entrenador Técnico de Simulaciones.

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
(Deja una línea en blanco entre pares)
```

#### Nivel 4: Análisis (Analizar)

**PROMPT COMPLETO**:

```
Rol: Diseñador Senior de Exámenes de Certificación (Psicometría).

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
(Deja una línea en blanco entre cada par P/R)
```

---

### Personalización de Prompts

#### Editar Prompts Existentes

1. Abre la aplicación
2. Click en "⚙️ Configuración"
3. Ve a la pestaña "Prompts"
4. Selecciona el tipo de tarjeta
5. Edita el texto del prompt
6. Variables disponibles: `{texto_ocr}` (se reemplaza con el texto extraído)
7. Click en "💾 Guardar"

#### Crear Set Personalizado

1. En Configuración, click en "➕ Nuevo"
2. Ingresa nombre del set
3. Edita prompts según necesites
4. Activa/desactiva tipos de tarjetas
5. Guarda el set

#### Exportar/Importar Sets

**Exportar**:
1. Configuración → Pestaña "Importar/Exportar"
2. Click en "📤 Exportar a texto"
3. Copia el JSON generado
4. Guarda en archivo o comparte

**Importar**:
1. Configuración → Pestaña "Importar/Exportar"
2. Pega el JSON en el área de texto
3. Click en "📥 Importar desde texto"
4. El set aparece en la lista


## 🔌 Comunicación con Anki

### AnkiConnect: El Puente

AnkiConnect es un add-on de Anki que expone una API REST local para que aplicaciones externas puedan interactuar con Anki.

#### Arquitectura de Comunicación

```
anki_import_interface.py
        ↓
anki_sync_manager.py
        ↓
HTTP POST → http://localhost:8765
        ↓
AnkiConnect (Add-on)
        ↓
Anki Desktop
```

### Operaciones Disponibles

#### 1. Verificar Estado de Anki

**Método**: `_check_anki_status()`

**Request**:
```json
{
    "action": "version",
    "version": 6
}
```

**Response (Éxito)**:
```json
{
    "result": 6,
    "error": null
}
```

**Response (Fallo)**:
```json
{
    "error": "Connection refused"
}
```

**Código**:
```python
def _check_anki_status(self) -> bool:
    try:
        response = requests.post(
            self.anki_url,
            json={"action": "version", "version": 6},
            timeout=5
        )
        data = response.json()
        return data.get("error") is None
    except:
        return False
```

#### 2. Crear Mazo

**Método**: `_create_deck_if_not_exists(deck_name)`

**Request**:
```json
{
    "action": "createDeck",
    "version": 6,
    "params": {
        "deck": "Flashcards - Basic"
    }
}
```

**Response**:
```json
{
    "result": 1234567890123,
    "error": null
}
```

**Comportamiento**:
- Si el mazo ya existe, no hace nada (idempotente)
- Retorna el ID del mazo
- Crea mazos anidados si el nombre contiene `::`

**Ejemplo de Mazos Anidados**:
```python
deck_name = "Universidad::Biología::Fotosíntesis"
# Crea:
# - Universidad
# - Universidad::Biología
# - Universidad::Biología::Fotosíntesis
```

#### 3. Obtener Modelos (Note Types)

**Método**: `_get_model_for_card_type(card_type)`

**Mapeo de Tipos**:
```python
TYPE_TO_MODEL = {
    "basic": "Basic",
    "multiple_choice": "Basic",
    "cloze": "Cloze",
    "vocabulary": "Basic",
    "level_1_cloze": "Cloze",
    "level_2_relations": "Basic",
    "level_3_application": "Basic",
    "level_4_analysis": "Basic"
}
```

**Request (Verificar modelo)**:
```json
{
    "action": "modelNames",
    "version": 6
}
```

**Response**:
```json
{
    "result": ["Basic", "Cloze", "Basic (and reversed card)", ...],
    "error": null
}
```

#### 4. Importar Flashcards

**Método**: `sync_flashcards_to_anki(deck_name, flashcards, card_type)`

**Request (Basic)**:
```json
{
    "action": "addNotes",
    "version": 6,
    "params": {
        "notes": [
            {
                "deckName": "Flashcards - Basic",
                "modelName": "Basic",
                "fields": {
                    "Front": "¿Qué es la fotosíntesis?",
                    "Back": "Proceso de conversión de luz en energía química"
                },
                "tags": ["auto-generated", "biology"]
            }
        ]
    }
}
```

**Request (Cloze)**:
```json
{
    "action": "addNotes",
    "version": 6,
    "params": {
        "notes": [
            {
                "deckName": "Flashcards - Cloze",
                "modelName": "Cloze",
                "fields": {
                    "Text": "La fotosíntesis ocurre en los {{c1::cloroplastos}}",
                    "Back Extra": "Proceso biológico"
                },
                "tags": ["auto-generated", "biology"]
            }
        ]
    }
}
```

**Response**:
```json
{
    "result": [1234567890123, 1234567890124, 1234567890125],
    "error": null
}
```

**Manejo de Duplicados**:
- Anki detecta duplicados automáticamente
- Si una tarjeta ya existe, retorna `null` en lugar del ID
- El sistema cuenta solo las tarjetas nuevas

**Ejemplo**:
```json
{
    "result": [1234567890123, null, 1234567890125],
    "error": null
}
// Resultado: 2 tarjetas nuevas, 1 duplicada
```


### Sistema de Reintentos

#### Flujo de Reintentos Automáticos

```
Intento 1: Importar flashcards
    ↓
¿Éxito? → SÍ → Fin
    ↓ NO
Detectar tipo de error
    ↓
¿Anki no instalado? → SÍ → Guardar pendientes + Mensaje
    ↓ NO
Intentar abrir Anki
    ↓
Esperar 10 segundos
    ↓
Intento 2: Importar flashcards
    ↓
¿Éxito? → SÍ → Fin
    ↓ NO
Esperar 10 segundos
    ↓
Intento 3: Importar flashcards (último)
    ↓
¿Éxito? → SÍ → Fin
    ↓ NO
Guardar en pending_flashcards.json
```

**Código**:
```python
def _import_to_anki_with_retry(self, anki_manager, deck_name, 
                                flashcards, card_type, max_retries=2):
    for attempt in range(max_retries + 1):
        success, msg, count = anki_manager.sync_flashcards_to_anki(
            deck_name, flashcards, card_type
        )
        
        if success:
            return success, msg, count
        
        # Detectar si Anki no está instalado
        if "not found" in msg.lower():
            self._save_pending_flashcards(...)
            return False, "Anki no instalado", 0
        
        # Si quedan reintentos
        if attempt < max_retries:
            anki_manager.ensure_anki_running()
            time.sleep(10)
    
    # Todos los intentos fallaron
    self._save_pending_flashcards(...)
    return False, "Guardado en pendientes", 0
```

### Abrir Anki Automáticamente

**Método**: `ensure_anki_running()`

**Rutas de Búsqueda (Windows)**:
```python
ANKI_PATHS = [
    r"C:\Program Files\Anki\anki.exe",
    r"C:\Program Files (x86)\Anki\anki.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Anki\anki.exe")
]
```

**Rutas de Búsqueda (Linux/Mac)**:
```python
ANKI_PATHS = [
    "/usr/bin/anki",
    "/usr/local/bin/anki",
    "/Applications/Anki.app/Contents/MacOS/anki"
]
```

**Código**:
```python
def ensure_anki_running(self) -> tuple[bool, str]:
    # Verificar si ya está corriendo
    if self._check_anki_status():
        return True, "Anki ya está corriendo"
    
    # Buscar ejecutable
    for path in ANKI_PATHS:
        if os.path.exists(path):
            try:
                subprocess.Popen([path], 
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True, f"Anki iniciado desde {path}"
            except:
                continue
    
    return False, "No se encontró Anki instalado"
```

### Estructura de Mazos

#### Nomenclatura Automática

**Formato**: `{Prefijo} - {Sección} - {Tipo}`

**Ejemplos**:
```
Flashcards - Sección 1 - Basic
Flashcards - Sección 1 - Multiple Choice
Flashcards - Sección 1 - Cloze
Flashcards - Sección 1 - Vocabulary

Flashcards - Pregunta 2 - Nivel 1 - Cloze
Flashcards - Pregunta 2 - Nivel 2 - Relaciones
Flashcards - Pregunta 2 - Nivel 3 - Aplicación
Flashcards - Pregunta 2 - Nivel 4 - Análisis
```

**Prefijo Personalizable**:
- Default: "Flashcards"
- Configurable en modo normal (campo "Deck Prefix")
- Útil para organizar por materia: "Biología", "Matemáticas", etc.

#### Organización Jerárquica

Puedes usar `::` para crear jerarquías:

**Ejemplo**:
```python
prefix = "Universidad::Biología::Fotosíntesis"
# Resultado en Anki:
# Universidad
#   └── Biología
#       └── Fotosíntesis
#           ├── Basic
#           ├── Multiple Choice
#           ├── Cloze
#           └── Vocabulary
```

### Manejo de Errores Comunes

#### Error 1: Connection Refused

**Causa**: AnkiConnect no está corriendo o Anki está cerrado

**Solución Automática**:
1. Intenta abrir Anki
2. Espera 10 segundos
3. Reintenta conexión

**Solución Manual**:
1. Abre Anki manualmente
2. Verifica que AnkiConnect esté instalado
3. Click en "Check Anki" en la interfaz

#### Error 2: Model Not Found

**Causa**: El modelo de tarjeta no existe en Anki

**Modelos Requeridos**:
- `Basic`: Viene por defecto con Anki
- `Cloze`: Viene por defecto con Anki

**Solución**:
1. Abre Anki
2. `Tools` → `Manage Note Types`
3. Verifica que existan "Basic" y "Cloze"
4. Si no existen, reinstala Anki

#### Error 3: Duplicate Note

**Causa**: La tarjeta ya existe en Anki

**Comportamiento**:
- No es un error real
- Anki simplemente no importa duplicados
- El contador muestra solo tarjetas nuevas

**Configuración de Duplicados**:
En Anki: `Tools` → `Preferences` → `Network` → "Check for duplicates"


## ⚙️ Sistema de Configuración

### Arquitectura de Configuración

```
config_sets_manager.py
    ↓
Gestiona múltiples "Sets" de configuración
    ↓
Cada Set contiene:
- Nombre
- Modelo de Gemini
- Tiempo de espera
- Modo de importación
- Tipos activos
- Prompts personalizados
```

### Archivo de Configuración

**Ubicación**: `flashcards_config.json`

**Estructura**:
```json
{
  "active_set": "Por Defecto",
  "sets": {
    "Por Defecto": {
      "name": "Por Defecto",
      "model": "gemini-2.0-flash",
      "wait_time": 80,
      "replace_mode": false,
      "active_types": {
        "basic": true,
        "multiple_choice": true,
        "cloze": true,
        "vocabulary": true
      },
      "prompts": {
        "basic": "Rol: Asesor experto...",
        "multiple_choice": "Rol: Diseñador Senior...",
        "cloze": "Rol: Editor de Diseño...",
        "vocabulary": "Rol: Profesor de Inglés..."
      }
    },
    "Niveles Bloom": {
      "name": "Niveles Bloom",
      "model": "gemini-2.0-flash",
      "wait_time": 80,
      "replace_mode": false,
      "active_types": {
        "level_1_cloze": true,
        "level_2_relations": true,
        "level_3_application": true,
        "level_4_analysis": true
      },
      "prompts": {
        "level_1_cloze": "...",
        "level_2_relations": "...",
        "level_3_application": "...",
        "level_4_analysis": "..."
      }
    }
  }
}
```

### Parámetros de Configuración

#### 1. name (string)

**Descripción**: Nombre del set de configuración

**Uso**: Identificación en la UI

**Ejemplo**: `"Por Defecto"`, `"Niveles Bloom"`, `"Matemáticas Avanzadas"`

#### 2. model (string)

**Descripción**: Modelo de Gemini a usar

**Opciones**:
- `gemini-2.0-flash` (Recomendado, más rápido)
- `gemini-1.5-pro` (Más preciso, más lento)
- `gemini-1.5-flash` (Balance)
- `gemini-1.5-flash-8b` (Más económico)

**Impacto**:
- Velocidad de generación
- Calidad de respuestas
- Costo de API

**Fallback**: Si el modelo falla, intenta automáticamente con otros modelos

#### 3. wait_time (integer)

**Descripción**: Segundos de espera entre secciones

**Rango**: 10-300 segundos

**Default**: 80 segundos

**Propósito**:
- Evitar límites de rate de la API
- Dar tiempo a Anki para procesar

**Recomendaciones**:
- API gratuita: 80-120 segundos
- API de pago: 30-60 segundos
- Testing: 10-20 segundos

#### 4. replace_mode (boolean)

**Descripción**: Modo de importación de flashcards

**Opciones**:
- `false` (Acumular): Añade tarjetas al mazo existente
- `true` (Reemplazar): Elimina mazo y crea uno nuevo

**Uso**:
- Acumular: Para ir agregando contenido
- Reemplazar: Para regenerar desde cero

**Advertencia**: Reemplazar elimina TODO el mazo, incluyendo progreso de estudio

#### 5. active_types (object)

**Descripción**: Tipos de tarjetas activos

**Estructura**:
```json
{
  "basic": true,
  "multiple_choice": false,
  "cloze": true,
  "vocabulary": false
}
```

**Comportamiento**:
- Solo se generan los tipos marcados como `true`
- Reduce tiempo de procesamiento
- Reduce costo de API

**Casos de Uso**:
- Solo Basic y Cloze para estudio rápido
- Solo Multiple Choice para exámenes
- Todos activos para cobertura completa

#### 6. prompts (object)

**Descripción**: Prompts personalizados por tipo

**Estructura**:
```json
{
  "basic": "Rol: ... Objetivo: ... {texto_ocr}",
  "cloze": "Rol: ... Objetivo: ... {texto_ocr}"
}
```

**Variable Obligatoria**: `{texto_ocr}`
- Se reemplaza con el texto extraído de las imágenes
- Debe aparecer al menos una vez en el prompt

**Edición**:
- Desde la UI: Configuración → Pestaña "Prompts"
- Resaltado automático de variables
- Botón "Restaurar por defecto"


### Gestión de Sets

#### Crear Nuevo Set

**Desde UI**:
1. Configuración → Click en "➕ Nuevo"
2. Ingresa nombre del set
3. Se copia la configuración del set actual
4. Edita según necesites
5. Guarda

**Desde JSON**:
1. Configuración → Pestaña "Importar/Exportar"
2. Pega JSON del set
3. Click en "📥 Importar desde texto"

**Programáticamente**:
```python
config_manager = ConfigSetsManager()
config_manager.create_set(
    name="Mi Set Personalizado",
    base_set="Por Defecto"  # Copia desde este set
)
```

#### Editar Set Existente

**Desde UI**:
1. Configuración → Selecciona set en dropdown
2. Edita parámetros en pestaña "General"
3. Edita prompts en pestaña "Prompts"
4. Click en "💾 Guardar"

**Cambios se aplican**:
- Inmediatamente en la UI
- En el próximo procesamiento
- Se guardan en `flashcards_config.json`

#### Eliminar Set

**Restricciones**:
- No se pueden eliminar sets predefinidos:
  - "Por Defecto"
  - "Niveles Bloom"

**Desde UI**:
1. Configuración → Selecciona set
2. Click en "🗑 Eliminar"
3. Confirma eliminación
4. Se activa "Por Defecto" automáticamente

#### Exportar Set

**Formato**: JSON

**Contenido**:
```json
{
  "name": "Mi Set",
  "model": "gemini-2.0-flash",
  "wait_time": 80,
  "replace_mode": false,
  "active_types": {...},
  "prompts": {...}
}
```

**Usos**:
- Compartir configuraciones con otros usuarios
- Backup de configuraciones
- Versionado de prompts

**Proceso**:
1. Configuración → Pestaña "Importar/Exportar"
2. Click en "📤 Exportar a texto"
3. Copia el JSON generado
4. Guarda en archivo `.json`

#### Importar Set

**Validación**:
- Verifica estructura JSON
- Valida campos obligatorios
- Detecta conflictos de nombres

**Proceso**:
1. Configuración → Pestaña "Importar/Exportar"
2. Pega JSON en el área de texto
3. Click en "📥 Importar desde texto"
4. Si el nombre existe, se sobrescribe (con confirmación)

### Sets Predefinidos

#### Set "Por Defecto"

**Características**:
- 4 tipos de tarjetas tradicionales
- Prompts generales para cualquier tema
- Balance entre cobertura y velocidad

**Tipos**:
- Basic: Pregunta/Respuesta
- Multiple Choice: Opción múltiple
- Cloze: Respuesta anidada
- Vocabulary: Vocabulario inglés

**Uso Recomendado**:
- Apuntes generales
- Diapositivas de clase
- Documentación técnica

#### Set "Niveles Bloom"

**Características**:
- 4 niveles cognitivos
- Basado en Taxonomía de Bloom
- Escalamiento de complejidad

**Tipos**:
- Nivel 1 - Cloze: Recordar
- Nivel 2 - Relaciones: Entender
- Nivel 3 - Aplicación: Aplicar
- Nivel 4 - Análisis: Analizar

**Uso Recomendado**:
- Estudio profundo
- Preparación de exámenes
- Aprendizaje conceptual

### Widgets Dinámicos

La interfaz de configuración se adapta automáticamente al set seleccionado.

**Comportamiento**:
1. Seleccionas un set en el dropdown
2. La UI detecta qué tipos tiene el set
3. Reconstruye los checkboxes de tipos activos
4. Reconstruye las pestañas de prompts
5. Carga los valores del set

**Ejemplo**:
```
Set "Por Defecto" seleccionado:
→ Muestra: Basic, Multiple Choice, Cloze, Vocabulary
→ 4 pestañas de prompts

Set "Niveles Bloom" seleccionado:
→ Muestra: Nivel 1, Nivel 2, Nivel 3, Nivel 4
→ 4 pestañas de prompts (diferentes)
```

**Código**:
```python
def rebuild_type_widgets(set_name):
    config = config_manager.get_set(set_name)
    active_types = config.get("active_types", {})
    
    # Detectar tipo de set
    if any(k.startswith("level_") for k in active_types.keys()):
        type_keys = ["level_1_cloze", "level_2_relations", ...]
    else:
        type_keys = ["basic", "multiple_choice", ...]
    
    # Reconstruir UI
    for type_key in type_keys:
        create_checkbox(type_key)
        create_prompt_tab(type_key)
```


## 🃏 Tipos de Tarjetas

### Anatomía de una Tarjeta Anki

```
┌─────────────────────────────────────┐
│ FRONT (Anverso)                     │
│                                     │
│ ¿Qué es la fotosíntesis?           │
│                                     │
└─────────────────────────────────────┘
                ↓ (Flip)
┌─────────────────────────────────────┐
│ BACK (Reverso)                      │
│                                     │
│ Proceso por el cual las plantas    │
│ convierten luz solar en energía    │
│ química.                            │
│                                     │
└─────────────────────────────────────┘
```

### Tipo 1: Basic (Pregunta/Respuesta)

**Modelo Anki**: `Basic`

**Campos**:
- `Front`: Pregunta
- `Back`: Respuesta

**Formato de Entrada**:
```
P: [Pregunta]
R: [Respuesta]
```

**Conversión a TSV**:
```
¿Qué es la fotosíntesis?\tProceso de conversión de luz en energía
¿Dónde ocurre?\tEn los cloroplastos
```

**Características**:
- Más simple y versátil
- Ideal para definiciones
- Soporta HTML y LaTeX
- Puede incluir imágenes

**Ejemplo con LaTeX**:
```
P: ¿Cuál es la fórmula de la fotosíntesis?
R: \\( 6CO_2 + 6H_2O + luz → C_6H_{12}O_6 + 6O_2 \\)
```

**Renderizado en Anki**:
- Front: "¿Cuál es la fórmula de la fotosíntesis?"
- Back: Fórmula renderizada con MathJax

### Tipo 2: Multiple Choice (Opción Múltiple)

**Modelo Anki**: `Basic` (se adapta)

**Campos**:
- `Front`: Pregunta + Opciones
- `Back`: Respuesta + Explicación

**Formato de Entrada**:
```
P: [Pregunta]
a) [Opción A]
b) [Opción B]
c) [Opción C]
d) [Opción D]
R: [Letra] - [Explicación]
```

**Conversión a TSV**:
```
¿Cuál es la función de los cloroplastos?<br>a) Respiración<br>b) Fotosíntesis<br>c) Síntesis de proteínas<br>d) Almacenar ADN\tb - Los cloroplastos realizan fotosíntesis
```

**Renderizado en Anki**:
```
Front:
¿Cuál es la función de los cloroplastos?
a) Respiración celular
b) Fotosíntesis
c) Síntesis de proteínas
d) Almacenar ADN

Back:
b - Los cloroplastos contienen clorofila y realizan fotosíntesis
```

**Ventajas**:
- Simula exámenes reales
- Distractores inteligentes
- Entrena pensamiento crítico

**Desventajas**:
- Más largo de revisar
- Puede dar pistas por eliminación

### Tipo 3: Cloze (Respuesta Anidada)

**Modelo Anki**: `Cloze`

**Campos**:
- `Text`: Texto con huecos
- `Back Extra`: Contexto adicional

**Formato de Entrada**:
```
P: Texto con {{c1::concepto::pista}}
R: [Contexto]
```

**Sintaxis de Oclusión**:
```
{{c1::texto::pista}}
│  │  │      │
│  │  │      └─ Pista (opcional pero recomendada)
│  │  └──────── Texto a ocultar
│  └─────────── Número de oclusión
└────────────── Marcador de cloze
```

**Ejemplos**:

**Oclusión Simple**:
```
P: La fotosíntesis ocurre en los {{c1::cloroplastos::orgánulo}}.
R: Proceso biológico de las plantas
```

**Renderizado**:
- Pregunta: "La fotosíntesis ocurre en los [...orgánulo...]."
- Respuesta: "La fotosíntesis ocurre en los **cloroplastos**."

**Oclusiones Múltiples**:
```
P: La fotosíntesis produce {{c1::glucosa::azúcar}} y {{c2::oxígeno::gas}}.
R: Productos de la fotosíntesis
```

**Renderizado (2 tarjetas)**:
- Tarjeta 1: "La fotosíntesis produce [...azúcar...] y oxígeno."
- Tarjeta 2: "La fotosíntesis produce glucosa y [...gas...]."

**Oclusiones Anidadas**:
```
P: {{c1::La fotosíntesis}} produce {{c1::glucosa}} y {{c1::oxígeno}}.
R: Proceso y productos
```

**Renderizado (1 tarjeta)**:
- Pregunta: "[...] produce [...] y [...]."
- Respuesta: "**La fotosíntesis** produce **glucosa** y **oxígeno**."

**Ventajas**:
- Muy eficiente para memorización
- Contexto siempre visible
- Múltiples tarjetas de una oración

**Desventajas**:
- Requiere sintaxis específica
- Puede ser confuso al principio

### Tipo 4: Vocabulary (Vocabulario)

**Modelo Anki**: `Basic`

**Campos**:
- `Front`: Término en inglés
- `Back`: Traducción + Fonética IPA

**Formato de Entrada**:
```
P: [English Term]
R: [Traducción] | [/IPA/]
```

**Conversión a TSV**:
```
Photosynthesis\tFotosíntesis | /ˌfoʊ.toʊˈsɪn.θə.sɪs/
Chloroplast\tCloroplasto | /ˈklɔː.rə.plæst/
```

**Renderizado en Anki**:
```
Front: Photosynthesis

Back:
Fotosíntesis
/ˌfoʊ.toʊˈsɪn.θə.sɪs/
```

**Características**:
- Enfoque en terminología técnica
- Incluye pronunciación
- Útil para papers en inglés

**Extensión Posible**:
Puedes agregar más información en el back:
```
R: Fotosíntesis | /ˌfoʊ.toʊˈsɪn.θə.sɪs/ | Proceso de conversión de luz
```


### Conversión de Formatos

#### Parser de Flashcards

**Archivo**: `flashcards_converter.py`

**Método Principal**: `convert(text, card_type)`

**Flujo**:
```
Texto de Gemini
    ↓
Detectar formato (P:/R:)
    ↓
Parsear según tipo
    ↓
Convertir a TSV
    ↓
Retornar string TSV
```

#### Parser Basic

**Regex**:
```python
pattern = r'P:\s*(.+?)\s*R:\s*(.+?)(?=P:|$)'
```

**Explicación**:
- `P:\s*` - Busca "P:" seguido de espacios opcionales
- `(.+?)` - Captura la pregunta (non-greedy)
- `\s*R:\s*` - Busca "R:" con espacios
- `(.+?)` - Captura la respuesta
- `(?=P:|$)` - Hasta el próximo "P:" o fin de texto

**Código**:
```python
def _parse_basic(self, text: str) -> str:
    matches = re.findall(
        r'P:\s*(.+?)\s*R:\s*(.+?)(?=P:|$)',
        text,
        re.DOTALL
    )
    
    tsv_lines = []
    for front, back in matches:
        front = front.strip()
        back = back.strip()
        if front and back:
            tsv_lines.append(f"{front}\t{back}")
    
    return "\n".join(tsv_lines)
```

#### Parser Multiple Choice

**Regex**:
```python
pattern = r'P:\s*(.+?)\s*a\)\s*(.+?)\s*b\)\s*(.+?)\s*c\)\s*(.+?)\s*d\)\s*(.+?)\s*R:\s*([a-d])\s*-\s*(.+?)(?=P:|$)'
```

**Conversión**:
```python
def _parse_multiple_choice(self, text: str) -> str:
    matches = re.findall(pattern, text, re.DOTALL)
    
    tsv_lines = []
    for question, opt_a, opt_b, opt_c, opt_d, answer, explanation in matches:
        # Construir front con opciones
        front = f"{question.strip()}<br>"
        front += f"a) {opt_a.strip()}<br>"
        front += f"b) {opt_b.strip()}<br>"
        front += f"c) {opt_c.strip()}<br>"
        front += f"d) {opt_d.strip()}"
        
        # Back con respuesta y explicación
        back = f"{answer.strip()} - {explanation.strip()}"
        
        tsv_lines.append(f"{front}\t{back}")
    
    return "\n".join(tsv_lines)
```

#### Parser Cloze

**Características Especiales**:
- Mantiene sintaxis `{{c1::texto::pista}}`
- No convierte a TSV tradicional
- Formato especial para Anki

**Código**:
```python
def _parse_cloze(self, text: str) -> str:
    matches = re.findall(
        r'P:\s*(.+?)\s*R:\s*(.+?)(?=P:|$)',
        text,
        re.DOTALL
    )
    
    tsv_lines = []
    for cloze_text, extra in matches:
        cloze_text = cloze_text.strip()
        extra = extra.strip()
        
        # Verificar que tenga sintaxis cloze
        if '{{c' in cloze_text:
            tsv_lines.append(f"{cloze_text}\t{extra}")
    
    return "\n".join(tsv_lines)
```

#### Parser Vocabulary

**Código**:
```python
def _parse_vocabulary(self, text: str) -> str:
    matches = re.findall(
        r'P:\s*(.+?)\s*R:\s*(.+?)(?=P:|$)',
        text,
        re.DOTALL
    )
    
    tsv_lines = []
    for term, translation in matches:
        term = term.strip()
        translation = translation.strip()
        if term and translation:
            tsv_lines.append(f"{term}\t{translation}")
    
    return "\n".join(tsv_lines)
```

### Manejo de Caracteres Especiales

#### LaTeX

**Entrada**:
```
R: La fórmula es \\( E = mc^2 \\)
```

**Salida TSV**:
```
¿Cuál es la fórmula?\tLa fórmula es \\( E = mc^2 \\)
```

**Renderizado en Anki**:
- Anki usa MathJax para renderizar
- Se muestra como: E = mc²

#### HTML

**Entrada**:
```
R: La fotosíntesis produce <b>glucosa</b> y <i>oxígeno</i>
```

**Salida TSV**:
```
¿Qué produce?\tLa fotosíntesis produce <b>glucosa</b> y <i>oxígeno</i>
```

**Renderizado en Anki**:
- **glucosa** (negrita)
- *oxígeno* (cursiva)

#### Saltos de Línea

**Entrada**:
```
R: Productos:
- Glucosa
- Oxígeno
```

**Salida TSV**:
```
¿Productos?\tProductos:<br>- Glucosa<br>- Oxígeno
```

**Conversión**:
```python
text = text.replace('\n', '<br>')
```

#### Tabulaciones

**Problema**: TSV usa `\t` como separador

**Solución**:
```python
text = text.replace('\t', '    ')  # 4 espacios
```


## 🔄 Sistema de Fallback

El sistema implementa múltiples niveles de fallback para garantizar robustez.

### Nivel 1: Fallback de Modelos Gemini

#### Arquitectura

```
Intento 1: gemini-2.0-flash (configurado)
    ↓
¿Éxito? → SÍ → Retornar resultado
    ↓ NO
¿Error de cuota? → SÍ → Siguiente modelo
    ↓
Intento 2: gemini-1.5-pro
    ↓
¿Éxito? → SÍ → Retornar resultado
    ↓ NO
Intento 3: gemini-1.5-flash
    ↓
¿Éxito? → SÍ → Retornar resultado
    ↓ NO
Retornar error
```

#### Lista de Modelos

**Orden de Preferencia**:
```python
FALLBACK_MODELS = [
    "gemini-2.0-flash",      # Más rápido, más reciente
    "gemini-1.5-pro",        # Más preciso
    "gemini-1.5-flash"       # Más económico
]
```

#### Detección de Errores

**Error de Cuota**:
```python
error_str = str(e).lower()
if "quota" in error_str or "429" in error_str or "resource" in error_str:
    # Probar siguiente modelo
```

**Error de Copyright**:
```python
if "copyrighted" in error_str or "finish_reason" in error_str:
    # Saltar a Tesseract OCR
```

#### Código de Implementación

```python
def generate_flashcards_single(self, texto_ocr: str, card_type: str):
    # Lista de modelos a intentar
    models_to_try = [self.model_name] + [
        m for m in self.FALLBACK_MODELS if m != self.model_name
    ]
    
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            self._log(f"🤖 [{card_type}] Modelo: {model_name}...")
            
            response = model.generate_content(prompt)
            
            if response and response.text:
                self._log(f"✅ [{card_type}] Éxito con {model_name}")
                return {
                    "success": True,
                    "content": response.text,
                    "model_used": model_name
                }
            else:
                self._log(f"⚠️ [{card_type}] Respuesta vacía, probando siguiente...")
                continue
                
        except Exception as e:
            error_str = str(e).lower()
            
            if "quota" in error_str or "429" in error_str:
                self._log(f"⚠️ [{card_type}] Cuota excedida, probando siguiente...")
                continue
            
            self._log(f"⚠️ [{card_type}] Error: {e}")
            continue
    
    # Todos los modelos fallaron
    return {"success": False, "error": "Todos los modelos fallaron"}
```

### Nivel 2: Fallback de OCR (Gemini → Tesseract)

#### Arquitectura

```
Intento 1: Gemini Vision OCR
    ↓
¿Éxito? → SÍ → Retornar texto
    ↓ NO
¿Error de copyright? → SÍ → Tesseract
    ↓
¿Tesseract instalado? → SÍ → Usar Tesseract
    ↓ NO
Retornar error
```

#### Detección de Copyright

**Trigger**:
```python
if "copyrighted" in error_str or "finish_reason" in error_str:
    self._log("⚠️ Rechazado por copyright, usando Tesseract...")
    return self._extract_with_tesseract(images)
```

**Casos Comunes**:
- Capturas de películas/series
- Logos de marcas registradas
- Contenido con watermarks

#### Tesseract OCR

**Instalación**:
```bash
# Windows
# Descargar desde: https://github.com/UB-Mannheim/tesseract/wiki
# Instalar y configurar TESSERACT_PATH en .env

# Linux
sudo apt-get install tesseract-ocr
sudo apt-get install tesseract-ocr-spa  # Español

# Mac
brew install tesseract
brew install tesseract-lang  # Idiomas adicionales
```

**Configuración en .env**:
```env
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
```

**Código**:
```python
def _extract_with_tesseract(self, images: List[tuple]) -> str:
    if not TESSERACT_AVAILABLE:
        self._log("❌ Tesseract no disponible")
        return ""
    
    # Configurar ruta
    tesseract_path = os.getenv("TESSERACT_PATH", "")
    if tesseract_path and os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    
    all_text = []
    for idx, (path, img) in enumerate(images, 1):
        self._log(f"   📄 Procesando imagen {idx}/{len(images)}...")
        
        # Extraer texto (español + inglés)
        text = pytesseract.image_to_string(img, lang='spa+eng')
        
        if text.strip():
            all_text.append(f"--- Imagen {idx} ---")
            all_text.append(text.strip())
    
    combined_text = "\n".join(all_text)
    self._log(f"✅ Tesseract OCR: {len(combined_text)} caracteres")
    
    return combined_text
```

**Ventajas de Tesseract**:
- ✅ Gratuito y open source
- ✅ No requiere API
- ✅ Funciona offline
- ✅ Soporta múltiples idiomas

**Desventajas**:
- ❌ Menos preciso que Gemini Vision
- ❌ No entiende contexto
- ❌ Problemas con handwriting
- ❌ Requiere instalación adicional


### Nivel 3: Fallback de Importación (Anki → Pendientes)

#### Arquitectura

```
Intento 1: Importar a Anki
    ↓
¿Éxito? → SÍ → Fin
    ↓ NO
¿Anki no instalado? → SÍ → Guardar pendientes
    ↓ NO
Intentar abrir Anki
    ↓
Esperar 10 segundos
    ↓
Intento 2: Importar a Anki
    ↓
¿Éxito? → SÍ → Fin
    ↓ NO
Intento 3: Importar a Anki (último)
    ↓
¿Éxito? → SÍ → Fin
    ↓ NO
Guardar en pending_flashcards.json
```

#### Archivo de Pendientes

**Ubicación**: `pending_flashcards.json`

**Estructura**:
```json
[
  {
    "timestamp": "2026-01-27 15:30:45",
    "deck_name": "Flashcards - Sección 1 - Basic",
    "card_type": "basic",
    "flashcards": [
      {
        "front": "¿Qué es la fotosíntesis?",
        "back": "Proceso de conversión de luz en energía"
      },
      {
        "front": "¿Dónde ocurre?",
        "back": "En los cloroplastos"
      }
    ],
    "error": "Connection refused",
    "count": 2
  },
  {
    "timestamp": "2026-01-27 15:31:20",
    "deck_name": "Flashcards - Sección 1 - Cloze",
    "card_type": "cloze",
    "flashcards": [...],
    "error": "Anki not running",
    "count": 5
  }
]
```

#### Guardar Pendientes

**Código**:
```python
def _save_pending_flashcards(self, deck_name, flashcards, card_type, error):
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
        
        self._log(f"💾 {len(flashcards)} flashcards guardadas en pendientes")
        
    except Exception as e:
        self._log(f"❌ Error guardando pendientes: {e}")
```

#### Importar Pendientes

**Proceso**:
1. Usuario abre Anki
2. Click en "📋 Importar Pendientes"
3. Sistema intenta importar cada lote
4. Lotes exitosos se eliminan del archivo
5. Lotes fallidos permanecen

**Código**:
```python
def import_pending_flashcards(self, anki_manager):
    if not os.path.exists(PENDING_FLASHCARDS_FILE):
        return {"success": True, "imported": 0}
    
    with open(PENDING_FLASHCARDS_FILE, 'r', encoding='utf-8') as f:
        pending = json.load(f)
    
    total_imported = 0
    still_pending = []
    
    for item in pending:
        deck_name = item["deck_name"]
        card_type = item["card_type"]
        flashcards = item["flashcards"]
        
        success, msg, count = anki_manager.sync_flashcards_to_anki(
            deck_name, flashcards, card_type
        )
        
        if success:
            total_imported += count
        else:
            still_pending.append(item)
    
    # Actualizar archivo
    if still_pending:
        with open(PENDING_FLASHCARDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(still_pending, f, ensure_ascii=False, indent=2)
    else:
        os.remove(PENDING_FLASHCARDS_FILE)
    
    return {
        "success": True,
        "imported": total_imported,
        "still_pending": len(still_pending)
    }
```

#### Contador de Pendientes

**UI**:
```
📋 Importar Pendientes (3)
```

**Actualización Automática**:
- Después de procesar secciones
- Después de importar pendientes
- Al abrir modo automático

**Código**:
```python
def _update_pending_button(self):
    count = self.flashcard_generator.get_pending_count()
    if count > 0:
        self.pending_btn.config(text=f"📋 Importar Pendientes ({count})")
    else:
        self.pending_btn.config(text="📋 Importar Pendientes")
```

### Nivel 4: Fallback de API Keys

#### Distribución de APIs

**Mapeo**:
```python
TYPE_TO_API_INDEX = {
    "basic": 1,
    "multiple_choice": 2,
    "cloze": 3,
    "vocabulary": 4,
    "level_1_cloze": 1,
    "level_2_relations": 2,
    "level_3_application": 3,
    "level_4_analysis": 4
}
```

**Ventajas**:
- Procesamiento paralelo (4 tipos simultáneos)
- Evita límites de rate por API
- Mayor throughput

**Fallback**:
Si solo tienes 1 API key:
```env
GEMINI_API_KEY_1=tu_unica_key
GEMINI_API_KEY_2=tu_unica_key
GEMINI_API_KEY_3=tu_unica_key
GEMINI_API_KEY_4=tu_unica_key
```

**Comportamiento**:
- Funciona correctamente
- Procesamiento secuencial (no paralelo)
- Más lento pero funcional


## 🖼️ Gestión de Imágenes

### Carga de Imágenes

#### Método 1: Drag & Drop

**Requisitos**:
- Biblioteca `tkinterdnd2` (opcional)
- Si no está instalada, solo funciona click

**Implementación**:
```python
def _setup_drop_bindings(self, drop_frame, section):
    try:
        drop_frame.drop_target_register('DND_Files')
        drop_frame.dnd_bind('<<Drop>>', lambda e, s=section: self._on_drop(e, s))
        drop_frame.dnd_bind('<<DragEnter>>', lambda e: drop_frame.config(bg="#c0e0c0"))
        drop_frame.dnd_bind('<<DragLeave>>', lambda e: drop_frame.config(bg="#e0e0e0"))
    except:
        # tkinterdnd2 no disponible, solo usar click
        pass
```

**Uso**:
1. Abre explorador de archivos
2. Selecciona imágenes
3. Arrastra sobre el área gris de la sección
4. Suelta

**Feedback Visual**:
- Hover: Fondo verde claro (#c0e0c0)
- Normal: Fondo gris (#e0e0e0)

#### Método 2: Click para Seleccionar

**Implementación**:
```python
def browse_images(self, section: ImageSection):
    filetypes = [
        ("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tiff *.ico"),
        ("Todos los archivos", "*.*")
    ]
    files = filedialog.askopenfilenames(
        title="Seleccionar imágenes",
        filetypes=filetypes
    )
    
    for file_path in files:
        self._add_image_to_section(section, file_path)
```

**Uso**:
1. Click en área gris de la sección
2. Se abre explorador de archivos
3. Selecciona múltiples imágenes (Ctrl+Click)
4. Click en "Abrir"

**Ventajas**:
- Funciona siempre (no requiere tkinterdnd2)
- Selección múltiple
- Filtro por tipo de archivo

#### Método 3: Pegar desde Portapapeles

**Requisitos**:
- Biblioteca `PIL.ImageGrab`
- Incluida en Pillow

**Implementación**:
```python
def paste_from_clipboard(self, section: ImageSection):
    try:
        from PIL import ImageGrab
        
        img = ImageGrab.grabclipboard()
        
        if img is None:
            self.auto_log("⚠️ No hay imagen en el portapapeles")
            return
        
        if not isinstance(img, Image.Image):
            self.auto_log("⚠️ El contenido no es una imagen")
            return
        
        # Guardar temporalmente
        import tempfile
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_path = os.path.join(temp_dir, f"clipboard_{timestamp}.png")
        
        img.save(temp_path, "PNG")
        self.auto_log("📋 Imagen pegada desde portapapeles")
        
        # Añadir a la sección
        self._add_image_to_section(section, temp_path)
        
    except Exception as e:
        self.auto_log(f"❌ Error al pegar: {e}")
```

**Uso**:
1. Haz captura de pantalla (Win+Shift+S en Windows)
2. Click en botón "📋 Pegar" de la sección
3. La imagen se guarda automáticamente en temp

**Ubicación Temporal**:
- Windows: `C:\Users\<usuario>\AppData\Local\Temp\`
- Linux: `/tmp/`
- Mac: `/var/folders/.../T/`

**Formato**: `clipboard_YYYYMMDD_HHMMSS.png`

### Validación de Imágenes

#### Tamaño Máximo

**Límite**: 25 MB por imagen

**Razón**: Límite de Gemini API

**Validación**:
```python
file_size = os.path.getsize(path)
if file_size > 25 * 1024 * 1024:
    return {"error": f"Imagen excede 25 MB: {os.path.basename(path)}"}
```

**Mensaje de Error**:
```
❌ Error: Imagen excede 25 MB: foto_grande.jpg
```

#### Formatos Soportados

**Lista**:
```python
SUPPORTED_FORMATS = (
    '.png', '.jpg', '.jpeg', '.gif', 
    '.bmp', '.webp', '.tiff', '.ico'
)
```

**Validación**:
```python
if not file_path.lower().endswith(self.SUPPORTED_FORMATS):
    return {"error": "Formato no soportado"}
```

#### Integridad de Imagen

**Validación con PIL**:
```python
try:
    img = Image.open(path)
    img_format = img.format or path.split('.')[-1].upper()
    # Imagen válida
except Exception as e:
    return {"error": f"Imagen corrupta: {e}"}
```

### Thumbnails (Miniaturas)

#### Generación

**Tamaño**: 100x100 píxeles (mantiene aspect ratio)

**Código**:
```python
img = Image.open(path)
thumbnail = img.copy()
thumbnail.thumbnail((100, 100))

image_data = {
    "path": path,
    "thumbnail": thumbnail,  # PIL Image object
    "width": img.width,
    "height": img.height
}
```

#### Conversión a PhotoImage

**Para Tkinter**:
```python
photo = ImageTk.PhotoImage(img_data["thumbnail"])
self.thumbnail_refs[section.section_id].append(photo)

thumb_label = ttk.Label(thumb_container, image=photo)
thumb_label.pack()
```

**Importante**: Mantener referencia
```python
# ❌ MAL (la imagen desaparece)
thumb_label = ttk.Label(container, image=ImageTk.PhotoImage(img))

# ✅ BIEN (mantener referencia)
photo = ImageTk.PhotoImage(img)
self.thumbnail_refs.append(photo)
thumb_label = ttk.Label(container, image=photo)
```

#### Botón de Eliminación

**Posicionamiento**:
```python
delete_btn = tk.Button(
    thumb_container,
    text="×",
    fg="red",
    font=("Arial", 10, "bold"),
    command=lambda s=section, i=idx: self._remove_image(s, i),
    relief="flat",
    bd=0
)
delete_btn.place(relx=1.0, rely=0, anchor="ne")
```

**Estilo**:
- Símbolo: × (multiplicación)
- Color: Rojo
- Posición: Esquina superior derecha
- Sin borde

### Información de Imágenes

#### Metadatos Almacenados

```python
image_data = {
    "path": "/ruta/completa/imagen.png",
    "name": "imagen.png",
    "size": 1234567,  # bytes
    "format": "PNG",
    "date": "2026-01-27 15:30:45",
    "thumbnail": <PIL.Image>,
    "width": 1920,
    "height": 1080
}
```

#### Display de Información

**Por Sección**:
```
4 imágenes - 3.45 MB total
```

**Código**:
```python
count = len(section.images)
total_size = sum(img["size"] for img in section.images) / (1024 * 1024)
info_label.config(
    text=f"{count} imagen{'es' if count != 1 else ''} - {total_size:.2f} MB total"
)
```

#### Tooltip al Hover

**Implementación**:
```python
def _show_tooltip(self, event, text):
    self.tooltip = tk.Toplevel()
    self.tooltip.wm_overrideredirect(True)
    self.tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
    label = tk.Label(self.tooltip, text=text, bg="yellow", relief="solid", bd=1)
    label.pack()

def _hide_tooltip(self, event):
    if hasattr(self, 'tooltip'):
        self.tooltip.destroy()

# Bind
thumb_label.bind("<Enter>", lambda e, n=img_data["name"]: self._show_tooltip(e, n))
thumb_label.bind("<Leave>", self._hide_tooltip)
```

**Muestra**: Nombre del archivo al pasar el mouse


## 📝 Modo Manual

El modo manual permite entrada directa de texto sin usar IA.

### Interfaz

**Componentes**:
- 4 cajitas de texto (Text widgets)
- Selector de prefijo de mazo
- Botones de acción
- Panel de logs
- Indicador de estado de Anki

### Casos de Uso

#### 1. Texto Ya Formateado

**Escenario**: Tienes flashcards en formato P:/R: de otra fuente

**Proceso**:
1. Copia el texto
2. Pega en la cajita correspondiente
3. Click en "Convert & Import"

**Ventaja**: No consume API de Gemini

#### 2. Conversión de Formato

**Escenario**: Tienes flashcards en otro formato y quieres convertirlas

**Ejemplo**:
```
Entrada (formato libre):
¿Qué es X?
Respuesta: Y

¿Qué es Z?
Respuesta: W

Salida (formato P:/R:):
P: ¿Qué es X?
R: Y

P: ¿Qué es Z?
R: W
```

#### 3. Testing y Debugging

**Escenario**: Quieres probar el parser sin usar IA

**Proceso**:
1. Escribe flashcards de prueba
2. Click en "Count Cards" para verificar parsing
3. Ajusta formato si es necesario
4. Importa cuando esté correcto

#### 4. Edición Manual

**Escenario**: Generaste flashcards con IA pero quieres editarlas

**Proceso**:
1. Genera con modo automático
2. Copia el texto generado (desde logs o archivo)
3. Pega en modo manual
4. Edita manualmente
5. Importa versión editada

### Botones de Acción

#### Convert & Import to Anki

**Función**: Convierte y importa todas las cajitas con contenido

**Proceso**:
```
Para cada cajita con texto:
1. Parsear según tipo
2. Convertir a TSV
3. Crear mazo en Anki
4. Importar flashcards
5. Mostrar resultado en logs
```

**Logs**:
```
==================================================
Starting conversion and import...

→ Processing Basic (Anverso/Reverso)...
  Input length: 245 chars
✓ Imported 12 flashcards to deck: Flashcards - Basic

→ Processing Cloze (Respuesta Anidada)...
  Input length: 189 chars
✓ Imported 8 flashcards to deck: Flashcards - Cloze

==================================================
✓ Total imported: 20 flashcards
```

#### Export as TSV

**Función**: Exporta todas las cajitas a un archivo TSV

**Formato del Archivo**:
```tsv
# Basic (Anverso/Reverso)
¿Qué es X?	Respuesta X
¿Qué es Y?	Respuesta Y

# Cloze (Respuesta Anidada)
Texto con {{c1::hueco}}	Contexto
Otro {{c1::ejemplo}}	Más contexto
```

**Uso**:
- Backup de flashcards
- Compartir con otros
- Importar manualmente a Anki

**Proceso**:
1. Click en "Export as TSV"
2. Selecciona ubicación y nombre
3. Se guarda archivo .tsv

#### Clear All

**Función**: Limpia todas las cajitas de texto

**Confirmación**: No pide confirmación (cuidado)

**Uso**: Empezar de cero

#### Count Cards

**Función**: Cuenta flashcards en una cajita específica

**Proceso**:
1. Click en "Count Cards" de una cajita
2. Parsea el contenido
3. Muestra popup con cantidad

**Ejemplo de Popup**:
```
Basic (Anverso/Reverso)

Total flashcards: 12
```

**Uso**:
- Verificar que el formato es correcto
- Saber cuántas tarjetas se importarán
- Debugging de parsing

### Prefijo de Mazo

**Campo**: "Deck Prefix"

**Default**: "Flashcards"

**Uso**: Personalizar nombre de mazos

**Ejemplos**:
```
Prefix: "Biología"
→ Mazos: Biología - Basic, Biología - Cloze, etc.

Prefix: "Universidad::Matemáticas"
→ Mazos: Universidad::Matemáticas - Basic, etc.
```

**Jerarquía**:
Usa `::` para crear estructura:
```
Universidad
└── Matemáticas
    ├── Basic
    ├── Cloze
    └── Vocabulary
```

### Formato de Entrada Detallado

#### Basic

**Formato Estricto**:
```
P: [Pregunta]
R: [Respuesta]

P: [Siguiente pregunta]
R: [Siguiente respuesta]
```

**Reglas**:
- Debe empezar con "P:"
- Debe tener "R:" después
- Línea en blanco entre pares (opcional pero recomendado)
- Espacios después de P: y R: son opcionales

**Válido**:
```
P:¿Qué es X?
R:Respuesta X

P: ¿Qué es Y?
R: Respuesta Y
```

**Inválido**:
```
¿Qué es X?
Respuesta X

Pregunta: ¿Qué es Y?
Respuesta: Respuesta Y
```

#### Multiple Choice

**Formato Estricto**:
```
P: [Pregunta]
a) [Opción A]
b) [Opción B]
c) [Opción C]
d) [Opción D]
R: [letra] - [Explicación]
```

**Reglas**:
- Exactamente 4 opciones (a, b, c, d)
- Respuesta debe ser letra minúscula
- Guion después de la letra
- Explicación obligatoria

**Válido**:
```
P: ¿Cuál es correcto?
a) Opción 1
b) Opción 2
c) Opción 3
d) Opción 4
R: b - Porque es la correcta
```

**Inválido**:
```
P: ¿Cuál es correcto?
1) Opción 1
2) Opción 2
R: 2
```

#### Cloze

**Formato Estricto**:
```
P: Texto con {{c1::concepto::pista}}
R: [Contexto]
```

**Reglas**:
- Debe contener `{{c1::...}}`
- Número de oclusión (c1, c2, c3, etc.)
- Pista es opcional pero recomendada
- Doble llave de apertura y cierre

**Válido**:
```
P: La {{c1::fotosíntesis::proceso}} ocurre en {{c2::cloroplastos::orgánulo}}.
R: Proceso biológico

P: Python fue creado en {{c1::1991::año}}.
R: Historia de Python
```

**Inválido**:
```
P: La [fotosíntesis] ocurre en [cloroplastos].
R: Proceso biológico

P: Python fue creado en {1991}.
R: Historia de Python
```

#### Vocabulary

**Formato Estricto**:
```
P: [English Term]
R: [Traducción] | [/IPA/]
```

**Reglas**:
- Término en inglés en Front
- Traducción + fonética en Back
- Separador: `|` (pipe)
- IPA entre barras `/.../ `

**Válido**:
```
P: Photosynthesis
R: Fotosíntesis | /ˌfoʊ.toʊˈsɪn.θə.sɪs/

P: Algorithm
R: Algoritmo | /ˈæl.ɡə.rɪ.ðəm/
```

**Inválido**:
```
P: Photosynthesis
R: Fotosíntesis

P: Algorithm
R: Algoritmo (al-go-rit-mo)
```

### Logs del Modo Manual

**Ubicación**: Panel inferior de la interfaz

**Contenido**:
- Estado de Anki
- Progreso de conversión
- Errores de parsing
- Cantidad de tarjetas importadas

**Ejemplo**:
```
✓ Anki is running
==================================================
Starting conversion and import...

→ Processing Basic (Anverso/Reverso)...
  Input length: 245 chars
✓ Imported 12 flashcards to deck: Flashcards - Basic

⊘ Multiple Choice (Opción Múltiple): No input

→ Processing Cloze (Respuesta Anidada)...
  Input length: 189 chars
✗ Cloze (Respuesta Anidada): No flashcards parsed

⊘ Vocabulary (Vocabulario): No input

==================================================
✓ Total imported: 12 flashcards
```

**Símbolos**:
- ✓ : Éxito
- ✗ : Error
- ⊘ : Sin entrada
- → : Procesando


## 🎬 Procesamiento de Videos

**Estado**: En desarrollo (UI completa, procesamiento pendiente)

### Arquitectura

```
video_processor.py
    ↓
1. Validar video (formato, tamaño, duración)
    ↓
2. Transcribir con Whisper (opcional)
    ↓
3. Segmentar video
    ↓
4. Cortar segmentos con FFmpeg
    ↓
5. [PENDIENTE] Enviar segmentos a Gemini
    ↓
6. [PENDIENTE] Generar flashcards
```

### Configuración

#### Duración de Segmento

**Rango**: 1-10 minutos
**Default**: 3 minutos
**Uso**: Controla el tamaño de cada segmento

**Recomendaciones**:
- Videos cortos (< 15 min): 2-3 minutos
- Videos medianos (15-60 min): 3-5 minutos
- Videos largos (> 60 min): 5-10 minutos

#### Overlap (Solapamiento)

**Rango**: 0-120 segundos
**Default**: 30 segundos
**Uso**: Evita cortar información importante

**Ejemplo**:
```
Segmento 1: 0:00 - 3:00
Segmento 2: 2:30 - 5:30  (overlap de 30s)
Segmento 3: 5:00 - 8:00  (overlap de 30s)
```

#### Métodos de Segmentación

**1. Fijo (Siempre activo)**
- Corta cada X minutos
- Predecible y simple
- Puede cortar en medio de una idea

**2. Detección de Silencios (Opcional)**
- Usa FFmpeg para detectar pausas
- Corta en silencios naturales
- Más inteligente pero más lento

**3. Análisis de Transcripción (Opcional)**
- Usa Whisper para transcribir
- Analiza cambios de tema
- Más preciso pero más costoso

**Combinación**:
Puedes usar los 3 métodos simultáneamente:
```
1. Genera cortes fijos cada 3 minutos
2. Detecta silencios cercanos a esos cortes
3. Analiza transcripción para validar
4. Combina todos los puntos de corte
5. Elimina duplicados (tolerancia 5 segundos)
```

#### Idioma

**Opciones**: Español, Inglés, Francés, Alemán, Italiano, Portugués

**Uso**: Para transcripción con Whisper

**Importante**: Selecciona el idioma correcto para mejor precisión

### Límites de Video

**Formato**: MP4, AVI, MOV, MKV
**Tamaño máximo**: 2 GB
**Duración máxima**: 2 horas
**Resolución**: Sin límite

**Validación**:
```python
def validate_video(video_path):
    # Verificar extensión
    ext = os.path.splitext(video_path)[1].lower()
    if ext not in ['.mp4', '.avi', '.mov', '.mkv']:
        return False, "Formato no soportado"
    
    # Verificar tamaño
    size = os.path.getsize(video_path)
    if size > 2 * 1024 * 1024 * 1024:
        return False, "Archivo muy grande (máx 2GB)"
    
    # Verificar duración
    probe = ffmpeg.probe(video_path)
    duration = float(probe['format']['duration'])
    if duration > 7200:  # 2 horas
        return False, "Video muy largo (máx 2 horas)"
    
    return True, "Video válido"
```

### Whisper Transcription

**Modelo**: Local (no API)

**Instalación**:
```bash
pip install openai-whisper
```

**Modelos Disponibles**:
- `tiny`: Más rápido, menos preciso
- `base`: Balance (default)
- `small`: Más preciso
- `medium`: Muy preciso, más lento
- `large`: Máxima precisión, muy lento

**Uso**:
```python
model = whisper.load_model("base")
result = model.transcribe(
    video_path,
    language="es",
    word_timestamps=True,
    verbose=False
)
```

**Output**:
```json
{
  "text": "Transcripción completa del video...",
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "Hola, bienvenidos a esta clase..."
    },
    {
      "start": 5.2,
      "end": 12.8,
      "text": "Hoy vamos a hablar sobre fotosíntesis..."
    }
  ]
}
```

### Archivos Temporales

**Ubicación**: `temp_videos/session_YYYYMMDD_HHMMSS/`

**Estructura**:
```
temp_videos/
└── session_20260127_153045/
    ├── segments/
    │   ├── segment_001.mp4
    │   ├── segment_002.mp4
    │   └── segment_003.mp4
    ├── transcription.json
    └── metadata.json
```

**metadata.json**:
```json
{
  "session_id": "20260127_153045",
  "original_video": "clase_biologia.mp4",
  "duration": 1800.5,
  "language": "es",
  "segment_duration": 180,
  "overlap": 30,
  "use_silence_detection": false,
  "use_transcription_analysis": true,
  "segments": [
    {
      "id": 1,
      "start": 0.0,
      "end": 180.0,
      "duration": 180.0,
      "file": "segment_001.mp4"
    }
  ]
}
```

**Limpieza**:
- Automática después de procesar
- Manual con `cleanup_session(session_dir)`

### Pendiente de Implementación

**1. Envío de Segmentos a Gemini**
```python
# TODO: Implementar
def process_video_segment(segment_path):
    # Subir segmento a Gemini File API
    file = genai.upload_file(segment_path)
    
    # Generar flashcards del video
    response = model.generate_content([
        "Analiza este video y genera flashcards...",
        file
    ])
    
    return response.text
```

**2. Extracción de Frames (Alternativa)**
```python
# TODO: Implementar si Gemini no acepta videos
def extract_key_frames(segment_path, num_frames=3):
    # Extraer frames distribuidos uniformemente
    # Usar FFmpeg o OpenCV
    # Retornar lista de imágenes
    pass
```

**3. Integración con Generador**
```python
# TODO: Conectar con gemini_flashcard_generator
def process_video_segments(segments):
    for segment in segments:
        # Procesar segmento
        content = extract_content(segment)
        
        # Generar flashcards
        flashcards = generator.generate_all_flashcards_parallel(content)
        
        # Importar a Anki
        import_flashcards(flashcards)
```


## 🔧 Troubleshooting

### Problema 1: "Anki is not running"

**Síntomas**:
- Botón "Check Anki" muestra mensaje rojo
- Importación falla con "Connection refused"

**Causas Posibles**:
1. Anki no está abierto
2. AnkiConnect no está instalado
3. AnkiConnect está deshabilitado
4. Puerto 8765 bloqueado

**Soluciones**:

**1. Abrir Anki**:
```
- Abre Anki manualmente
- Espera 5 segundos
- Click en "Check Anki" nuevamente
```

**2. Verificar AnkiConnect**:
```
En Anki:
Tools → Add-ons → Busca "AnkiConnect"
Si no aparece:
  Tools → Add-ons → Get Add-ons...
  Código: 2055492159
  Reinicia Anki
```

**3. Verificar Puerto**:
```bash
# Windows
netstat -ano | findstr :8765

# Linux/Mac
lsof -i :8765
```

**4. Configurar Firewall**:
```
Permite conexiones locales al puerto 8765
```

### Problema 2: "API Key no configurada"

**Síntomas**:
- Botón "🔌 Chequear API" muestra errores
- Procesamiento falla inmediatamente

**Causas**:
- Archivo `.env` no existe
- API keys vacías o incorrectas
- Variables mal nombradas

**Soluciones**:

**1. Verificar .env**:
```bash
# Debe existir en la raíz del proyecto
ls -la .env  # Linux/Mac
dir .env     # Windows
```

**2. Verificar Contenido**:
```env
# Debe tener estas variables
GEMINI_API_KEY_OCR=AIza...
GEMINI_API_KEY_1=AIza...
GEMINI_API_KEY_2=AIza...
GEMINI_API_KEY_3=AIza...
GEMINI_API_KEY_4=AIza...
```

**3. Obtener API Keys**:
```
1. Ve a: https://makersuite.google.com/app/apikey
2. Inicia sesión
3. Click en "Create API Key"
4. Copia y pega en .env
```

**4. Reiniciar Aplicación**:
```bash
# Cierra la aplicación
# Vuelve a abrir
python anki_import_interface.py
```

### Problema 3: "No se pudieron parsear flashcards"

**Síntomas**:
- Logs muestran "⚠️ [tipo] No se pudieron parsear flashcards"
- Contador muestra 0 tarjetas

**Causas**:
1. Gemini no siguió el formato P:/R:
2. Respuesta vacía de Gemini
3. Error en el prompt

**Soluciones**:

**1. Verificar Logs**:
```
Busca en logs:
"✅ [tipo] Respuesta recibida (X chars)"

Si X es muy pequeño (< 100):
  - Gemini no generó contenido suficiente
  - Revisa el prompt
```

**2. Verificar Prompt**:
```
Configuración → Pestaña "Prompts"
Verifica que contenga:
  - Variable {texto_ocr}
  - Instrucciones de formato P:/R:
  - Ejemplos claros
```

**3. Probar con Texto Simple**:
```
Usa texto muy simple para testing:
"La fotosíntesis es un proceso biológico."

Si funciona con texto simple:
  - El problema es el contenido complejo
  - Simplifica las imágenes
```

**4. Restaurar Prompt por Defecto**:
```
Configuración → Pestaña "Prompts"
Click en "🔄 Restaurar por defecto"
```

### Problema 4: "Quota exceeded" o "429 Error"

**Síntomas**:
- Logs muestran "⚠️ Cuota excedida"
- Procesamiento se detiene

**Causas**:
- Límite de requests por minuto alcanzado
- Límite diario alcanzado
- API key gratuita con límites bajos

**Soluciones**:

**1. Esperar**:
```
Límites típicos (API gratuita):
- 60 requests por minuto
- 1500 requests por día

Espera 1 minuto y reintenta
```

**2. Aumentar wait_time**:
```
Configuración → General
wait_time: 120 segundos (en lugar de 80)
```

**3. Usar Menos Tipos**:
```
Configuración → General
Desactiva algunos tipos de tarjetas
Ejemplo: Solo Basic y Cloze
```

**4. Upgrade a API de Pago**:
```
Google Cloud Console
Habilita billing
Límites mucho más altos
```

### Problema 5: "Tesseract not found"

**Síntomas**:
- Fallback a Tesseract falla
- Mensaje "❌ Tesseract no disponible"

**Causas**:
- Tesseract no instalado
- Ruta incorrecta en .env

**Soluciones**:

**1. Instalar Tesseract**:

**Windows**:
```
1. Descarga: https://github.com/UB-Mannheim/tesseract/wiki
2. Instala en: C:\Program Files\Tesseract-OCR\
3. Agrega a PATH o configura en .env
```

**Linux**:
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
sudo apt-get install tesseract-ocr-spa  # Español
```

**Mac**:
```bash
brew install tesseract
brew install tesseract-lang  # Idiomas adicionales
```

**2. Configurar .env**:
```env
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
```

**3. Verificar Instalación**:
```bash
tesseract --version
```

### Problema 6: "Flashcards pendientes no se importan"

**Síntomas**:
- Click en "Importar Pendientes"
- Sigue mostrando contador
- No se importan a Anki

**Causas**:
1. Anki sigue cerrado
2. Modelo de tarjeta no existe
3. Error en formato de pendientes

**Soluciones**:

**1. Verificar Anki**:
```
- Abre Anki
- Espera que cargue completamente
- Click en "Check Anki" (debe estar verde)
- Reintenta importar pendientes
```

**2. Verificar Modelos**:
```
En Anki:
Tools → Manage Note Types
Verifica que existan:
  - Basic
  - Cloze
```

**3. Verificar Archivo**:
```
Abre: pending_flashcards.json
Verifica estructura JSON válida
Si está corrupto, elimínalo y regenera
```

**4. Importar Manualmente**:
```
1. Abre pending_flashcards.json
2. Copia las flashcards
3. Usa modo manual para importar
```

### Problema 7: "Video processing failed"

**Síntomas**:
- Error al procesar video
- Segmentación falla

**Causas**:
1. FFmpeg no instalado
2. Whisper no instalado
3. Video corrupto
4. Formato no soportado

**Soluciones**:

**1. Instalar FFmpeg**:

**Windows**:
```
1. Descarga: https://ffmpeg.org/download.html
2. Extrae a C:\ffmpeg\
3. Agrega a PATH: C:\ffmpeg\bin\
```

**Linux**:
```bash
sudo apt-get install ffmpeg
```

**Mac**:
```bash
brew install ffmpeg
```

**2. Instalar Whisper**:
```bash
pip install openai-whisper
```

**3. Verificar Video**:
```
- Abre el video en VLC
- Verifica que se reproduzca correctamente
- Convierte a MP4 si es necesario
```

**4. Reducir Configuración**:
```
- Desactiva "Detección de silencios"
- Desactiva "Análisis de transcripción"
- Usa solo segmentación fija
```

### Logs de Debugging

**Ubicación**: Panel de logs en la interfaz

**Niveles**:
- ✅ : Éxito
- ⚠️ : Advertencia
- ❌ : Error
- ℹ️ : Información

**Guardar Logs**:
```python
# Los logs se muestran en tiempo real
# Para guardar, copia desde la interfaz
# O redirige stdout a archivo:
python anki_import_interface.py > logs.txt 2>&1
```


## 📁 Estructura del Proyecto

```
PP001-api_gemini/
│
├── 📄 anki_import_interface.py      # Interfaz gráfica principal
│   ├── Clase: AnkiImportInterface
│   ├── Modo Normal (entrada manual)
│   ├── Modo Automático - Imágenes
│   ├── Modo Automático - Videos
│   └── Sistema de configuración UI
│
├── 📄 gemini_flashcard_generator.py # Generador con Gemini AI
│   ├── Clase: GeminiFlashcardGenerator
│   ├── OCR con Gemini Vision
│   ├── Generación paralela (4 APIs)
│   ├── Sistema de fallback
│   └── Gestión de pendientes
│
├── 📄 flashcards_converter.py       # Conversión de formatos
│   ├── Clase: FlashcardsConverter
│   ├── Parser Basic
│   ├── Parser Multiple Choice
│   ├── Parser Cloze
│   └── Parser Vocabulary
│
├── 📄 anki_sync_manager.py          # Comunicación con Anki
│   ├── Clase: AnkiSyncManager
│   ├── AnkiConnect API
│   ├── Creación de mazos
│   ├── Importación de tarjetas
│   └── Sistema de reintentos
│
├── 📄 config_sets_manager.py        # Gestión de configuración
│   ├── Clase: ConfigSetsManager
│   ├── DEFAULT_PROMPTS (Set 1)
│   ├── DEFAULT_PROMPTS2 (Set 2 - Bloom)
│   ├── Carga/guardado de sets
│   └── Importar/exportar JSON
│
├── 📄 video_processor.py            # Procesamiento de videos
│   ├── Clase: VideoProcessor
│   ├── Validación de videos
│   ├── Transcripción con Whisper
│   ├── Segmentación inteligente
│   ├── Detección de silencios
│   └── Corte con FFmpeg
│
├── 📄 .env                          # Variables de entorno (NO en Git)
│   ├── GEMINI_API_KEY_OCR
│   ├── GEMINI_API_KEY_1 a 4
│   ├── GEMINI_MODEL
│   ├── TESSERACT_PATH
│   └── ANKI_CONNECT_URL
│
├── 📄 .env.example                  # Plantilla de .env
│
├── 📄 flashcards_config.json        # Configuración de sets
│   ├── active_set
│   └── sets: {Por Defecto, Niveles Bloom, ...}
│
├── 📄 flashcard_sessions.json       # Sesiones guardadas
│   └── Últimas 10 sesiones de imágenes
│
├── 📄 pending_flashcards.json       # Flashcards pendientes
│   └── Lotes que fallaron al importar
│
├── 📄 highlights.json               # (No usado actualmente)
│
├── 📄 requirements.txt              # Dependencias completas
│   ├── google-generativeai
│   ├── python-dotenv
│   ├── Pillow
│   ├── requests
│   ├── openai-whisper
│   └── ffmpeg-python
│
├── 📄 requirements_minimal.txt      # Dependencias mínimas
│   └── Sin video processing
│
├── 📄 README.md                     # Esta documentación
│
├── 📄 arquitectura_PP001.excalidraw # Diagrama de arquitectura
├── 📄 arquitectura_PP001.png        # Diagrama (PNG)
├── 📄 arquitectura_PP001.svg        # Diagrama (SVG)
│
├── 📁 temp_videos/                  # Videos temporales (Git ignore)
│   └── session_*/
│       ├── segments/
│       ├── transcription.json
│       └── metadata.json
│
├── 📁 venv/                         # Entorno virtual (Git ignore)
│
├── 📁 __pycache__/                  # Cache de Python (Git ignore)
│
├── 📁 build/                        # Build artifacts (Git ignore)
│
└── 📁 dist/                         # Distribución (Git ignore)
```

### Archivos Principales

#### anki_import_interface.py (1787 líneas)

**Responsabilidades**:
- Interfaz gráfica con Tkinter
- Gestión de 3 modos de operación
- Sistema de secciones dinámicas
- Carga y visualización de imágenes
- Integración con todos los módulos
- Logs en tiempo real

**Clases**:
- `ImageSection`: Representa una sección con imágenes
- `AnkiImportInterface`: Interfaz principal

**Métodos Clave**:
- `setup_normal_mode()`: UI modo manual
- `setup_automatic_images_mode()`: UI modo imágenes
- `setup_automatic_videos_mode()`: UI modo videos
- `process_all_sections_auto()`: Procesamiento automático
- `show_config_dialog()`: Ventana de configuración

#### gemini_flashcard_generator.py (790 líneas)

**Responsabilidades**:
- Comunicación con Gemini API
- OCR de imágenes
- Generación de flashcards
- Sistema de fallback
- Gestión de pendientes

**Métodos Clave**:
- `extract_text_from_images()`: OCR con Gemini Vision
- `generate_all_flashcards_parallel()`: Generación paralela
- `generate_flashcards_single()`: Generación individual
- `_extract_with_tesseract()`: Fallback OCR
- `import_pending_flashcards()`: Importar pendientes

#### flashcards_converter.py (~200 líneas)

**Responsabilidades**:
- Parsing de respuestas de Gemini
- Conversión a formato TSV
- Manejo de formatos especiales

**Métodos Clave**:
- `convert()`: Método principal
- `_parse_basic()`: Parser Basic
- `_parse_multiple_choice()`: Parser Multiple Choice
- `_parse_cloze()`: Parser Cloze
- `_parse_vocabulary()`: Parser Vocabulary

#### anki_sync_manager.py (~300 líneas)

**Responsabilidades**:
- Comunicación con AnkiConnect
- Creación de mazos
- Importación de tarjetas
- Reintentos automáticos

**Métodos Clave**:
- `sync_flashcards_to_anki()`: Importación principal
- `_check_anki_status()`: Verificar conexión
- `_create_deck_if_not_exists()`: Crear mazo
- `ensure_anki_running()`: Abrir Anki

#### config_sets_manager.py (~400 líneas)

**Responsabilidades**:
- Gestión de sets de configuración
- Prompts predefinidos
- Carga/guardado de configuración
- Importar/exportar JSON

**Constantes**:
- `DEFAULT_PROMPTS`: Set "Por Defecto"
- `DEFAULT_PROMPTS2`: Set "Niveles Bloom"

**Métodos Clave**:
- `get_active_set()`: Obtener set activo
- `create_set()`: Crear nuevo set
- `update_set()`: Actualizar set
- `export_set()`: Exportar a JSON
- `import_set()`: Importar desde JSON

#### video_processor.py (~500 líneas)

**Responsabilidades**:
- Validación de videos
- Transcripción con Whisper
- Segmentación inteligente
- Corte con FFmpeg
- Gestión de archivos temporales

**Métodos Clave**:
- `validate_video()`: Validar formato/tamaño
- `transcribe_video()`: Transcripción con Whisper
- `segment_by_fixed_duration()`: Segmentación fija
- `segment_by_silence()`: Detección de silencios
- `segment_by_transcription_analysis()`: Análisis de contenido
- `process_video()`: Procesamiento completo

### Archivos de Configuración

#### .env

**Propósito**: Variables de entorno sensibles

**NO incluir en Git**: Añadido a `.gitignore`

**Contenido**:
- API keys de Gemini
- Configuración de modelos
- Rutas de herramientas externas

#### flashcards_config.json

**Propósito**: Configuración de sets

**Incluir en Git**: Sí (configuración por defecto)

**Contenido**:
- Set activo
- Definición de sets
- Prompts personalizados

#### flashcard_sessions.json

**Propósito**: Sesiones guardadas

**Incluir en Git**: No (datos del usuario)

**Contenido**:
- Últimas 10 sesiones
- Títulos de secciones
- Rutas de imágenes

#### pending_flashcards.json

**Propósito**: Flashcards pendientes de importar

**Incluir en Git**: No (datos temporales)

**Contenido**:
- Lotes fallidos
- Flashcards completas
- Información de error

### Dependencias

#### Principales

```
google-generativeai==0.3.0  # API de Gemini
python-dotenv==1.0.0        # Variables de entorno
Pillow==10.0.0              # Procesamiento de imágenes
requests==2.31.0            # HTTP requests
```

#### Video Processing

```
openai-whisper==20231117    # Transcripción de audio
ffmpeg-python==0.2.0        # Procesamiento de video
```

#### Opcionales

```
pytesseract==0.3.10         # OCR fallback
tkinterdnd2==0.3.0          # Drag & drop
```

### Convenciones de Código

**Estilo**: PEP 8

**Docstrings**: Google Style

**Ejemplo**:
```python
def method_name(self, param1: str, param2: int) -> bool:
    """
    Descripción breve del método.
    
    Args:
        param1: Descripción del parámetro 1
        param2: Descripción del parámetro 2
        
    Returns:
        Descripción del valor de retorno
        
    Raises:
        ValueError: Cuando param2 es negativo
    """
    pass
```

**Type Hints**: Usar siempre que sea posible

**Logging**: Usar `self._log()` o `self.auto_log()`

---

## 📚 Referencias

### Documentación Oficial

- **Gemini API**: https://ai.google.dev/docs
- **AnkiConnect**: https://foosoft.net/projects/anki-connect/
- **Anki**: https://docs.ankiweb.net/
- **Whisper**: https://github.com/openai/whisper
- **FFmpeg**: https://ffmpeg.org/documentation.html

### Recursos Adicionales

- **Taxonomía de Bloom**: https://cft.vanderbilt.edu/guides-sub-pages/blooms-taxonomy/
- **Spaced Repetition**: https://en.wikipedia.org/wiki/Spaced_repetition
- **Anki Manual**: https://docs.ankiweb.net/

---

## 📝 Licencia

Este proyecto es de código abierto. Consulta el archivo LICENSE para más detalles.

---

## 👥 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📧 Contacto

Para preguntas, sugerencias o reportar bugs, abre un issue en GitHub.

---

**Última actualización**: Enero 2026
**Versión**: 1.0.0
