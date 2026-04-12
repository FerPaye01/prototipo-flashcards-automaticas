from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import time

load_dotenv()

# Obtener una llave API de la lista del .env
keys = os.environ.get("GEMINI_API_KEYS_1", "").split(",")
api_key = keys[0].strip() if keys else None

# Inicializar cliente con la llave explícita para evitar que intente usar Vertex AI
client = genai.Client(api_key=api_key)

# Usaremos uno de los pequeños audios/videos que generó tu programa como prueba
# Cambia esta ruta si quieres probar con otro
test_file_path = r"temp_videos\tmpdzizx721.wav" 

print(f"Subiendo archivo {test_file_path}...")
myfile = client.files.upload(file=test_file_path)
print(f"Archivo subido: {myfile.name}. Esperando a que esté listo...")

# Esperar a que el archivo sea procesado (necesario para audio/video en la API)
while myfile.state.name == "PROCESSING":
    print(".", end="", flush=True)
    time.sleep(2)
    myfile = client.files.get(name=myfile.name)
print(f"\nEstado del archivo: {myfile.state.name}")

if myfile.state.name == "FAILED":
    print("Error procesando el archivo.")
    exit(1)

# Leer el modelo del entorno, por defecto gemini-3-flash-preview
model_name = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")

print(f"Generando transcripción con {model_name}...")
response = client.models.generate_content(
    model=model_name,
    contents=[
        myfile, 
        "Por favor, transcribe palabra por palabra lo que se dice en este audio. Asegúrate de tener buena ortografía y puntuación en español."
    ]
)

print("\n--- TRANSCRIPCIÓN ---")
print(response.text)