"""
Conversor simple de flashcards a formato TSV para Anki.
Sin IA, solo conversión de formato.
"""

import re
from typing import List, Dict, Tuple


class FlashcardsConverter:
    """Convierte flashcards en formato P:/R: a TSV para Anki."""
    
    @staticmethod
    def parse_generic(text: str) -> List[Tuple[str, str]]:
        """
        Parser genérico robusto.
        Busca: P: ... R: ... P: (siguiente)
        """
        flashcards = []
        
        # Encontrar todas las posiciones de P: y R:
        p_positions = [(m.start(), m.end()) for m in re.finditer(r'P:', text)]
        r_positions = [(m.start(), m.end()) for m in re.finditer(r'R:', text)]
        
        if not p_positions:
            return flashcards
        
        # Para cada P:
        for i, (p_start, p_end) in enumerate(p_positions):
            # Encontrar el R: más cercano después de este P:
            r_match = None
            for r_start, r_end in r_positions:
                if r_start > p_end:
                    r_match = (r_start, r_end)
                    break
            
            if not r_match:
                continue
            
            r_start, r_end = r_match
            
            # Encontrar el siguiente P: (o fin del texto)
            next_p_start = len(text)
            if i + 1 < len(p_positions):
                next_p_start = p_positions[i + 1][0]
            
            # Extraer pregunta (entre P: y R:)
            front = text[p_end:r_start].strip()
            
            # Extraer respuesta (entre R: y siguiente P:)
            back = text[r_end:next_p_start].strip()
            
            if front and back:
                flashcards.append((front, back))
        
        return flashcards
    
    @staticmethod
    def parse_basic(text: str) -> List[Tuple[str, str]]:
        """
        Parsea flashcards básicos.
        Formato: P: pregunta R: respuesta P: pregunta2 R: respuesta2
        """
        return FlashcardsConverter.parse_generic(text)
    
    @staticmethod
    def parse_multiple_choice(text: str) -> List[Tuple[str, str]]:
        """
        Parsea flashcards de opción múltiple.
        Formato: P: pregunta A) opción1 B) opción2 C) opción3 D) opción4 R: respuesta
        """
        return FlashcardsConverter.parse_generic(text)
    
    @staticmethod
    def parse_cloze(text: str) -> List[Tuple[str, str]]:
        """
        Parsea flashcards Cloze.
        Formato: P: texto con {{c1::respuesta::extra}} P: siguiente
        Si no hay R:, usa el siguiente P: como delimitador.
        """
        flashcards = []
        
        # Encontrar todas las posiciones de P:
        p_positions = [(m.start(), m.end()) for m in re.finditer(r'P:', text)]
        
        if not p_positions:
            return flashcards
        
        # Para cada P:
        for i, (p_start, p_end) in enumerate(p_positions):
            # Encontrar el siguiente P: (o fin del texto)
            next_p_start = len(text)
            if i + 1 < len(p_positions):
                next_p_start = p_positions[i + 1][0]
            
            # Extraer contenido (entre P: y siguiente P:)
            content = text[p_end:next_p_start].strip()
            
            if content:
                # Para Cloze, el contenido es el "Texto" y el "Extra" es vacío
                # Pero para que se reconozca como flashcard en TSV, usar un placeholder
                flashcards.append((content, "[Cloze]"))
        
        return flashcards
    
    @staticmethod
    def parse_vocabulary(text: str) -> List[Tuple[str, str]]:
        """
        Parsea flashcards de vocabulario.
        Formato: P: Término R: Pronunciación /.../ Contexto
        """
        return FlashcardsConverter.parse_generic(text)
    
    @staticmethod
    def to_tsv(flashcards: List[Tuple[str, str]]) -> str:
        """
        Convierte lista de flashcards a formato TSV.
        Formato: pregunta\trespuesta\n
        """
        lines = []
        for front, back in flashcards:
            # Escapar saltos de línea en los campos
            front_escaped = front.replace('\n', ' | ')
            back_escaped = back.replace('\n', ' | ')
            lines.append(f"{front_escaped}\t{back_escaped}")
        
        return '\n'.join(lines)
    
    @staticmethod
    def convert(text: str, card_type: str) -> str:
        """
        Convierte flashcards al formato TSV.
        
        Args:
            text: Texto con flashcards en formato P:/R:
            card_type: Tipo de flashcard (basic, multiple_choice, cloze, vocabulary, level_*)
            
        Returns:
            String en formato TSV
        """
        if card_type == "basic":
            flashcards = FlashcardsConverter.parse_basic(text)
        elif card_type == "multiple_choice":
            flashcards = FlashcardsConverter.parse_multiple_choice(text)
        elif card_type == "cloze":
            flashcards = FlashcardsConverter.parse_cloze(text)
        elif card_type == "vocabulary":
            flashcards = FlashcardsConverter.parse_vocabulary(text)
        # Niveles Bloom
        elif card_type == "level_1_cloze":
            flashcards = FlashcardsConverter.parse_cloze(text)
        elif card_type == "level_2_relations":
            flashcards = FlashcardsConverter.parse_basic(text)
        elif card_type == "level_3_application":
            flashcards = FlashcardsConverter.parse_basic(text)
        elif card_type == "level_4_analysis":
            flashcards = FlashcardsConverter.parse_multiple_choice(text)
        else:
            flashcards = []
        
        return FlashcardsConverter.to_tsv(flashcards)
