# Corre esto para actualizar tu .env automáticamente
import os

env_path = ".env"
new_vars = {
    "API_KEY_SECRET": "flashcards_secret_2026",
    "POSTGRES_USER": "admin",
    "POSTGRES_PASSWORD": "admin123",
    "POSTGRES_DB": "flashcards",
    "S3_BUCKET_NAME": "flashcards-media",
}

with open(env_path, "a") as f:
    f.write("\n# --- MLOps Modernization Vars ---\n")
    for k, v in new_vars.items():
        f.write(f"{k}={v}\n")
print("✅ .env actualizado con variables de seguridad y base de datos.")
