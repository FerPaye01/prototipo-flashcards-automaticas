# 📋 Pendientes del Proyecto — Flashcards

## 💾 Persistencia de la Sala de Espera (`pending_queue.json`)

**Contexto:** Actualmente `self.pending_flashcard_imports` es una lista en memoria que se pierde al cerrar la app.
Al recuperar una sesión, las flashcards se recargan desde los `.txt` guardados en disco, pero esto requiere
el paso manual de "Recuperar Sesión" y solo funciona para flashcards de video.

**Propuesta:** Persistir la sala de espera automáticamente en un archivo `pending_queue.json` en la raíz del proyecto.

**Comportamiento deseado:**
- Al terminar de generar flashcards (o al cerrar la app) → guardar automáticamente la cola en `pending_queue.json`
- Al abrir la app → detectar si existe `pending_queue.json` y preguntar si cargar las tarjetas pendientes
- Al presionar "✅ Ejecutar Sincronización" con éxito → borrar `pending_queue.json`
- Al presionar "🗑 Limpiar Todo" → ofrecer opción de borrar también los pendientes

**Ventaja principal:** Elimina el riesgo de doble importación a Anki y hace innecesario "Recuperar Sesión"
solo para obtener las flashcards generadas. Aplica a TODAS las pestañas (Video, Texto, Libros, Audio).

**Archivos a modificar:**
- `anki_import_interface.py`: añadir `_save_pending_queue()` y `_load_pending_queue()`, llamarlos en los momentos clave.
