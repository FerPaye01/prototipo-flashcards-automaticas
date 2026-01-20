# Inicio Rápido - Anki Sync

## 1. Instalación de Requisitos

### Anki
1. Descarga Anki desde: https://apps.ankiweb.net/
2. Instala en tu sistema

### AnkiConnect (Complemento de Anki)
1. Abre Anki
2. Ve a **Tools** → **Add-ons** → **Get Add-ons**
3. Ingresa el código: `2055492159`
4. Haz clic en **OK**
5. Reinicia Anki

### Python (si no está instalado)
- Descarga desde: https://www.python.org/
- Asegúrate de marcar "Add Python to PATH"

## 2. Primeros Pasos

### Paso 1: Ejecutar el Programa
```bash
python programa_proyecto_flashcards_automaticas.py
```

### Paso 2: Seleccionar Anki Sync
- En el banner superior, haz clic en el botón **"Anki Sync"**
- Se abrirá la interfaz de sincronización

### Paso 3: Verificar Estado de Anki
- Verifica que el indicador de estado sea **verde** (Anki ejecutándose)
- Si es **rojo**, haz clic en **"Start Anki"** para iniciarlo automáticamente

### Paso 4: Configurar un Mazo
1. En **Deck 1**, ingresa un nombre: `Mi Primer Mazo`
2. Selecciona el tipo: `basic`
3. Haz clic en **"Load Flashcards"**
4. Selecciona el archivo: `ejemplo_flashcards_anki.json`

### Paso 5: Sincronizar
1. Haz clic en **"Sync to Anki"**
2. Espera a que se complete la sincronización
3. Verás un mensaje de éxito con el número de tarjetas sincronizadas

### Paso 6: Verificar en Anki
1. Abre Anki
2. Verás el nuevo mazo "Mi Primer Mazo"
3. Haz clic en el mazo para ver las tarjetas

## 3. Ejemplos de Uso

### Ejemplo 1: Sincronizar Flashcards Básicos
```
Nombre del Mazo: "Conceptos WGAN"
Tipo: basic
Archivo: ejemplo_flashcards_anki.json
```

### Ejemplo 2: Sincronizar Opción Múltiple
```
Nombre del Mazo: "Preguntas WGAN"
Tipo: multiple_choice
Archivo: ejemplo_flashcards_anki.json
```

### Ejemplo 3: Sincronizar Cloze
```
Nombre del Mazo: "Cloze WGAN"
Tipo: cloze
Archivo: ejemplo_flashcards_anki.json
```

### Ejemplo 4: Sincronizar Vocabulario
```
Nombre del Mazo: "Vocabulary"
Tipo: vocabulary
Archivo: ejemplo_flashcards_anki.json
```

## 4. Crear Tus Propios Flashcards

### Formato JSON
Crea un archivo `mis_flashcards.json`:

```json
[
  {
    "front": "¿Qué es X?",
    "back": "X es...",
    "tags": ["tema1", "basico"]
  },
  {
    "front": "¿Cuál es Y?",
    "back": "Y es...",
    "tags": ["tema1", "basico"]
  }
]
```

### Formato Texto
Crea un archivo `mis_flashcards.txt`:

```
P: ¿Qué es X?
R: X es...

P: ¿Cuál es Y?
R: Y es...
```

## 5. Solución de Problemas

### Problema: "Anki is not running"
**Solución:**
- Haz clic en **"Start Anki"**
- O inicia Anki manualmente

### Problema: "AnkiConnect not responding"
**Solución:**
- Verifica que AnkiConnect esté instalado
- Reinicia Anki
- Comprueba que el puerto 8765 no esté bloqueado

### Problema: Los flashcards no se sincronizan
**Solución:**
- Verifica que el archivo tenga el formato correcto
- Asegúrate de que el tipo de flashcard sea correcto
- Revisa los logs en la sección "Logs / Messages"

### Problema: "Failed to create deck"
**Solución:**
- Usa un nombre de mazo diferente
- Evita caracteres especiales en el nombre

## 6. Consejos Útiles

1. **Nombres de Mazos**: Usa nombres descriptivos
   - ✅ "WGAN-Conceptos", "ML-Preguntas"
   - ❌ "Mazo1", "Test"

2. **Tipos de Flashcards**: Elige el tipo correcto
   - `basic`: Para preguntas simples
   - `multiple_choice`: Para opciones A, B, C, D
   - `cloze`: Para rellenar espacios en blanco
   - `vocabulary`: Para términos en inglés

3. **Etiquetas**: Usa etiquetas para organizar
   - Facilita búsqueda en Anki
   - Ayuda a filtrar tarjetas

4. **Vista Previa**: Siempre revisa antes de sincronizar
   - Usa el selector "Preview Deck"
   - Verifica que los flashcards se vean correctamente

## 7. Próximos Pasos

1. Crea tus propios flashcards
2. Sincroniza múltiples mazos
3. Estudia en Anki
4. Sincroniza más contenido

## 8. Recursos Adicionales

- **Guía Completa**: Ver `ANKI_SYNC_GUIDE.md`
- **Documentación Técnica**: Ver `ANKI_INTEGRATION_README.md`
- **Anki Manual**: https://docs.ankiweb.net/
- **AnkiConnect**: https://github.com/FooSoft/anki-connect

---

¡Listo! Ya puedes empezar a sincronizar flashcards con Anki.
