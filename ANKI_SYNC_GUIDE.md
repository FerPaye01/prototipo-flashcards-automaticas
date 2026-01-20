# Anki Sync - Guía de Uso

## Descripción General

La nueva pestaña **Anki Sync** permite sincronizar hasta 4 mazos de flashcards con Anki de forma secuencial. Soporta 4 tipos diferentes de flashcards, cada uno con su propio formato.

## Requisitos Previos

1. **Anki instalado**: Descarga desde [https://apps.ankiweb.net/](https://apps.ankiweb.net/)
2. **AnkiConnect**: Instala el complemento AnkiConnect en Anki
   - En Anki: Tools → Add-ons → Get Add-ons
   - Código: `2055492159`
3. **Python requests library**: Se instala automáticamente con el proyecto

## Tipos de Flashcards Soportados

### 1. Básico (Basic)
Formato simple de pregunta-respuesta.

**Formato de entrada:**
```
P: ¿Qué es la Penalización de Gradiente?
R: Es un término de regularización que fuerza la norma del gradiente a mantenerse cerca de 1.

P: ¿Cuál es la relación entre Wasserstein y estabilidad?
R: Proporciona gradientes suaves incluso cuando las distribuciones no se superponen.
```

**En Anki:** Tarjeta con Anverso (Front) y Reverso (Back)

---

### 2. Opción Múltiple (Multiple Choice)
Preguntas con opciones A, B, C, D con saltos de línea adecuados.

**Formato de entrada:**
```
P: ¿Cuál es el mecanismo de Focal Loss?
A) Aumenta el peso de los ejemplos fáciles
B) Reduce el peso de los ejemplos bien clasificados
C) Penaliza la norma del gradiente
D) Genera ruido gaussiano
R: B) Reduce el peso de los ejemplos bien clasificados

P: ¿Qué función de activación usa el Generador?
A) ReLU
B) Leaky ReLU
C) Tanh
D) Sigmoid
R: C) Tanh
```

**En Anki:** 
- Anverso: Pregunta + Opciones (con saltos de línea)
- Reverso: Respuesta correcta

---

### 3. Respuesta Anidada / Cloze Deletion
Formato con espacios en blanco para rellenar ({{c1::respuesta::extra}}).

**Formato de entrada:**
```
P: La métrica {{c1::F1-Score::Métrica}} combina la precisión y la exhaustividad
R: Ideal para datos desbalanceados

P: El generador en una WGAN busca minimizar la {{c1::Distancia Wasserstein}} en lugar de la divergencia JS
R: Propiedad fundamental de WGAN
```

**En Anki:**
- Modelo: Cloze
- Texto: Contenido con {{c1::respuesta::extra}}
- Extra: Información adicional

---

### 4. Vocabulario en Inglés (English Vocabulary)
Términos con pronunciación y contexto.

**Formato de entrada:**
```
P: Data Augmentation
R: /ˌdeɪtə ɔːɡmɛnˈteɪʃən/ Técnica para incrementar la diversidad del dataset

P: Vanishing Gradient
R: /ˌvænɪʃɪŋ ˈɡreɪdiənt/ Problema común en el entrenamiento de redes profundas

P: Loss Function
R: /lɔːs ˈfʌŋkʃən/ Método para evaluar qué tan bien el algoritmo modela los datos
```

**En Anki:**
- Anverso: Término + Pronunciación
- Reverso: Contexto/Definición

---

## Pasos para Sincronizar

### 1. Acceder a la Pestaña Anki Sync
- Haz clic en el botón **"Anki Sync"** en el banner de entrada
- Se abrirá la interfaz de sincronización

### 2. Verificar Estado de Anki
- La interfaz mostrará el estado de Anki (verde = ejecutándose, rojo = no ejecutándose)
- Si Anki no está ejecutándose, haz clic en **"Start Anki"** para iniciarlo automáticamente
- Anki se abrirá automáticamente si no está en ejecución

### 3. Configurar Mazos (hasta 4)
Para cada mazo que desees sincronizar:

1. **Nombre del Mazo**: Ingresa el nombre del mazo en Anki
   - Ejemplo: "WGAN-Conceptos", "WGAN-Preguntas", etc.
   - Si el mazo no existe, se creará automáticamente

2. **Tipo de Flashcard**: Selecciona el tipo de flashcard
   - `basic`: Pregunta-Respuesta simple
   - `multiple_choice`: Opción múltiple
   - `cloze`: Respuesta anidada
   - `vocabulary`: Vocabulario en inglés

3. **Cargar Flashcards**: Haz clic en **"Load Flashcards"**
   - Selecciona un archivo JSON o TXT con los flashcards
   - El archivo se parseará según el tipo seleccionado
   - Se mostrará el número de tarjetas cargadas

### 4. Vista Previa
- Usa el selector **"Preview Deck"** para ver una vista previa de los flashcards
- Se mostrarán los primeros 3 flashcards de cada mazo

### 5. Sincronizar
- Haz clic en **"Sync to Anki"**
- La barra de progreso mostrará el avance
- Se sincronizarán los mazos de forma secuencial
- Se mostrará un resumen con el número de tarjetas sincronizadas

### 6. Limpiar (Opcional)
- Haz clic en **"Clear All"** para limpiar todos los datos y empezar de nuevo

---

## Formatos de Archivo Soportados

### JSON
```json
[
  {
    "front": "¿Qué es la Penalización de Gradiente?",
    "back": "Es un término de regularización...",
    "tags": ["wgan", "conceptos"]
  },
  {
    "front": "¿Cuál es la relación causal?",
    "back": "La Distancia Wasserstein proporciona...",
    "tags": ["wgan", "análisis"]
  }
]
```

### Texto Plano (TSV)
```
P: Pregunta 1	R: Respuesta 1
P: Pregunta 2	R: Respuesta 2
```

---

## Ejemplos de Uso

### Ejemplo 1: Sincronizar 2 Mazos
1. **Mazo 1**: "WGAN-Conceptos" (tipo: basic)
   - Cargar archivo: `conceptos_wgan.json`
   - 15 flashcards

2. **Mazo 2**: "WGAN-Preguntas" (tipo: multiple_choice)
   - Cargar archivo: `preguntas_wgan.txt`
   - 8 flashcards

3. Hacer clic en **"Sync to Anki"**
4. Resultado: 23 flashcards sincronizadas en 2 mazos

### Ejemplo 2: Sincronizar 4 Mazos Diferentes
1. **Mazo 1**: "Conceptos" (basic) - 20 cards
2. **Mazo 2**: "Preguntas" (multiple_choice) - 10 cards
3. **Mazo 3**: "Cloze" (cloze) - 15 cards
4. **Mazo 4**: "Vocabulary" (vocabulary) - 25 cards

Total: 70 flashcards en 4 mazos diferentes

---

## Solución de Problemas

### Anki no se inicia automáticamente
- Verifica que Anki esté instalado correctamente
- Intenta iniciar Anki manualmente
- Asegúrate de que AnkiConnect esté instalado

### AnkiConnect no responde
- Reinicia Anki
- Verifica que AnkiConnect esté habilitado en Anki
- Comprueba que el puerto 8765 no esté bloqueado

### Los flashcards no se sincronizan
- Verifica que el nombre del mazo sea válido
- Asegúrate de que el tipo de flashcard sea correcto
- Revisa el formato del archivo de entrada

### Error: "Anki is not running"
- Haz clic en **"Start Anki"** para iniciar automáticamente
- O inicia Anki manualmente desde tu sistema

---

## Notas Importantes

1. **Sincronización Secuencial**: Los mazos se sincronizan uno por uno para evitar conflictos
2. **Creación Automática de Mazos**: Si un mazo no existe, se creará automáticamente
3. **Duplicados**: Anki evita automáticamente duplicados basándose en el contenido
4. **Modelos de Anki**: Asegúrate de que los modelos (Basic, Cloze) existan en tu Anki
5. **Etiquetas**: Los flashcards se etiquetan automáticamente según su tipo

---

## Contacto y Soporte

Para reportar problemas o sugerencias, contacta al equipo de desarrollo.
