import os
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    ocr_keys = os.getenv("GEMINI_API_KEYS_OCR")
    if ocr_keys:
        api_key = [k.strip() for k in ocr_keys.split(",") if k.strip()][0]

modelos_imagen = [
    "imagen-4.0-fast-generate-001",
    "imagen-4.0-generate-001",
    "imagen-4.0-ultra-generate-001"
]

print("==================================================")
print("🖼️ Probando Modelos de Generación de Imagen (vía REST)")
print("==================================================")

for m in modelos_imagen:
    print(f"🔹 {m}")
    try:
        # Petición GET directa para ver si la API Key tiene acceso al modelo de Imagen
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}?key={api_key}"
        req = urllib.request.Request(url)
        
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                print(f"  ✅ Acceso Permitido -> El modelo está activo en tu cuenta y listo para usarse.")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("  ❌ Error 429: Tienes acceso, pero tu cuota está excedida.")
            elif e.code == 404:
                print("  ❌ Error 404: No tienes acceso a este modelo o requiere whitelist.")
            elif e.code == 403:
                print("  ❌ Error 403: Permisos insuficientes para Imagen 4.0.")
            else:
                print(f"  ❌ Error HTTP: {e.code}")

    except Exception as e:
        print(f"  ❌ Error de conexión: {e}")
        
print("==================================================")
