from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import time

load_dotenv()

# Obtener una llave API de la lista del .env
keys = os.environ.get("GEMINI_API_KEYS_1", "").split(",")
api_key = keys[0].strip() if keys else None

# Inicializar cliente con la llave explícita
client = genai.Client(api_key=api_key)

# Usaremos el video test1.mp4 como solicitaste
test_file_path = "test1.mp4"

if not os.path.exists(test_file_path):
    print(f"Error: El archivo {test_file_path} no existe en el directorio actual.")
    exit(1)

print(f"Subiendo video completo {test_file_path} a Gemini...")
start_upload = time.time()
myfile = client.files.upload(file=test_file_path)
print(f"Video subido en {time.time() - start_upload:.1f}s. ID: {myfile.name}. Esperando a que termine de procesarse...")

# Esperar a que el video sea procesado
# Los videos tardan unos segundos extra en estar listos (ACTIVE) en los servidores de Google
while myfile.state.name == "PROCESSING":
    print(".", end="", flush=True)
    time.sleep(3)
    myfile = client.files.get(name=myfile.name)
print(f"\nEstado final del archivo: {myfile.state.name}")

if myfile.state.name == "FAILED":
    print(f"Error procesando el archivo: {myfile.error}")
    exit(1)

# Leer el modelo del entorno, por defecto gemini-3-flash-preview
model_name = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")

print(f"Generando transcripción estructurada con {model_name}...")
start_infer = time.time()

# Prompt diseñado para transcripción de video
prompt = (
    "Por favor, escucha cuidadosamente el audio de este video y proporciona una "
    "transcripción completa, palabra por palabra, de todo lo que se dice. "
    "Aplica las siguientes reglas estrictas:\n"
    "- Mantén una excelente ortografía y puntuación en español.\n"
    "- Este es un contexto sobre derecho, SERVIR, secretaría técnica disciplinaria, etc.\n"
    "- Si hay pausas largas, simplemente sigue con el texto.\n"
    "- No hagas resúmenes, no crees cuestionarios. Solo devuelve la transcripción literal del locutor."
)

response = client.models.generate_content(
    model=model_name,
    contents=[myfile, prompt]
)

print(f"Transcripción generada en {time.time() - start_infer:.1f}s")
print("\n--- TRANSCRIPCIÓN DEL VIDEO COMPLETO ---")
print(response.text)
