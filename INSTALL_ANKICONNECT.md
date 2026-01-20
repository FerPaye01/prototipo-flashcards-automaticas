# Instalación de AnkiConnect

AnkiConnect es un complemento de Anki que permite que aplicaciones externas se comuniquen con Anki a través de una API REST. Es **obligatorio** para que la funcionalidad de Anki Sync funcione.

## Requisitos Previos

- Anki 2.1.50 o superior
- Conexión a Internet (para descargar el complemento)

## Pasos de Instalación

### Opción 1: Instalación Automática (Recomendado)

#### Paso 1: Abre Anki
Inicia la aplicación Anki en tu computadora.

#### Paso 2: Accede al Gestor de Complementos
- Ve a **Tools** (Herramientas) en la barra de menú
- Selecciona **Add-ons** (Complementos)
- Haz clic en **Get Add-ons** (Obtener Complementos)

#### Paso 3: Ingresa el Código de AnkiConnect
- Se abrirá una ventana de diálogo
- Ingresa el código: `2055492159`
- Haz clic en **OK**

#### Paso 4: Reinicia Anki
- Cierra Anki completamente
- Vuelve a abrir Anki
- AnkiConnect debería estar instalado

#### Paso 5: Verifica la Instalación
- Ve a **Tools** → **Add-ons**
- Busca "AnkiConnect" en la lista
- Debería aparecer en la lista de complementos instalados

---

### Opción 2: Instalación Manual

Si la instalación automática no funciona:

#### Paso 1: Descarga AnkiConnect
1. Ve a: https://github.com/FooSoft/anki-connect/releases
2. Descarga el archivo más reciente (generalmente `AnkiConnect.ankiaddon`)

#### Paso 2: Instala el Complemento
1. Abre Anki
2. Ve a **Tools** → **Add-ons** → **Install Add-on**
3. Selecciona el archivo `AnkiConnect.ankiaddon` descargado
4. Haz clic en **Open**

#### Paso 3: Reinicia Anki
- Cierra Anki completamente
- Vuelve a abrir Anki

---

## Verificación de la Instalación

### Método 1: Verificar en Anki
1. Abre Anki
2. Ve a **Tools** → **Add-ons**
3. Busca "AnkiConnect" en la lista
4. Debería estar habilitado (checkbox marcado)

### Método 2: Verificar Conexión
1. Abre una terminal/consola
2. Ejecuta el siguiente comando:
   ```bash
   curl -X POST http://localhost:8765 -d "{\"action\": \"version\", \"version\": 6}"
   ```
3. Si AnkiConnect está funcionando, verás una respuesta JSON

### Método 3: Verificar en el Programa
1. Ejecuta el programa de flashcards
2. Selecciona la pestaña "Anki Sync"
3. El indicador de estado debería ser **verde** (Anki ejecutándose)

---

## Solución de Problemas

### Problema: No puedo encontrar "Get Add-ons"
**Solución:**
- Asegúrate de tener Anki 2.1.50 o superior
- Actualiza Anki desde: https://apps.ankiweb.net/

### Problema: El código 2055492159 no funciona
**Solución:**
- Verifica que hayas ingresado el código correctamente
- Intenta la instalación manual

### Problema: AnkiConnect no aparece en la lista de complementos
**Solución:**
- Reinicia Anki completamente
- Intenta instalar nuevamente
- Verifica que tengas permisos de administrador

### Problema: "AnkiConnect not responding"
**Solución:**
- Verifica que AnkiConnect esté habilitado en Anki
- Reinicia Anki
- Comprueba que el puerto 8765 no esté bloqueado por un firewall

### Problema: El puerto 8765 está en uso
**Solución:**
- Cierra otras aplicaciones que usen el puerto 8765
- Reinicia tu computadora
- Contacta al equipo de soporte

---

## Configuración Avanzada

### Cambiar el Puerto de AnkiConnect
Por defecto, AnkiConnect usa el puerto 8765. Si necesitas cambiar el puerto:

1. Abre Anki
2. Ve a **Tools** → **Add-ons** → **AnkiConnect** → **Config**
3. Modifica el valor de `"webBindPort"` (por defecto 8765)
4. Guarda los cambios
5. Reinicia Anki

### Habilitar CORS (Cross-Origin Resource Sharing)
Si necesitas acceder a AnkiConnect desde un dominio diferente:

1. Abre Anki
2. Ve a **Tools** → **Add-ons** → **AnkiConnect** → **Config**
3. Modifica `"webCorsOriginList"` según sea necesario
4. Guarda los cambios
5. Reinicia Anki

---

## Verificación de Funcionamiento

### Test 1: Verificar Versión
```bash
curl -X POST http://localhost:8765 \
  -d "{\"action\": \"version\", \"version\": 6}"
```

**Respuesta esperada:**
```json
{"result": 6, "error": null}
```

### Test 2: Obtener Nombres de Mazos
```bash
curl -X POST http://localhost:8765 \
  -d "{\"action\": \"deckNames\", \"version\": 6}"
```

**Respuesta esperada:**
```json
{"result": ["Default", "Otros mazos..."], "error": null}
```

---

## Desinstalación

Si necesitas desinstalar AnkiConnect:

1. Abre Anki
2. Ve a **Tools** → **Add-ons**
3. Selecciona "AnkiConnect"
4. Haz clic en **Delete** (Eliminar)
5. Reinicia Anki

---

## Recursos Adicionales

- **Página oficial de AnkiConnect**: https://github.com/FooSoft/anki-connect
- **Documentación de AnkiConnect**: https://github.com/FooSoft/anki-connect#readme
- **Foro de Anki**: https://forums.ankiweb.net/
- **Documentación de Anki**: https://docs.ankiweb.net/

---

## Soporte

Si tienes problemas con la instalación de AnkiConnect:

1. Verifica que Anki esté actualizado
2. Intenta desinstalar y reinstalar AnkiConnect
3. Reinicia tu computadora
4. Contacta al equipo de soporte de Anki

---

## Notas Importantes

1. **AnkiConnect debe estar ejecutándose**: Anki debe estar abierto para que AnkiConnect funcione
2. **Puerto 8765**: Debe estar disponible en tu sistema
3. **Firewall**: Asegúrate de que tu firewall no bloquee el puerto 8765
4. **Versión de Anki**: Requiere Anki 2.1.50 o superior

---

**Última actualización**: Noviembre 2025
**Versión de AnkiConnect**: 6.0+
