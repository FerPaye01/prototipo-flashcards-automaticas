import os
import google.generativeai as genai
from dotenv import load_dotenv
import urllib.request
import json

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    ocr_keys = os.getenv("GEMINI_API_KEYS_OCR")
    if ocr_keys:
        api_key = [k.strip() for k in ocr_keys.split(",") if k.strip()][0]

modelos_multimedia = [
    "lyria-3-clip-preview",
    "lyria-3-pro-preview",
    "veo-2.0-generate-001",
    "veo-3.0-fast-generate-001",
    "veo-3.0-generate-001",
    "veo-3.1-fast-generate-preview",
    "veo-3.1-generate-preview",
    "veo-3.1-lite-generate-preview"
]

print("==================================================")
print("🎥🎵 Probando Modelos de Audio (Lyria) y Video (Veo)")
print("==================================================")
print("Nota: Estos modelos usualmente están en alpha privada o usan Endpoints REST puros.")
print("Verificando accesibilidad...\n")

for m in modelos_multimedia:
    print(f"🔹 {m}")
    try:
        # Puesto que Veo y Lyria raramente están expuestos en el objeto GenerativeModel nativo,
        # hacemos una petición REST simple para pedir información del modelo.
        # Si devuelve 404 = No existe o no hay acceso.
        # Si devuelve 403/429/200 = Existe y la API key lo reconoce.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}?key={api_key}"
        req = urllib.request.Request(url)
        
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                print(f"  ✅ Acceso Permitido -> El modelo está activo en tu cuenta.")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("  ❌ Error 429: Acceso detectado, pero tu cuota está excedida.")
            elif e.code == 404:
                print("  ❌ Error 404: No tienes acceso a este modelo o requiere programa Alpha/Beta.")
            elif e.code == 403:
                print("  ❌ Error 403: Permisos insuficientes para este modelo experimental.")
            else:
                print(f"  ❌ Error HTTP: {e.code}")

    except Exception as e:
        print(f"  ❌ Error de conexión: {e}")
        
print("==================================================")
