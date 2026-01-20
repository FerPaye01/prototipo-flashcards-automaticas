# Flashcards Automáticas con Gemini AI

Sistema automatizado para generar flashcards desde imágenes usando Gemini Vision API e importarlas directamente a Anki.

## 🚀 Características

- **OCR con Gemini Vision**: Extrae texto de capturas de pantalla y fotos de apuntes
- **Generación inteligente**: Crea 4 tipos de flashcards usando Gemini AI
- **Dos modos de configuración**:
  - **Por Defecto**: Basic, Multiple Choice, Cloze, Vocabulary
  - **Niveles Bloom**: 4 niveles cognitivos (Recordar, Entender, Aplicar, Analizar)
- **Importación directa a Anki**: Sincronización automática vía AnkiConnect
- **Gestión de sesiones**: Guarda y recupera sesiones de trabajo
- **Pegar desde portapapeles**: Añade capturas directamente con Ctrl+V

## 📋 Requisitos

### Software necesario
- Python 3.8+
- Anki (con AnkiConnect instalado)

### Dependencias Python
```bash
pip install -r requirements.txt
```

Principales librerías:
- `google-generativeai` - API de Gemini
- `Pillow` - Procesamiento de imágenes
- `requests` - Comunicación con AnkiConnect
- `python-dotenv` - Variables de entorno

## ⚙️ Configuración

### 1. Instalar AnkiConnect

1. Abre Anki
2. Ve a `Tools` → `Add-ons` → `Get Add-ons`
3. Código: `2055492159`
4. Reinicia Anki

### 2. Configurar API Keys de Gemini

Crea un archivo `.env` en la raíz del proyecto:

```env
# API Key para OCR (Gemini Vision)
GEMINI_API_KEY_OCR=tu_api_key_aqui

# API Keys para generación de flashcards (4 tipos en paralelo)
GEMINI_API_KEY_1=tu_api_key_aqui
GEMINI_API_KEY_2=tu_api_key_aqui
GEMINI_API_KEY_3=tu_api_key_aqui
GEMINI_API_KEY_4=tu_api_key_aqui

# Modelo a usar (opcional)
GEMINI_MODEL=gemini-3-flash-preview
```

**Nota**: Puedes usar la misma API key para todas si no necesitas paralelización.

Obtén tus API keys en: https://aistudio.google.com/app/apikey

## 🎯 Uso

### Iniciar la aplicación

```bash
python anki_import_interface.py
```

### Flujo de trabajo

1. **Modo Automático** (recomendado):
   - Haz clic en "🤖 Modo Automático"
   - Añade secciones con el botón "+ Añadir Sección"
   - Para cada sección:
     - Haz una captura (Win+Shift+S)
     - Haz clic en "📋 Pegar" o arrastra la imagen
   - Configura el set de prompts (⚙️ Configuración)
   - Haz clic en "🚀 Procesar Secciones"

2. **Modo Normal**:
   - Pega texto directamente en las 4 cajitas
   - Haz clic en "Convert & Import to Anki"

### Configuración de Sets

Accede a la configuración con el botón "⚙️ Configuración":

**Set "Por Defecto"**:
- Basic: Preguntas y respuestas simples
- Multiple Choice: Opción múltiple con distractores
- Cloze: Respuestas anidadas con huecos
- Vocabulary: Términos en inglés con pronunciación

**Set "Niveles Bloom"**:
- Nivel 1 - Cloze: Recordar conceptos clave
- Nivel 2 - Relaciones: Entender conexiones
- Nivel 3 - Aplicación: Resolver problemas
- Nivel 4 - Análisis: Preguntas complejas

Puedes crear sets personalizados y editar los prompts.

## 📁 Estructura del Proyecto

```
.
├── anki_import_interface.py      # Aplicación principal (GUI)
├── gemini_flashcard_generator.py # Generador con Gemini API
├── flashcards_converter.py       # Parser de flashcards
├── anki_sync_manager.py          # Sincronización con Anki
├── config_sets_manager.py        # Gestión de configuraciones
├── requirements.txt              # Dependencias
├── .env.example                  # Plantilla de configuración
└── README.md                     # Este archivo
```

## 🔧 Solución de Problemas

### Anki no se conecta
- Verifica que Anki esté abierto
- Verifica que AnkiConnect esté instalado (código: 2055492159)
- Reinicia Anki

### Error de API Key
- Verifica que el archivo `.env` exista
- Verifica que las API keys sean válidas
- Prueba con "🔌 Chequear API" en el modo automático

### OCR no funciona
- Verifica que las imágenes sean legibles
- Prueba con imágenes más claras
- El sistema usa Tesseract como fallback si Gemini falla

### Flashcards no se parsean
- Verifica que el formato de salida de Gemini sea correcto
- Revisa los logs en la interfaz
- Prueba editando los prompts en la configuración

## 📝 Formato de Flashcards

### Basic
```
P: ¿Pregunta?
R: Respuesta

P: ¿Otra pregunta?
R: Otra respuesta
```

### Multiple Choice
```
P: ¿Pregunta?
a) Opción 1
b) Opción 2
c) Opción 3
d) Opción 4
R: c - Explicación
```

### Cloze
```
P: El concepto {{c1::clave::pista}} es importante
```

### Vocabulary
```
P: Término en inglés
R: /pronunciación/ Contexto en español
```

## 🤝 Contribuir

Este es un proyecto educativo. Si encuentras bugs o tienes sugerencias, siéntete libre de crear un issue.

## 📄 Licencia

Proyecto educativo - Uso libre para fines académicos

## 🙏 Agradecimientos

- Google Gemini AI por la API
- Anki y AnkiConnect por la integración
- Comunidad de Python por las librerías

---

**Desarrollado como proyecto de investigación - 2026**
