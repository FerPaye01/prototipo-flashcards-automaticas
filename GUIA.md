
🔴 1. Cierra cualquier .exe que hayas intentado ejecutar antes

Asegúrate de que programa_proyecto_flashcards_automaticas.exe no esté abierto ni ejecutándose en segundo plano.

Abre el Administrador de tareas (Ctrl + Shift + Esc) y cierra cualquier proceso con ese nombre si existe.

🟡 2. Elimina manualmente los directorios build, dist y el .spec

Ya que estás en PowerShell, usa esta sintaxis:

Remove-Item -Recurse -Force build, dist
Remove-Item programa_proyecto_flashcards_automaticas.spec

🟢 3. Ejecuta PowerShell como administrador

Cierra tu PowerShell o terminal actual.

Abre PowerShell como administrador (clic derecho → "Ejecutar como administrador").

Navega a tu proyecto:

cd "D:\Cursos\DECIMO\TRABAJO DE INVESTIGACION\PP001-api_gemini"

🔵 4. Vuelve a compilar con PyInstaller

Ejecuta:

pyinstaller --onefile --noconsole programa_proyecto_flashcards_automaticas.py

🟣 5. Desactiva temporalmente tu antivirus o Windows Defender

A veces bloquean la creación de archivos .exe. Puedes:

Añadir una exclusión para tu carpeta del proyecto.

O temporalmente desactivar protección solo durante la compilación.

✅ Confirmación

Después de seguir estos pasos, deberías ver el .exe generado en:

D:\Cursos\DECIMO\TRABAJO DE INVESTIGACION\PP001-api_gemini\dist
