# Guía de Entrada Manual - Anki Sync

## Descripción

La nueva funcionalidad de **Entrada Manual** permite pegar flashcards directamente en una caja de texto. El sistema detecta automáticamente el tipo de cada flashcard y los distribuye entre los mazos.

## Características

✓ **Detección Automática**: Identifica automáticamente el tipo de flashcard
✓ **Distribución Inteligente**: Agrupa flashcards por tipo en diferentes mazos
✓ **Limpieza Automática**: Limpia y normaliza el texto pegado
✓ **Soporte Completo**: Soporta los 4 tipos de flashcards

## Tipos de Flashcards Soportados

### 1. Básico (Basic)
```
P: ¿Qué es WGAN?
R: Wasserstein GAN es una arquitectura...
```

### 2. Opción Múltiple (Multiple Choice)
```
P: ¿Cuál es la función de activación?
A) ReLU
B) Leaky ReLU
C) Tanh
D) Sigmoid
R: C) Tanh
```

### 3. Respuesta Anidada (Cloze)
```
P: La métrica {{c1::F1-Score::Métrica}} combina precisión
R: Métrica fundamental en machine learning
```

### 4. Vocabulario (Vocabulary)
```
P: Término: Data Augmentation
R: Data Augmentation /ˌdeɪtə ɔːɡmɛnˈteɪʃən/
```

## Cómo Usar

### Paso 1: Abrir Anki Sync
1. Ejecuta el programa
2. Haz clic en "Anki Sync" en el banner

### Paso 2: Pegar Flashcards
1. Copia tus flashcards del formato proporcionado
2. Haz clic en el área de texto "Manual Input"
3. Pega con **Ctrl+V** (o Cmd+V en macOS)

### Paso 3: Parsear Automáticamente
1. Haz clic en **"Parse & Auto-Detect"**
2. El sistema detectará automáticamente:
   - El tipo de cada flashcard
   - Distribuirá entre mazos según tipo
   - Configurará los nombres de mazos

### Paso 4: Revisar y Sincronizar
1. Verifica la vista previa de cada mazo
2. Haz clic en **"Sync to Anki"**
3. Los flashcards se sincronizarán automáticamente

## Ejemplo Completo

### Entrada (Pegar en el área de texto)
```
P: Concepto: ¿Qué es la Penalización de Gradiente?
R: Es un término de regularización agregado a la función de pérdida del Crítico que fuerza a la norma del gradiente a mantenerse cerca de 1.

P: En la fase de entrenamiento, ¿cuál es el mecanismo de Focal Loss?
A) Aumenta el peso de los ejemplos fáciles
B) Reduce el peso de los ejemplos bien clasificados
C) Penaliza la norma del gradiente
D) Genera ruido gaussiano
R: B) Reduce el peso de los ejemplos bien clasificados

P: La métrica {{c1::F1-Score::Métrica}} combina precisión y exhaustividad
R: Ideal para datos desbalanceados

P: Término: Data Augmentation
R: Data Augmentation /ˌdeɪtə ɔːɡmɛnˈteɪʃən/
```

### Resultado Automático
```
Flashcards Detectados: 4

Distribución:
├─ Deck 1: "Basic" (1 flashcard)
├─ Deck 2: "Multiple Choice" (1 flashcard)
├─ Deck 3: "Cloze" (1 flashcard)
└─ Deck 4: "Vocabulary" (1 flashcard)

Estado: ✓ 4 flashcards parsed and distributed
```

## Formatos Aceptados

### Separador de Flashcards
```
P: Pregunta
R: Respuesta

P: Otra pregunta
R: Otra respuesta
```

### Espacios en Blanco
El sistema tolera espacios en blanco excesivos:
```
P: Pregunta


R: Respuesta


P: Otra pregunta
R: Otra respuesta
```

### Caracteres Especiales
Se soportan caracteres especiales:
- Acentos: á, é, í, ó, ú
- Símbolos: {{c1::}}, /.../, A), B), etc.
- Saltos de línea dentro de respuestas

## Detección Automática

El sistema detecta el tipo basándose en:

| Tipo | Indicador |
|------|-----------|
| **Cloze** | Contiene `{{c1::` |
| **Multiple Choice** | Contiene `A)`, `B)`, `C)`, `D)` |
| **Vocabulary** | Contiene `/.../ ` (pronunciación) |
| **Basic** | Ninguno de los anteriores |

## Limitaciones

1. **Máximo 4 tipos diferentes**: Si hay más de 4 tipos, se mostrará un error
2. **Formato P: R:**: Debe seguir el formato `P: pregunta` y `R: respuesta`
3. **Separación clara**: Cada flashcard debe estar separado por una línea en blanco

## Solución de Problemas

### Problema: "No flashcards found in the text"
**Solución:**
- Verifica que uses el formato `P: ... R: ...`
- Asegúrate de que haya al menos un flashcard
- Revisa que no haya caracteres especiales que interfieran

### Problema: "More than 4 different flashcard types detected"
**Solución:**
- Limita a máximo 4 tipos diferentes
- Combina tipos similares en un mismo mazo
- Usa múltiples lotes de sincronización

### Problema: Los flashcards no se parsean correctamente
**Solución:**
- Verifica el formato exacto: `P: pregunta` y `R: respuesta`
- Asegúrate de que haya saltos de línea entre flashcards
- Revisa que no haya espacios extra antes de `P:` o `R:`

## Consejos Útiles

1. **Copiar desde documentos**: Copia directamente desde Word, Google Docs, etc.
2. **Múltiples lotes**: Si tienes muchos flashcards, divide en lotes de máximo 4 tipos
3. **Revisar vista previa**: Siempre revisa la vista previa antes de sincronizar
4. **Nombres de mazos**: Se generan automáticamente, pero puedes editarlos

## Flujo Recomendado

```
1. Preparar flashcards en formato P: R:
   ↓
2. Copiar al portapapeles
   ↓
3. Pegar en el área de texto (Ctrl+V)
   ↓
4. Haz clic en "Parse & Auto-Detect"
   ↓
5. Verifica la distribución automática
   ↓
6. Revisa la vista previa
   ↓
7. Haz clic en "Sync to Anki"
   ↓
8. ✓ Flashcards sincronizados
```

## Ejemplos Adicionales

### Ejemplo 1: Solo Básicos
```
P: ¿Qué es machine learning?
R: Es una rama de la IA que permite a las máquinas aprender de datos.

P: ¿Cuál es la diferencia entre supervised y unsupervised?
R: Supervised usa datos etiquetados, unsupervised no.
```

### Ejemplo 2: Mezcla de Tipos
```
P: ¿Qué es una red neuronal?
R: Es un modelo computacional inspirado en el cerebro.

P: ¿Cuál es la función de activación más común?
A) ReLU
B) Sigmoid
C) Tanh
D) Linear
R: A) ReLU

P: Una {{c1::red neuronal convolucional}} es ideal para procesamiento de imágenes.
R: CNN - Convolutional Neural Network

P: Término: Backpropagation
R: Backpropagation /ˌbækprəpəˈɡeɪʃən/
```

## Integración con Anki

Una vez sincronizados, los flashcards aparecerán en Anki con:
- Nombres de mazos automáticos
- Modelos correctos (Basic, Cloze)
- Campos formateados correctamente
- Etiquetas automáticas por tipo

## Contacto y Soporte

Para reportar problemas o sugerencias sobre la entrada manual, contacta al equipo de desarrollo.

---

**Última actualización**: Noviembre 2025
**Versión**: 1.0
