
#automatizar_importacion.py

#Para probar conexion solo ejecutar hasta print(res)
#import requests

#res = requests.post("http://localhost:8765", json={
#    "action": "version",
#    "version": 6
#}).json()

#print(res)
import requests
import datetime
def anki_request(action, **params):
    """Envía una acción a AnkiConnect y devuelve la respuesta JSON."""
    return requests.post("http://localhost:8765", json={
        "action": action,
        "version": 6,
        "params": params
    }).json()

def parse_flashcards(texto_tab):
    """
    Convierte un bloque de texto tab-separado en una lista de flashcards.
    Cada línea debe ser 'Pregunta\tRespuesta'.
    """
    flashcards = []
    for line in texto_tab.strip().split("\n"):
        if "\t" in line:
            pregunta, respuesta = line.split("\t", 1)
            flashcards.append((pregunta.strip(), respuesta.strip()))
    return flashcards

def generar_nombre_deck():
    """Genera un nombre de deck semialeatorio basado en fecha/hora actual."""
    return "deck_" + datetime.datetime.now().strftime("%d-%m-%Y-%I-%M-%p").lower()

def crear_deck(deck_name):
    """Crea un deck en Anki (si ya existe, no hace nada)."""
    return anki_request("createDeck", deck=deck_name)

def agregar_flashcards(deck_name, flashcards):
    """
    Inserta flashcards en un deck usando el modelo 'Básico'
    con campos 'Anverso' y 'Reverso'.
    """
    notes = []
    for pregunta, respuesta in flashcards:
        notes.append({
            "deckName": deck_name,
            "modelName": "Básico",   # Tipo de nota en español
            "fields": {
                "Anverso": pregunta,
                "Reverso": respuesta
            },
            "options": {
                "allowDuplicate": True
            },
            "tags": ["auto_import"]
        })
    return anki_request("addNotes", notes=notes)

def sincronizar():
    """Sincroniza con AnkiWeb (si el usuario tiene la opción activada en Anki)."""
    return anki_request("sync")
def procesar_importacion_automática(flashcards_text):
    flashcards = parse_flashcards(flashcards_text)
    deck_name = generar_nombre_deck()
    crear_deck(deck_name)
    resultado = agregar_flashcards(deck_name, flashcards)
    print("Resultado addNotes:", resultado)
    sincronizar()
    print(f"Deck '{deck_name}' creado con {len(flashcards)} tarjetas y sincronizado con AnkiWeb.")
#if __name__ == "__main__":
    # Flashcards de ejemplo
    #flashcards_text = """¿Qué es My?\tUn sistema de de datos relacional.
    #¿Qué es PHP?\tUn lenguaje de programación de propósito general orientado a la web.
    #"""

    # Procesar flashcards
    #flashcards = parse_flashcards(flashcards_text)

    # Crear deck único
    #deck_name = generar_nombre_deck()
    #crear_deck(deck_name)

    # Agregar tarjetas
    #resultado = agregar_flashcards(deck_name, flashcards)
    #print("Resultado addNotes:", resultado)

    # Sincronizar con AnkiWeb
    #sincronizar()
    #print(f"Deck '{deck_name}' creado con {len(flashcards)} tarjetas y sincronizado con AnkiWeb.")
