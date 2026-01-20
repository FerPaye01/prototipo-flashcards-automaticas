"""
Módulo para parsear y limpiar flashcards desde texto pegado.
Convierte automáticamente los formatos entregados al formato adecuado para Anki.
"""

import re
from typing import List, Dict, Any, Tuple


class FlashcardParser:
    """Parser para convertir flashcards de texto a formato Anki."""
    
    @staticmethod
    def detect_flashcard_type(text: str) -> str:
        """
        Detecta automáticamente el tipo de flashcard basado en el contenido.
        
        Args:
            text: Texto con flashcards
            
        Returns:
            Tipo detectado: 'basic', 'multiple_choice', 'cloze', 'vocabulary'
        """
        # Detectar Cloze (contiene {{c1::)
        if '{{c1::' in text:
            return 'cloze'
        
        # Detectar Opción Múltiple (contiene A), B), C), D))
        if re.search(r'[A-D]\)', text):
            return 'multiple_choice'
        
        # Detectar Vocabulario (contiene /)
        if re.search(r'/[^/]+/', text):
            return 'vocabulary'
        
        # Por defecto, básico
        return 'basic'
    
    @staticmethod
    def parse_raw_text(text: str) -> List[Dict[str, Any]]:
        """
        Parsea texto crudo y detecta automáticamente el tipo de cada flashcard.
        
        Args:
            text: Texto con flashcards en formato P: ... R: ...
            
        Returns:
            Lista de flashcards parseados
        """
        flashcards = []
        
        # Dividir por "P:" para obtener cada flashcard
        parts = re.split(r'\nP:', text)
        
        for part in parts:
            if not part.strip():
                continue
            
            # Agregar "P:" de vuelta para procesamiento
            part = "P:" + part
            
            # Buscar la sección de respuesta
            match = re.search(r'P:\s*(.+?)\s*R:\s*(.+?)(?=\nP:|$)', part, re.DOTALL)
            
            if match:
                question = match.group(1).strip()
                answer = match.group(2).strip()
                
                # Detectar tipo de flashcard
                combined_text = question + " " + answer
                card_type = FlashcardParser.detect_flashcard_type(combined_text)
                
                # Parsear según el tipo
                if card_type == 'multiple_choice':
                    flashcard = FlashcardParser._parse_multiple_choice(question, answer)
                elif card_type == 'cloze':
                    flashcard = FlashcardParser._parse_cloze(question, answer)
                elif card_type == 'vocabulary':
                    flashcard = FlashcardParser._parse_vocabulary(question, answer)
                else:
                    flashcard = FlashcardParser._parse_basic(question, answer)
                
                if flashcard:
                    flashcard['type'] = card_type
                    flashcards.append(flashcard)
        
        return flashcards
    
    @staticmethod
    def _parse_basic(question: str, answer: str) -> Dict[str, Any]:
        """Parsea flashcard básico."""
        return {
            'front': question,
            'back': answer,
            'tags': ['basic']
        }
    
    @staticmethod
    def _parse_multiple_choice(question: str, answer: str) -> Dict[str, Any]:
        """Parsea flashcard de opción múltiple."""
        # Extraer opciones (A), B), C), D))
        options = re.findall(r'[A-D]\)[^\n]*', question)
        
        # Limpiar la pregunta (sin opciones)
        clean_question = re.sub(r'\s*[A-D]\)[^\n]*', '', question).strip()
        
        return {
            'front': clean_question,
            'options': options,
            'back': answer,
            'tags': ['multiple_choice']
        }
    
    @staticmethod
    def _parse_cloze(question: str, answer: str) -> Dict[str, Any]:
        """Parsea flashcard Cloze."""
        return {
            'text': question,
            'extra': answer,
            'tags': ['cloze']
        }
    
    @staticmethod
    def _parse_vocabulary(question: str, answer: str) -> Dict[str, Any]:
        """Parsea flashcard de vocabulario."""
        # Extraer pronunciación entre /.../ 
        pron_match = re.search(r'/([^/]+)/', answer)
        pronunciation = pron_match.group(1) if pron_match else ""
        
        # Contexto es el resto después de la pronunciación
        context = re.sub(r'/[^/]+/', '', answer).strip()
        
        return {
            'term': question,
            'pronunciation': pronunciation,
            'context': context,
            'tags': ['vocabulary']
        }
    
    @staticmethod
    def clean_flashcard_text(text: str) -> str:
        """
        Limpia el texto pegado para mejorar el parseo.
        
        Args:
            text: Texto crudo pegado
            
        Returns:
            Texto limpiado
        """
        # Remover espacios en blanco excesivos
        text = re.sub(r'\n\s*\n', '\n', text)
        
        # Normalizar espacios alrededor de P: y R:
        text = re.sub(r'\s*\nP:\s*', '\nP: ', text)
        text = re.sub(r'\s*\nR:\s*', '\nR: ', text)
        
        # Remover espacios al inicio/final
        text = text.strip()
        
        return text
    
    @staticmethod
    def format_for_anki(flashcard: Dict[str, Any], card_type: str) -> Dict[str, Any]:
        """
        Convierte un flashcard al formato de Anki.
        
        Args:
            flashcard: Flashcard parseado
            card_type: Tipo de flashcard
            
        Returns:
            Flashcard formateado para Anki
        """
        if card_type == 'basic':
            return {
                'deckName': '',
                'modelName': 'Basic',
                'fields': {
                    'Front': flashcard.get('front', ''),
                    'Back': flashcard.get('back', '')
                },
                'tags': flashcard.get('tags', [])
            }
        
        elif card_type == 'multiple_choice':
            # Formatear opciones con saltos de línea
            options_text = '\n'.join(flashcard.get('options', []))
            front = f"{flashcard.get('front', '')}\n\n{options_text}"
            
            return {
                'deckName': '',
                'modelName': 'Basic',
                'fields': {
                    'Front': front,
                    'Back': flashcard.get('back', '')
                },
                'tags': flashcard.get('tags', [])
            }
        
        elif card_type == 'cloze':
            return {
                'deckName': '',
                'modelName': 'Cloze',
                'fields': {
                    'Text': flashcard.get('text', ''),
                    'Extra': flashcard.get('extra', '')
                },
                'tags': flashcard.get('tags', [])
            }
        
        elif card_type == 'vocabulary':
            front = f"{flashcard.get('term', '')}\n{flashcard.get('pronunciation', '')}"
            
            return {
                'deckName': '',
                'modelName': 'Basic',
                'fields': {
                    'Front': front,
                    'Back': flashcard.get('context', '')
                },
                'tags': flashcard.get('tags', [])
            }
        
        else:
            return {
                'deckName': '',
                'modelName': 'Basic',
                'fields': {
                    'Front': flashcard.get('front', ''),
                    'Back': flashcard.get('back', '')
                },
                'tags': flashcard.get('tags', [])
            }
    
    @staticmethod
    def parse_and_format(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Parsea texto crudo y lo formatea para Anki.
        
        Args:
            text: Texto crudo pegado
            
        Returns:
            Tupla de (flashcards formateados, tipos detectados)
        """
        # Limpiar texto
        cleaned_text = FlashcardParser.clean_flashcard_text(text)
        
        # Parsear
        flashcards = FlashcardParser.parse_raw_text(cleaned_text)
        
        # Formatear para Anki
        formatted = []
        types = []
        
        for card in flashcards:
            card_type = card.pop('type')
            types.append(card_type)
            
            formatted_card = FlashcardParser.format_for_anki(card, card_type)
            formatted.append(formatted_card)
        
        return formatted, types


# Ejemplo de uso
if __name__ == "__main__":
    # Test con los prompts proporcionados
    test_text = """P: Concepto: ¿Qué es la Penalización de Gradiente (Gradient Penalty - GP) en el contexto de tu arquitectura WGAN-GP?
R: Es un término de regularización agregado a la función de pérdida del Crítico que fuerza a la norma del gradiente a mantenerse cerca de 1, garantizando la continuidad de Lipschitz y la estabilidad del entrenamiento.

P: En la fase de entrenamiento del clasificador ResNet50, se utilizó la función de pérdida "Focal Loss". ¿Cuál es el mecanismo exacto por el cual esta función aborda el desbalance de clases?
A) Aumenta el peso de los ejemplos fáciles para mejorar la precisión global.
B) Reduce el peso de los ejemplos bien clasificados (fáciles), forzando al modelo a centrarse en los ejemplos difíciles (clase minoritaria).
C) Penaliza la norma del gradiente en las capas finales para evitar el overfitting en la clase mayoritaria.
D) Genera ruido gaussiano en las muestras de la clase mayoritaria para equilibrar la distribución de características.
R: B) Reduce el peso de los ejemplos bien clasificados (fáciles), forzando al modelo a centrarse en los ejemplos difíciles (clase minoritaria).

P: La métrica {{c1::F1-Score::Métrica}} combina la precisión y la exhaustividad, siendo ideal para datos desbalanceados.
R: Métrica fundamental en machine learning

P: Término: Aumentación de Datos (Contexto: Técnica para incrementar la diversidad del dataset)
R: Data Augmentation /ˌdeɪtə ɔːɡmɛnˈteɪʃən/"""
    
    formatted, types = FlashcardParser.parse_and_format(test_text)
    
    print(f"Flashcards detectados: {len(formatted)}")
    print(f"Tipos: {types}")
    print()
    
    for i, (card, card_type) in enumerate(zip(formatted, types), 1):
        print(f"Flashcard {i} ({card_type}):")
        print(f"  Modelo: {card.get('modelName')}")
        print(f"  Campos: {list(card.get('fields', {}).keys())}")
        print()
