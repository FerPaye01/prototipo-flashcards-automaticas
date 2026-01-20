# Implementación - Entrada Manual de Flashcards

## Resumen

Se ha agregado una nueva funcionalidad de **Entrada Manual** a la pestaña Anki Sync que permite:
- Pegar flashcards directamente en una caja de texto
- Detección automática del tipo de cada flashcard
- Distribución inteligente entre mazos
- Limpieza y normalización automática del texto

## Archivos Nuevos

### 1. `flashcard_parser.py` (200+ líneas)
**Módulo principal para parseo y detección automática**

Clases:
- `FlashcardParser`: Parser con métodos estáticos

Métodos principales:
- `detect_flashcard_type()`: Detecta automáticamente el tipo
- `parse_raw_text()`: Parsea texto crudo
- `clean_flashcard_text()`: Limpia el texto
- `format_for_anki()`: Formatea para Anki
- `parse_and_format()`: Parsea y formatea en un paso

Características:
- Detección automática de 4 tipos
- Limpieza de espacios en blanco
- Normalización de formato
- Conversión a formato Anki

### 2. `test_flashcard_parser.py` (100+ líneas)
**Script de prueba para el parser**

Pruebas:
- Limpieza de texto
- Parseo de flashcards
- Detección de tipos
- Formateo para Anki
- Validación de resultados

Resultado: ✓ 9/9 flashcards parseados correctamente

## Archivos Modificados

### `anki_sync_interface.py`
**Cambios:**
- Importación de `FlashcardParser`
- Nuevo método `_create_manual_input_section()`
- Nuevo método `_on_paste()`
- Nuevo método `_parse_manual_input()`
- Actualización de `_create_decks_section()`

**Líneas agregadas:** ~150

**Nuevas características:**
- Área de texto para entrada manual
- Botón "Parse & Auto-Detect"
- Distribución automática entre mazos
- Indicador de estado
- Manejo de errores

## Flujo de Funcionamiento

```
Usuario pega flashcards (Ctrl+V)
    ↓
Haz clic en "Parse & Auto-Detect"
    ↓
FlashcardParser.clean_flashcard_text()
    ↓
FlashcardParser.parse_raw_text()
    ↓
Para cada flashcard:
    - Detectar tipo automáticamente
    - Parsear según tipo
    - Formatear para Anki
    ↓
Distribuir entre mazos por tipo
    ↓
Configurar nombres de mazos automáticamente
    ↓
Actualizar vista previa
    ↓
Mostrar resumen
    ↓
Usuario hace clic en "Sync to Anki"
    ↓
✓ Flashcards sincronizados
```

## Detección Automática

El sistema detecta el tipo basándose en:

| Tipo | Indicador | Ejemplo |
|------|-----------|---------|
| **Cloze** | `{{c1::` | `{{c1::F1-Score::Métrica}}` |
| **Multiple Choice** | `A)`, `B)`, `C)`, `D)` | `A) Opción 1` |
| **Vocabulary** | `/.../ ` | `/ˌdeɪtə/` |
| **Basic** | Ninguno | Pregunta simple |

## Ejemplo de Uso

### Entrada (Pegar)
```
P: ¿Qué es WGAN?
R: Wasserstein GAN es una arquitectura...

P: ¿Cuál es la función de activación?
A) ReLU
B) Tanh
C) Sigmoid
D) Linear
R: B) Tanh

P: La métrica {{c1::F1-Score::Métrica}} combina precisión
R: Métrica fundamental

P: Término: Data Augmentation
R: Data Augmentation /ˌdeɪtə ɔːɡmɛnˈteɪʃən/
```

### Resultado Automático
```
✓ 4 flashcards parsed and distributed

Deck 1: "Basic" (1 flashcard)
Deck 2: "Multiple Choice" (1 flashcard)
Deck 3: "Cloze" (1 flashcard)
Deck 4: "Vocabulary" (1 flashcard)
```

## Características Principales

✓ **Detección Automática**
- Identifica el tipo de cada flashcard
- Agrupa por tipo automáticamente

✓ **Limpieza Inteligente**
- Normaliza espacios en blanco
- Ajusta formato de P: y R:
- Mantiene caracteres especiales

✓ **Distribución Inteligente**
- Agrupa flashcards por tipo
- Asigna a mazos automáticamente
- Genera nombres descriptivos

✓ **Validación Robusta**
- Verifica formato correcto
- Maneja errores gracefully
- Muestra mensajes descriptivos

✓ **Interfaz Intuitiva**
- Área de texto clara
- Botones de acción obvios
- Indicador de estado
- Vista previa actualizada

## Limitaciones

1. **Máximo 4 tipos**: Si hay más de 4 tipos diferentes, se muestra error
2. **Formato requerido**: Debe usar `P: pregunta` y `R: respuesta`
3. **Separación clara**: Flashcards deben estar separados por línea en blanco

## Pruebas Realizadas

### Test 1: Limpieza de Texto
- ✓ Normaliza espacios en blanco
- ✓ Ajusta formato P: y R:
- ✓ Mantiene caracteres especiales

### Test 2: Parseo de Flashcards
- ✓ Parsea 2 flashcards básicos
- ✓ Parsea 2 flashcards de opción múltiple
- ✓ Parsea 2 flashcards Cloze
- ✓ Parsea 3 flashcards de vocabulario

### Test 3: Detección de Tipos
- ✓ Detecta correctamente Cloze
- ✓ Detecta correctamente Multiple Choice
- ✓ Detecta correctamente Vocabulary
- ✓ Detecta correctamente Basic

### Test 4: Formateo para Anki
- ✓ Formatea Basic correctamente
- ✓ Formatea Multiple Choice con saltos de línea
- ✓ Formatea Cloze con campos Text y Extra
- ✓ Formatea Vocabulary con pronunciación

### Resultado: 9/9 Flashcards Parseados Correctamente ✓

## Integración con Anki Sync

La entrada manual se integra perfectamente con:
- Detección de estado de Anki
- Inicio automático de Anki
- Sincronización secuencial
- Vista previa de flashcards
- Barra de progreso
- Manejo de errores

## Flujo Completo

```
1. Usuario abre Anki Sync
   ↓
2. Pega flashcards en el área de texto
   ↓
3. Haz clic en "Parse & Auto-Detect"
   ↓
4. Sistema detecta tipos y distribuye
   ↓
5. Usuario revisa vista previa
   ↓
6. Usuario haz clic en "Sync to Anki"
   ↓
7. Sistema sincroniza secuencialmente
   ↓
8. ✓ Flashcards en Anki
```

## Ventajas

1. **Rápido**: No necesita cargar archivos
2. **Automático**: Detecta tipos automáticamente
3. **Inteligente**: Distribuye entre mazos
4. **Flexible**: Soporta múltiples formatos
5. **Robusto**: Maneja errores gracefully

## Casos de Uso

1. **Entrada rápida**: Pegar y sincronizar en segundos
2. **Múltiples tipos**: Mezclar diferentes tipos de flashcards
3. **Limpieza automática**: No necesita formatear manualmente
4. **Distribución automática**: Agrupa por tipo automáticamente

## Documentación

- `MANUAL_INPUT_GUIDE.md`: Guía de uso para usuarios
- `MANUAL_INPUT_IMPLEMENTATION.md`: Este documento
- `test_flashcard_parser.py`: Script de prueba

## Próximas Mejoras

1. Soporte para más formatos de entrada
2. Edición manual de flashcards antes de sincronizar
3. Historial de flashcards pegados
4. Guardado de plantillas personalizadas

## Resumen de Cambios

| Componente | Cambios | Estado |
|-----------|---------|--------|
| flashcard_parser.py | Nuevo módulo | ✓ Creado |
| anki_sync_interface.py | +150 líneas | ✓ Modificado |
| test_flashcard_parser.py | Nuevo script | ✓ Creado |
| MANUAL_INPUT_GUIDE.md | Documentación | ✓ Creado |
| **Total** | **~350 líneas** | **✓ Completado** |

---

**Fecha**: Noviembre 2025
**Versión**: 1.0
**Estado**: Completado y Testeado
