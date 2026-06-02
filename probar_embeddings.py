import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    ocr_keys = os.getenv("GEMINI_API_KEYS_OCR")
    if ocr_keys:
        api_key = [k.strip() for k in ocr_keys.split(",") if k.strip()][0]

genai.configure(api_key=api_key)

modelos_embeddings = [
    "gemini-embedding-001",
    "gemini-embedding-2",
    "gemini-embedding-2-preview"
]

print("==================================================")
print("📊 Probando Modelos de Embeddings (Vectores)")
print("==================================================")

for m in modelos_embeddings:
    print(f"🔹 {m}")
    try:
        # La función correcta para embeddings es embed_content
        resultado = genai.embed_content(
            model=m,
            content="Hola, esto es una prueba para convertir texto en vectores matemáticos.",
            task_type="retrieval_document"
        )
        if resultado and 'embedding' in resultado:
            dimensiones = len(resultado['embedding'])
            print(f"  ✅ Funciona -> Vector generado correctamente (Dimensiones: {dimensiones})")
        else:
            print("  ⚠️ No se generó el vector.")
    except Exception as e:
        error_msg = str(e).replace('\n', ' ')[:130] + "..."
        print(f"  ❌ Error: {error_msg}")
print("==================================================")
