import os
import google.generativeai as genai
from dotenv import load_dotenv

# Cargar archivo .env
load_dotenv()

# 1. Tomar una sola llave (la principal)
api_key = os.getenv("GEMINI_API_KEY")

# Si no está GEMINI_API_KEY, intentamos tomar la primera de OCR
if not api_key:
    ocr_keys = os.getenv("GEMINI_API_KEYS_OCR")
    if ocr_keys:
        api_key = [k.strip() for k in ocr_keys.split(",") if k.strip()][0]

if not api_key:
    print("❌ No se encontró ninguna API key en .env (asegúrate de tener GEMINI_API_KEY configurada).")
    exit(1)

# Ocultar llave para mostrar en pantalla
key_masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "..."

print("==================================================")
print(f"🔍 Probando TODOS los modelos con la llave: {key_masked}")
print("==================================================")

try:
    genai.configure(api_key=api_key)
    modelos_brutos = list(genai.list_models())
    
    # Extraer y ordenar nombres
    modelos_nombres = sorted([m.name.replace("models/", "") for m in modelos_brutos])
    
    print(f"Detectados {len(modelos_nombres)} modelos. Iniciando test de generación individual...\n")
    
    for m_name in modelos_nombres:
        print(f"🔹 {m_name}")
        
        # Filtramos modelos que sabemos que no soportan la función básica de texto
        if "embedding" in m_name or "aqa" in m_name or "imagen" in m_name or "veo" in m_name or "lyria" in m_name or "clip" in m_name:
            print(f"  ⏭️  Saltado (modelo de embedding, multimedia o no-texto)")
            continue
            
        try:
            model = genai.GenerativeModel(m_name)
            # Prueba muy corta para que sea rápida
            response = model.generate_content("Responde únicamente con 'OK'.")
            
            if response and response.text:
                print(f"  ✅  Funciona -> Respuesta: {response.text.strip()}")
            else:
                print(f"  ⚠️  Respuesta vacía o bloqueada por filtros de seguridad.")
                
        except Exception as e:
            # Capturamos el error y lo hacemos de una línea para leer bien el log
            error_msg = str(e).replace('\n', ' ')
            if len(error_msg) > 120:
                error_msg = error_msg[:117] + "..."
            print(f"  ❌  Error: {error_msg}")

except Exception as e:
    print(f"❌ Error crítico al inicializar la API: {e}")

print("\n==================================================")
print("Prueba exhaustiva de modelos finalizada.")
print("==================================================")
