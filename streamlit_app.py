import streamlit as st
import requests
import os
import uuid
from typing import List

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY_SECRET = os.getenv("API_KEY_SECRET", "supersecretkey")

st.set_page_config(
    page_title="Flashcards AI Dashboard",
    page_icon="🤖",
    layout="wide"
)

# Headers for Zero Trust API security
headers = {
    "X-API-Key": API_KEY_SECRET
}

# Session State Initialization
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "generated_cards" not in st.session_state:
    st.session_state.generated_cards = []

# Sidebar - Settings & Mode
with st.sidebar:
    st.title("⚙️ Configuración")
    st.info(f"Sesión activa: {st.session_state.session_id}")
    
    mode = st.radio(
        "Modo de Operación",
        ["Manual", "Imágenes", "Documentos", "Video"]
    )
    
    st.divider()
    st.write("### Opciones de IA")
    model = st.selectbox("Modelo Gemini", ["gemini-pro", "gemini-1.5-flash"])
    card_types = st.multiselect(
        "Tipos de Tarjetas",
        ["basic", "multiple_choice", "cloze", "vocabulary"],
        default=["basic"]
    )

# Main Interface
st.title("🚀 Generador de Flashcards Automáticas")

if mode == "Manual":
    st.subheader("📝 Entrada de Texto Directa")
    text_input = st.text_area("Pega aquí el contenido para estudiar:", height=300)
    
    if st.button("Generar Tarjetas", type="primary"):
        if text_input and card_types:
            with st.status("🤖 Procesando con IA...", expanded=True) as status:
                try:
                    payload = {
                        "session_id": st.session_state.session_id,
                        "text_content": text_input,
                        "card_types": card_types
                    }
                    response = requests.post(
                        f"{API_URL}/generate", 
                        json=payload, 
                        headers=headers,
                        timeout=180 # 3 minutes timeout for long AI tasks
                    )
                    
                    if response.status_code == 202:
                        data = response.json()
                        st.success(f"✅ {data['message']}")
                        status.update(label="Generación completada!", state="complete")
                    else:
                        st.error(f"❌ Error API: {response.text}")
                except Exception as e:
                    st.error(f"❌ Error de conexión: {e}")
        else:
            st.warning("Escribe algo de texto y selecciona al menos un tipo de tarjeta.")

elif mode == "Imágenes":
    st.subheader("📷 Carga de Imágenes para OCR")
    uploaded_files = st.file_uploader(
        "Suelta tus imágenes aquí (Drag & Drop nativo)", 
        accept_multiple_files=True,
        type=['png', 'jpg', 'jpeg']
    )
    
    if uploaded_files:
        for uploaded_file in uploaded_files:
            if st.button(f"Subir {uploaded_file.name}"):
                files = {"file": uploaded_file}
                res = requests.post(
                    f"{API_URL}/upload?session_id={st.session_state.session_id}",
                    files=files,
                    headers=headers
                )
                if res.status_code == 200:
                    st.success(f"Cargado en LocalStack S3: {uploaded_file.name}")
                else:
                    st.error(f"Error cargando {uploaded_file.name}")

# Historial y Sincronización
st.divider()
st.subheader("📑 Resultados y Sincronización Anki")
if st.button("Sincronizar con Anki"):
    with st.spinner("Sincronizando con Anki local..."):
        payload = {
            "session_id": st.session_state.session_id,
            "deck_name": "Default"
        }
        res = requests.post(f"{API_URL}/sync", json=payload, headers=headers)
        if res.status_code == 200:
            st.success("Tarjetas enviadas a Anki correctamente")
        else:
            st.error("Error al sincronizar con Anki")
