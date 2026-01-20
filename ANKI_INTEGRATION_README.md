# Integración Anki - Documentación Técnica

## Descripción General

Se ha agregado una nueva pestaña **Anki Sync** al sistema de flashcards automáticas que permite sincronizar hasta 4 mazos de flashcards con Anki de forma secuencial. El sistema soporta 4 tipos diferentes de flashcards y detecta automáticamente si Anki está ejecutándose.

## Archivos Nuevos

### 1. `anki_sync_manager.py`
Módulo principal para gestionar la sincronización con Anki.

**Clases principales:**
- `AnkiSyncManager`: Gestor de sincronización con Anki

**Funcionalidades:**
- Detección automática de Anki ejecutándose
- Inicio automático de Anki si no está ejecutándose
- Creación de mazos en Anki
- Sincronización de flashcards
- Conversión de formatos de flashcards
- Parseo de flashcards desde texto

**Tipos de flashcards soportados:**
- `basic`: Pregunta-Respuesta simple
- `multiple_choice`: Opción múltiple con saltos de línea
- `cloze`: Respuesta anidada (Cloze Deletion)
- `vocabulary`: Vocabulario en inglés con pronunciación

### 2. `anki_sync_interface.py`
Interfaz gráfica para la sincronización con Anki.

**Clases principales:**
- `AnkiSyncInterface`: Widget de interfaz para sincronización

**Características:**
- Indicador de estado de Anki (verde/rojo)
- Botón para iniciar Anki automáticamente
- Configuración de hasta 4 mazos
- Selector de tipo de flashcard por mazo
- Carga de flashcards desde archivos
- Vista previa de flashcards
- Barra de progreso de sincronización
- Manejo de errores y notificaciones

### 3. Archivos Modificados

#### `input_banner.py`
- Agregado nuevo modo: `MODE_ANKI_SYNC`
- Botón "Anki Sync" en el banner
- Sub-opciones para Anki Sync

#### `input_method_controller.py`
- Agregado nuevo modo: `InputMode.ANKI_SYNC`
- Actualización de `string_to_input_mode()` para soportar "anki_sync"
- Actualización de `_update_control_states()` para Anki Sync

#### `programa_proyecto_flashcards_automaticas.py`
- Importación de `AnkiSyncInterface`
- Método `_create_anki_sync_area()` para crear la pestaña
- Callback `_on_anki_sync_complete()` para manejar completación
- Actualización de `_on_start_process()` para manejar Anki Sync
- Actualización de `_update_right_panel_for_mode()` para Anki Sync

## Arquitectura

### Flujo de Sincronización

```
Usuario selecciona "Anki Sync"
    ↓
AnkiSyncInterface se muestra
    ↓
Usuario configura mazos (nombre, tipo, flashcards)
    ↓
Usuario hace clic en "Sync to Anki"
    ↓
AnkiSyncManager verifica si Anki está ejecutándose
    ↓
Si no está ejecutándose, inicia Anki automáticamente
    ↓
Para cada mazo (secuencial):
    - Crea el mazo en Anki si no existe
    - Convierte flashcards al formato de Anki
    - Sincroniza los flashcards
    ↓
Muestra resumen de sincronización
```

### Detección y Inicio de Anki

```
_check_anki_status()
    ↓
Intenta conectar a AnkiConnect (localhost:8765)
    ↓
Si falla:
    - Intenta iniciar Anki automáticamente
    - Espera hasta 30 segundos a que Anki inicie
    - Reintenta conexión
    ↓
Retorna estado (ejecutándose o no)
```

## Formatos de Flashcards

### 1. Básico (Basic)
```
Modelo Anki: "Basic"
Campos: Front, Back

Formato de entrada:
P: Pregunta
R: Respuesta
```

### 2. Opción Múltiple (Multiple Choice)
```
Modelo Anki: "Basic"
Campos: Front (pregunta + opciones), Back (respuesta)

Formato de entrada:
P: Pregunta
A) Opción 1
B) Opción 2
C) Opción 3
D) Opción 4
R: Respuesta correcta
```

### 3. Respuesta Anidada (Cloze)
```
Modelo Anki: "Cloze"
Campos: Text (con {{c1::respuesta::extra}}), Extra

Formato de entrada:
P: Texto con {{c1::respuesta::extra}}
R: Información extra
```

### 4. Vocabulario (Vocabulary)
```
Modelo Anki: "Basic"
Campos: Front (término + pronunciación), Back (contexto)

Formato de entrada:
P: Término
R: /pronunciación/ Contexto
```

## Requisitos

### Sistema
- Python 3.7+
- Anki 2.1.50+ (con AnkiConnect)

### Dependencias Python
- `requests`: Para comunicación con AnkiConnect
- `tkinter`: Para interfaz gráfica (incluido en Python)

### Instalación de AnkiConnect
1. Abre Anki
2. Ve a Tools → Add-ons → Get Add-ons
3. Ingresa el código: `2055492159`
4. Reinicia Anki

## Uso Programático

### Ejemplo 1: Sincronizar flashcards básicos
```python
from anki_sync_manager import AnkiSyncManager

manager = AnkiSyncManager()

# Asegurar que Anki está ejecutándose
success, msg = manager.ensure_anki_running()
if not success:
    print(f"Error: {msg}")
    exit()

# Preparar flashcards
flashcards = [
    {
        "front": "¿Qué es WGAN?",
        "back": "Wasserstein GAN - una arquitectura de red neuronal...",
        "tags": ["wgan", "conceptos"]
    }
]

# Sincronizar
success, msg, count = manager.sync_flashcards_to_anki(
    deck_name="Mi Mazo",
    flashcards_data=flashcards,
    card_type="basic"
)

print(f"Sincronización: {msg} ({count} tarjetas)")
```

### Ejemplo 2: Sincronizar múltiples tipos
```python
from anki_sync_manager import AnkiSyncManager

manager = AnkiSyncManager()
manager.ensure_anki_running()

# Flashcards básicos
basic_cards = [...]
manager.sync_flashcards_to_anki("Conceptos", basic_cards, "basic")

# Flashcards de opción múltiple
mc_cards = [...]
manager.sync_flashcards_to_anki("Preguntas", mc_cards, "multiple_choice")

# Flashcards Cloze
cloze_cards = [...]
manager.sync_flashcards_to_anki("Cloze", cloze_cards, "cloze")

# Vocabulario
vocab_cards = [...]
manager.sync_flashcards_to_anki("Vocabulary", vocab_cards, "vocabulary")
```

## Manejo de Errores

### Errores Comunes

1. **"Anki is not running"**
   - Solución: Haz clic en "Start Anki" o inicia Anki manualmente

2. **"AnkiConnect not responding"**
   - Solución: Verifica que AnkiConnect esté instalado en Anki
   - Reinicia Anki

3. **"Failed to create deck"**
   - Solución: Verifica que el nombre del mazo sea válido
   - Intenta con un nombre diferente

4. **"Failed to add notes"**
   - Solución: Verifica que el modelo de Anki exista
   - Comprueba el formato de los flashcards

## Configuración

### Parámetros de AnkiSyncManager

```python
ANKI_CONNECT_URL = "http://localhost:8765"  # URL de AnkiConnect
ANKI_CONNECT_VERSION = 6  # Versión de API
```

### Timeouts

- Conexión a AnkiConnect: 2 segundos
- Operaciones de Anki: 5-10 segundos
- Inicio de Anki: 30 segundos

## Limitaciones

1. **Máximo 4 mazos**: La interfaz soporta hasta 4 mazos simultáneamente
2. **Sincronización secuencial**: Los mazos se sincronizan uno por uno
3. **Modelos fijos**: Solo soporta modelos "Basic" y "Cloze"
4. **Plataformas soportadas**: Windows, macOS, Linux

## Futuras Mejoras

1. Soporte para más tipos de modelos de Anki
2. Sincronización paralela de múltiples mazos
3. Actualización de flashcards existentes
4. Importación de mazos desde Anki
5. Configuración personalizada de modelos

## Testing

Para probar la integración:

1. Instala Anki y AnkiConnect
2. Ejecuta el programa principal
3. Selecciona la pestaña "Anki Sync"
4. Carga el archivo `ejemplo_flashcards_anki.json`
5. Configura los 4 mazos
6. Haz clic en "Sync to Anki"

## Contacto

Para reportar problemas o sugerencias, contacta al equipo de desarrollo.
