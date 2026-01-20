# arhivo: crear_cliente.py
from google import genai
from dotenv import load_dotenv #https://bbc2.github.io/python-dotenv/ 

import os

# Cargar las variables del archivo .env
load_dotenv()
# Obtener la clave API desde la variable de entorno
My_API_KEY = os.getenv("GEMINI_API_KEY")

if not My_API_KEY:
    raise ValueError("GEMINI_API_KEY no está definido.")
# el siguiento comentario se enfoca en usar las variables pero definidas en la configuracion del sistema
#Cómo configurar la clave de API como una variable de entorno https://ai.google.dev/gemini-api/docs/api-key?hl=es-419#set-api-env-var

client = genai.Client(api_key=My_API_KEY)
