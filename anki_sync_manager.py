"""
Módulo para gestionar la sincronización de flashcards con Anki.
Soporta 4 tipos de flashcards:
1. Básico (Anverso/Reverso)
2. Opción Múltiple (con saltos de línea entre opciones)
3. Respuesta Anidada (Cloze Deletion)
4. Vocabulario en Inglés (Término/Pronunciación/Contexto)
"""

import subprocess
import os
import sys
import time
import json
from typing import List, Dict, Any, Tuple
from pathlib import Path
import re
from typing import Optional
# Try to import AnkiConnect
try:
    import requests
    ANKICONNECT_AVAILABLE = True
except ImportError:
    ANKICONNECT_AVAILABLE = False


class AnkiSyncManager:
    """Gestor de sincronización con Anki a través de AnkiConnect."""
    
    ANKI_CONNECT_URL = "http://localhost:8765"
    ANKI_CONNECT_VERSION = 6
    
    # Tipos de flashcards soportados
    CARD_TYPE_BASIC = "basic"
    CARD_TYPE_MULTIPLE_CHOICE = "multiple_choice"
    CARD_TYPE_CLOZE = "cloze"
    CARD_TYPE_VOCABULARY = "vocabulary"
    
    def __init__(self, connect_url: Optional[str] = None):
        """Inicializa el gestor de sincronización."""
        self.ANKI_CONNECT_URL = connect_url or os.getenv("ANKI_CONNECT_URL", "http://localhost:8765")
        self.anki_running = False
        self.anki_process = None
        self.last_error = None
        self._check_anki_status()
    
    def _check_anki_status(self) -> bool:
        """
        Verifica si Anki está ejecutándose.
        
        Returns:
            bool: True si Anki está ejecutándose, False en caso contrario
        """
        if not ANKICONNECT_AVAILABLE:
            self.last_error = "requests library not available"
            return False
        
        try:
            response = requests.post(
                self.ANKI_CONNECT_URL,
                json={"action": "version", "version": self.ANKI_CONNECT_VERSION},
                timeout=2
            )
            self.anki_running = response.status_code == 200
            return self.anki_running
        except (requests.ConnectionError, requests.Timeout):
            self.anki_running = False
            return False
        except Exception as e:
            self.last_error = str(e)
            self.anki_running = False
            return False
    
    def ensure_anki_running(self) -> Tuple[bool, str]:
        """
        Asegura que Anki esté ejecutándose. Si no está, intenta abrirlo.
        
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        if self._check_anki_status():
            return True, "Anki is already running"
        
        # Intentar abrir Anki
        try:
            if sys.platform == "win32":
                # Windows
                anki_paths = [
                    os.path.expandvars(r"%ProgramFiles%\Anki\anki.exe"),
                    os.path.expandvars(r"%ProgramFiles(x86)%\Anki\anki.exe"),
                    os.path.expandvars(r"%APPDATA%\Anki\anki.exe"),
                ]
                
                for path in anki_paths:
                    if os.path.exists(path):
                        subprocess.Popen(path)
                        # Esperar a que Anki inicie
                        for _ in range(30):  # 30 intentos, 1 segundo cada uno
                            time.sleep(1)
                            if self._check_anki_status():
                                return True, "Anki started successfully"
                        return False, "Anki started but AnkiConnect not responding"
                
                return False, "Anki installation not found"
            
            elif sys.platform == "darwin":
                # macOS
                subprocess.Popen(["open", "-a", "Anki"])
                for _ in range(30):
                    time.sleep(1)
                    if self._check_anki_status():
                        return True, "Anki started successfully"
                return False, "Anki started but AnkiConnect not responding"
            
            elif sys.platform == "linux":
                # Linux
                subprocess.Popen(["anki"])
                for _ in range(30):
                    time.sleep(1)
                    if self._check_anki_status():
                        return True, "Anki started successfully"
                return False, "Anki started but AnkiConnect not responding"
            
            else:
                return False, f"Unsupported platform: {sys.platform}"
        
        except Exception as e:
            self.last_error = str(e)
            return False, f"Failed to start Anki: {e}"
    
    def create_deck(self, deck_name: str) -> Tuple[bool, str]:
        """
        Crea un mazo en Anki.
        
        Args:
            deck_name: Nombre del mazo
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        if not self.anki_running:
            return False, "Anki is not running"
        
        try:
            response = requests.post(
                self.ANKI_CONNECT_URL,
                json={
                    "action": "deckNames",
                    "version": self.ANKI_CONNECT_VERSION
                },
                timeout=5
            )
            
            if response.status_code != 200:
                return False, "Failed to communicate with AnkiConnect"
            
            existing_decks = response.json().get("result", [])
            
            if deck_name in existing_decks:
                return True, f"Deck '{deck_name}' already exists"
            
            # Crear el mazo
            response = requests.post(
                self.ANKI_CONNECT_URL,
                json={
                    "action": "createDeck",
                    "version": self.ANKI_CONNECT_VERSION,
                    "params": {"deck": deck_name}
                },
                timeout=5
            )
            
            if response.status_code == 200:
                return True, f"Deck '{deck_name}' created successfully"
            else:
                return False, "Failed to create deck"
        
        except Exception as e:
            self.last_error = str(e)
            return False, f"Error creating deck: {e}"
    
    def add_notes(self, deck_name: str, notes: List[Dict[str, Any]]) -> Tuple[bool, str, int]:
        """
        Añade notas a un mazo en Anki en lotes.
        
        Args:
            deck_name: Nombre del mazo
            notes: Lista de notas a añadir
            
        Returns:
            Tuple[bool, str, int]: (éxito, mensaje, cantidad de notas añadidas)
        """
        if not self.anki_running:
            return False, "Anki is not running", 0
        
        if not notes:
            return False, "No notes to add", 0
        
        try:
            # Primero crear el mazo si no existe
            success, msg = self.create_deck(deck_name)
            if not success and "already exists" not in msg:
                return False, f"Failed to create deck: {msg}", 0
            
            # Preparar notas con opciones
            notes_with_options = []
            for note in notes:
                note_copy = note.copy()
                note_copy["deckName"] = deck_name
                note_copy["options"] = {
                    "allowDuplicate": True,
                    "duplicateScope": "deck",
                    "duplicateScopeOptions": {
                        "deckName": deck_name,
                        "checkChildren": False,
                        "checkAllModels": False
                    }
                }
                notes_with_options.append(note_copy)
            
            # Añadir todas las notas en un lote con addNotes
            response = requests.post(
                self.ANKI_CONNECT_URL,
                json={
                    "action": "addNotes",
                    "version": self.ANKI_CONNECT_VERSION,
                    "params": {
                        "notes": notes_with_options
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("error"):
                    return False, f"AnkiConnect error: {result['error']}", 0
                
                added_ids = result.get("result", [])
                added_count = len([id for id in added_ids if id is not None])
                
                if added_count > 0:
                    return True, f"Added {added_count} notes to '{deck_name}'", added_count
                else:
                    return False, "No notes were added", 0
            else:
                return False, "Failed to add notes", 0
        
        except Exception as e:
            self.last_error = str(e)
            return False, f"Error adding notes: {e}", 0
    
    def _get_available_models(self) -> List[str]:
        """Obtiene los modelos disponibles en Anki."""
        try:
            response = requests.post(
                self.ANKI_CONNECT_URL,
                json={"action": "modelNames", "version": self.ANKI_CONNECT_VERSION},
                timeout=5
            )
            if response.status_code == 200:
                return response.json().get("result", [])
        except:
            pass
        return []
    
    def _get_model_name(self, preferred: str) -> str:
        """Obtiene el nombre del modelo exacto."""
        if preferred == "Basic":
            return "Básico"
        elif preferred == "Cloze":
            return "Respuesta anidada"
        return preferred
    
    def format_flashcard_to_anki(self, flashcard: Dict[str, str], card_type: str) -> Dict[str, Any]:
        """
        Convierte un flashcard al formato de Anki.
        
        Args:
            flashcard: Diccionario con los datos del flashcard
            card_type: Tipo de flashcard (basic, multiple_choice, cloze, vocabulary, level_*)
            
        Returns:
            Dict con el formato de nota de Anki
        """
        # Determinar si es tipo Cloze
        is_cloze = card_type in [self.CARD_TYPE_CLOZE, "level_1_cloze"]
        
        if is_cloze:
            # Cloze: campos "Texto" y "Extra"
            return {
                "deckName": "",
                "modelName": "Respuesta anidada",
                "fields": {
                    "Texto": flashcard.get("front", ""),
                    "Extra": flashcard.get("back", "")
                },
                "tags": flashcard.get("tags", [])
            }
        
        else:
            # Basic, Multiple Choice, Vocabulary, Niveles 2-4: campos "Anverso" y "Reverso"
            front = flashcard.get("front", "")
            options = flashcard.get("options", [])
            
            # Para multiple choice, incluir opciones
            if options:
                options_text = "\n".join(options)
                front = f"{front}\n\n{options_text}"
            
            return {
                "deckName": "",
                "modelName": "Básico",
                "fields": {
                    "Anverso": front,
                    "Reverso": flashcard.get("back", "")
                },
                "tags": flashcard.get("tags", [])
            }
    
    def parse_flashcards_from_text(self, text: str, card_type: str) -> List[Dict[str, Any]]:
        """
        Parsea flashcards desde texto según el tipo.
        
        Args:
            text: Texto con flashcards
            card_type: Tipo de flashcard
            
        Returns:
            Lista de flashcards parseados
        """
        flashcards = []
        
        if card_type == self.CARD_TYPE_BASIC:
            # Formato: P: pregunta\nR: respuesta\n\nP: pregunta2\nR: respuesta2
            pattern = r"P:\s*(.+?)\s*\nR:\s*(.+?)(?=\n\nP:|$)"
            matches = re.findall(pattern, text, re.DOTALL)
            
            for front, back in matches:
                flashcards.append({
                    "front": front.strip(),
                    "back": back.strip(),
                    "tags": ["basic"]
                })
        
        elif card_type == self.CARD_TYPE_MULTIPLE_CHOICE:
            # Formato: P: pregunta\nA) opción1\nB) opción2\nC) opción3\nD) opción4\nR: respuesta
            pattern = r"P:\s*(.+?)\n((?:[A-D]\).*\n?)+)R:\s*(.+?)(?=\n\nP:|$)"
            matches = re.findall(pattern, text, re.DOTALL)
            
            for front, options_text, back in matches:
                options = [opt.strip() for opt in options_text.strip().split('\n') if opt.strip()]
                flashcards.append({
                    "front": front.strip(),
                    "options": options,
                    "back": back.strip(),
                    "tags": ["multiple_choice"]
                })
        
        elif card_type == self.CARD_TYPE_CLOZE:
            # Formato: P: texto con {{c1::respuesta::extra}}\nR: extra
            pattern = r"P:\s*(.+?)\nR:\s*(.+?)(?=\n\nP:|$)"
            matches = re.findall(pattern, text, re.DOTALL)
            
            for text_content, extra in matches:
                flashcards.append({
                    "text": text_content.strip(),
                    "extra": extra.strip(),
                    "tags": ["cloze"]
                })
        
        elif card_type == self.CARD_TYPE_VOCABULARY:
            # Formato: P: Término\nR: Pronunciación /.../ Contexto
            pattern = r"P:\s*(.+?)\nR:\s*(.+?)(?=\n\nP:|$)"
            matches = re.findall(pattern, text, re.DOTALL)
            
            for term, rest in matches:
                # Parsear pronunciación y contexto
                pron_match = re.search(r"/(.+?)/", rest)
                pronunciation = pron_match.group(1) if pron_match else ""
                context = re.sub(r"/(.+?)/", "", rest).strip()
                
                flashcards.append({
                    "term": term.strip(),
                    "pronunciation": pronunciation,
                    "context": context,
                    "tags": ["vocabulary"]
                })
        
        return flashcards
    
    def sync_flashcards_to_anki(
        self,
        deck_name: str,
        flashcards_data: List[Dict[str, Any]],
        card_type: str
    ) -> Tuple[bool, str, int]:
        """
        Sincroniza flashcards a Anki.
        
        Args:
            deck_name: Nombre del mazo
            flashcards_data: Lista de flashcards a sincronizar
            card_type: Tipo de flashcard
            
        Returns:
            Tuple[bool, str, int]: (éxito, mensaje, cantidad sincronizada)
        """
        # Asegurar que Anki está ejecutándose
        success, msg = self.ensure_anki_running()
        if not success:
            return False, msg, 0
        
        # Convertir flashcards al formato de Anki
        anki_notes = []
        for flashcard in flashcards_data:
            note = self.format_flashcard_to_anki(flashcard, card_type)
            note["deckName"] = deck_name
            anki_notes.append(note)
        
        # Añadir notas a Anki
        return self.add_notes(deck_name, anki_notes)
