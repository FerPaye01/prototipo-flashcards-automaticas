from google import genai

import os
from dotenv import load_dotenv
load_dotenv()
# The client gets the API key from the environment variable `GEMINI_API_KEY`.
client = genai.Client(api_key=os.getenv("GEMINI_API"))

response = client.models.generate_content(
    model="gemini-3-pro-preview", contents="Explain how AI works in a few words"
)
print(response.text)