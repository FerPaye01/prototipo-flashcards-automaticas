# Módulo de Adaptación y Traducción Académica de Mazos Anki

Este documento proporciona una descripción técnica detallada del nuevo módulo de traducción y adaptación inteligente integrado en el prototipo de flashcards.

## 📌 Propósito del Módulo
El objetivo principal es permitir a los usuarios reutilizar y traducir sus mazos de flashcards existentes en español a una versión equivalente en inglés (u otros idiomas de destino), preservando de manera exacta la estructura jerárquica original (mazos y submazos) y garantizando una traducción técnica, pedagógica y fluida apropiada para el ámbito académico y profesional (no literal).

---

## 🏗️ Arquitectura de la Solución

El módulo se compone de tres partes fundamentales:
1. **Interfaz Gráfica (GUI - Tkinter)**: Una vista dedicada (`anki_translator_frame`) con un Treeview dinámico y navegación de mazos, controles de parámetros y un área de estadísticas y registros.
2. **Control de Duplicados e Incremental**: Integrado en el gestor de notas usando identificadores únicos (`src_note_<id>`) y firmas de contenido (MD5 hashes `src_hash_<hash>`) almacenados como etiquetas en Anki.
3. **Adaptador LLM (Gemini API)**: Generación con preservación de formato Markdown/HTML y estructura de Cloze Deletions (`{{c1::...}}`), adaptando terminología técnica al inglés académico de alto nivel.

```mermaid
graph TD
    A[Usuario selecciona Mazo Raíz] --> B[Treeview dinámico consulta AnkiConnect]
    B --> C[Recorrido bottom-up de Decks y Submazos]
    C --> D[Mapeo de notas individuales]
    D --> E{Verificar tag src_note_ID en Anki}
    E -- Sí existe --> F{¿Ha cambiado el hash del contenido?}
    F -- No ha cambiado --> G[Omitir nota / Skip]
    F -- Sí ha cambiado / Completo --> H[Traducir campos con Gemini LLM]
    E -- No existe --> H
    H --> I[Generar JSON adaptado conservando Clozes y HTML]
    I --> J{¿Existe mazo equivalente en destino?}
    J -- No --> K[Crear submazo jerárquico 'Nombre Mazo (EN)']
    J -- Sí --> L[Guardar/Actualizar nota en Anki]
    K --> L
    L --> M[Actualizar tags src_note_ID y src_hash_HASH]
```

---

## 🛠️ Detalles de la Implementación

### 1. Preservación Jerárquica del Mazo
Cuando el usuario selecciona un mazo raíz (ej. `Conocimiento`), se procesan tanto el mazo raíz como todos sus descendientes de forma recursiva:
* **Algoritmo de Mapeo**: Los mazos son ordenados por profundidad (`::` count) de manera descendente. Esto nos permite aislar de manera precisa las notas que pertenecen exactamente a cada deck sin que la búsqueda de Anki mezcle elementos heredados.
* **Cálculo de Rutas**: El sufijo del idioma (ej. ` (EN)`) se aplica únicamente en el nivel secundario inmediato inferior del mazo raíz seleccionado (o al mismo nivel si es un mazo simple), garantizando que subcarpetas como `Introducción` o `Arquitectura` mantengan su nombre original bajo la nueva rama.

### 2. Modo Incremental y Control de Duplicados
Para asegurar eficiencia y evitar recrear tarjetas existentes en ejecuciones subsecuentes, el sistema realiza lo siguiente:
* **Firma de Contenido (Hash)**: Se genera un hash MD5 a partir de un JSON ordenado que representa la combinación de los valores originales de los campos de la nota.
* **Vinculación**: La nota traducida se etiqueta en Anki con:
  * `src_note_<original_note_id>`: Permite identificar qué tarjeta dio origen a la traducción.
  * `src_hash_<original_content_hash>`: Permite comprobar si el contenido original en español ha sufrido alguna modificación posterior.
* **Acciones de Duplicados**:
  * **Omitir**: Si ya existe un mazo de traducción y la tarjeta no ha cambiado, no se hace nada.
  * **Actualizar**: Si la tarjeta original cambió, se actualizan los campos correspondientes a través de `updateNoteFields` en AnkiConnect y se refresca el tag de firma de contenido.

### 3. Preservación de Estructuras Especiales por Gemini
El prompt utilizado para Gemini instruye estrictamente el formato y comportamiento del modelo para:
* **Preservación de Clozes**: Detectar formatos `{{c1::texto}}` o `{{c2::texto::pista}}` y adaptar el contenido en su interior sin romper la sintaxis del motor de repetición espaciada de Anki.
* **Formato HTML/Markdown**: Conservar las etiquetas estilográficas (negritas, cursivas, saltos de línea `<br>`).
* **Terminología Técnica**: Mapeo estandarizado de conceptos informáticos o académicos a su versión profesional (ej. *consistencia eventual* -> *eventual consistency*).

---

## 🖥️ Layout del Panel de Usuario

El nuevo panel integrado en la interfaz posee la siguiente distribución visual:

* **Panel Izquierdo**:
  * **Visualizador de Mazos Anki**: Un árbol interactivo (`ttk.Treeview`) que lee en tiempo real todos tus mazos.
  * **Selector de Idioma**: Dropdown con soporte para *Inglés*, *Portugués*, *Francés*, *Alemán* e *Italiano*.
  * **Modo de Ejecución**: Elección entre modo *Incremental* (rápido, inteligente) o *Completo* (re-traduce todo).
  * **Control de Duplicados**: Permite elegir si actualizar o no las tarjetas existentes que han cambiado.
  * **Acciones**: Botones para `Comenzar Adaptación` y `Detener` la ejecución de forma segura.

* **Panel Derecho**:
  * **Estadísticas de Ejecución**: Contadores dinámicos que muestran:
    * *Tarjetas analizadas* (Total evaluadas)
    * *Tarjetas generadas/actualizadas* (Operaciones de inserción o actualización)
    * *Tarjetas omitidas* (Duplicados vigentes saltados)
    * *Errores encontrados* (Problemas de conexión o procesamiento IA)
  * **Logs en tiempo real**: Registro de actividad paso a paso de cada mazo y nota procesada.

---

## 📈 Instrucciones de Uso

1. Inicie la aplicación principal (`python anki_import_interface.py`).
2. Haga clic en el botón superior **🔄 Adaptar Anki**.
3. Asegúrese de tener Anki abierto en su ordenador con el plugin **AnkiConnect** activado.
4. Presione **Recargar Mazos** si su mazo no aparece de inmediato.
5. Seleccione el mazo raíz en el árbol de carpetas.
6. Configure los parámetros de idioma y modo de ejecución según sus preferencias.
7. Presione **🚀 Comenzar Adaptación**. El proceso se ejecutará en segundo plano de manera segura sin congelar la ventana del programa.
