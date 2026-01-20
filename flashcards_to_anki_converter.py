"""
Módulo para convertir flashcards generadas (formato TSV) a Anki automáticamente.
Integra la generación de flashcards con la sincronización a Anki.
"""

import re
from typing import List, Dict, Any, Tuple
from anki_sync_manager import AnkiSyncManager


class FlashcardsToAnkiConverter:
    """Convierte flashcards en formato TSV a Anki automáticamente."""
    
    def __init__(self):
        """Inicializa el convertidor."""
        self.anki_manager = AnkiSyncManager()
        self.last_error = None
    
    def parse_tsv_flashcards(self, tsv_text: str) -> List[Dict[str, str]]:
        """
        Parsea flashcards en formato TSV (pregunta\trespuesta).
        
        Args:
            tsv_text: Texto con flashcards en formato TSV
            
        Returns:
            Lista de diccionarios con 'front' y 'back'
        """
        flashcards = []
        
        # Dividir por líneas y filtrar vacías
        lines = [line.strip() for line in tsv_text.split('\n') if line.strip()]
        
        for line in lines:
            # Buscar el separador de tabulación
            if '\t' in line:
                parts = line.split('\t', 1)  # Máximo 2 partes
                if len(parts) == 2:
                    front, back = parts
                    flashcards.append({
                        'front': front.strip(),
                        'back': back.strip(),
                        'tags': ['auto-generated']
                    })
        
        return flashcards
    
    def format_for_anki(self, flashcards: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Convierte flashcards al formato de Anki.
        
        Args:
            flashcards: Lista de flashcards parseados
            
        Returns:
            Lista de notas en formato Anki
        """
        anki_notes = []
        
        for flashcard in flashcards:
            note = {
                "modelName": "Basic",
                "fields": {
                    "Front": flashcard.get('front', ''),
                    "Back": flashcard.get('back', '')
                },
                "tags": flashcard.get('tags', [])
            }
            anki_notes.append(note)
        
        return anki_notes
    
    def sync_to_anki(
        self,
        tsv_flashcards: str,
        deck_name: str = "Auto-Generated Flashcards"
    ) -> Tuple[bool, str, int]:
        """
        Convierte y sincroniza flashcards TSV a Anki automáticamente.
        
        Args:
            tsv_flashcards: Texto con flashcards en formato TSV
            deck_name: Nombre del mazo en Anki
            
        Returns:
            Tuple[bool, str, int]: (éxito, mensaje, cantidad sincronizada)
        """
        try:
            # Paso 1: Parsear flashcards TSV
            flashcards = self.parse_tsv_flashcards(tsv_flashcards)
            
            if not flashcards:
                self.last_error = "No flashcards found in TSV format"
                return False, "No flashcards found in TSV format", 0
            
            # Paso 2: Convertir al formato de Anki
            anki_notes = self.format_for_anki(flashcards)
            
            # Paso 3: Asegurar que Anki está ejecutándose
            success, msg = self.anki_manager.ensure_anki_running()
            if not success:
                self.last_error = msg
                return False, msg, 0
            
            # Paso 4: Crear el mazo si no existe
            success, msg = self.anki_manager.create_deck(deck_name)
            if not success and "already exists" not in msg:
                self.last_error = msg
                return False, f"Failed to create deck: {msg}", 0
            
            # Paso 5: Añadir notas al mazo
            for note in anki_notes:
                note["deckName"] = deck_name
            
            success, msg, count = self.anki_manager.add_notes(deck_name, anki_notes)
            
            if success:
                return True, f"Successfully synced {count} flashcards to Anki deck '{deck_name}'", count
            else:
                self.last_error = msg
                return False, msg, 0
        
        except Exception as e:
            self.last_error = str(e)
            return False, f"Error during conversion: {str(e)}", 0
    
    def get_last_error(self) -> str:
        """Retorna el último error ocurrido."""
        return self.last_error or "No error"


# Función de conveniencia para uso directo
def convert_and_sync_flashcards(
    tsv_flashcards: str,
    deck_name: str = "Auto-Generated Flashcards"
) -> Tuple[bool, str, int]:
    """
    Función de conveniencia para convertir y sincronizar flashcards a Anki.
    
    Args:
        tsv_flashcards: Texto con flashcards en formato TSV
        deck_name: Nombre del mazo en Anki
        
    Returns:
        Tuple[bool, str, int]: (éxito, mensaje, cantidad sincronizada)
    """
    converter = FlashcardsToAnkiConverter()
    return converter.sync_to_anki(tsv_flashcards, deck_name)
