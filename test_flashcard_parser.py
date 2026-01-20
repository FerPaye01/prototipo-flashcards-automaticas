"""
Script de prueba para el parser de flashcards.
Prueba la detección automática y parseo de los 4 tipos de flashcards.
"""

from flashcard_parser import FlashcardParser

def test_parser():
    """Prueba el parser con los prompts proporcionados."""
    
    print("=" * 70)
    print("PRUEBA: FlashcardParser - Detección Automática y Parseo")
    print("=" * 70)
    
    # Texto de prueba con los 4 tipos de flashcards
    test_text = """P: Concepto: ¿Qué es la Penalización de Gradiente (Gradient Penalty - GP) en el contexto de tu arquitectura WGAN-GP?
R: Es un término de regularización agregado a la función de pérdida del Crítico que fuerza a la norma del gradiente a mantenerse cerca de 1, garantizando la continuidad de Lipschitz y la estabilidad del entrenamiento.

P: Análisis Sistémico: ¿Cuál es la relación causal entre el uso de la Distancia Wasserstein (en lugar de Jensen-Shannon) y la estabilidad del entrenamiento en tu modelo?
R: La Distancia Wasserstein proporciona gradientes suaves y útiles incluso cuando la distribución real y la generada no se superponen (común al inicio), evitando el problema del desvanecimiento del gradiente que sufren las GANs tradicionales.

P: En la fase de entrenamiento del clasificador ResNet50, se utilizó la función de pérdida "Focal Loss". ¿Cuál es el mecanismo exacto por el cual esta función aborda el desbalance de clases?
A) Aumenta el peso de los ejemplos fáciles para mejorar la precisión global.
B) Reduce el peso de los ejemplos bien clasificados (fáciles), forzando al modelo a centrarse en los ejemplos difíciles (clase minoritaria).
C) Penaliza la norma del gradiente en las capas finales para evitar el overfitting en la clase mayoritaria.
D) Genera ruido gaussiano en las muestras de la clase mayoritaria para equilibrar la distribución de características.
R: B) Reduce el peso de los ejemplos bien clasificados (fáciles), forzando al modelo a centrarse en los ejemplos difíciles (clase minoritaria).

P: Con respecto a la arquitectura del Generador en la WGAN-GP implementada, ¿qué función de activación se utiliza en la capa de salida para generar las imágenes de rayos X normalizadas?
A) ReLU (Rectified Linear Unit)
B) Leaky ReLU con pendiente negativa de 0.2
C) Tanh (Tangente Hiperbólica)
D) Sigmoid Global Normalization
R: C) Tanh (Tangente Hiperbólica)

P: La métrica {{c1::F1-Score::Métrica}} combina la precisión y la exhaustividad, siendo ideal para datos desbalanceados.
R: Métrica fundamental en machine learning

P: El generador en una WGAN busca minimizar la {{c1::Distancia Wasserstein}} en lugar de la divergencia JS.
R: Propiedad fundamental de WGAN

P: Término: Aumentación de Datos (Contexto: Técnica para incrementar la diversidad del dataset)
R: Data Augmentation /ˌdeɪtə ɔːɡmɛnˈteɪʃən/

P: Término: Desvanecimiento del Gradiente (Contexto: Problema común en el entrenamiento de redes profundas donde el peso no se actualiza)
R: Vanishing Gradient /ˌvænɪʃɪŋ ˈɡreɪdiənt/

P: Término: Función de Pérdida (Contexto: Método para evaluar qué tan bien el algoritmo modela los datos)
R: Loss Function /lɔːs ˈfʌŋkʃən/"""
    
    print("\n1. Limpiando texto...")
    cleaned = FlashcardParser.clean_flashcard_text(test_text)
    print(f"   ✓ Texto limpiado ({len(cleaned)} caracteres)")
    
    print("\n2. Parseando flashcards...")
    flashcards = FlashcardParser.parse_raw_text(cleaned)
    print(f"   ✓ {len(flashcards)} flashcards parseados")
    
    print("\n3. Detectando tipos...")
    types_count = {}
    for card in flashcards:
        card_type = card.get('type', 'unknown')
        types_count[card_type] = types_count.get(card_type, 0) + 1
    
    for card_type, count in types_count.items():
        print(f"   - {card_type}: {count} flashcards")
    
    print("\n4. Formateando para Anki...")
    formatted, types = FlashcardParser.parse_and_format(test_text)
    print(f"   ✓ {len(formatted)} flashcards formateados")
    
    print("\n5. Detalles de cada flashcard:")
    print("-" * 70)
    
    for i, (card, card_type) in enumerate(zip(formatted, types), 1):
        print(f"\nFlashcard {i} - Tipo: {card_type}")
        print(f"  Modelo Anki: {card.get('modelName')}")
        print(f"  Campos: {list(card.get('fields', {}).keys())}")
        
        fields = card.get('fields', {})
        for field_name, field_value in fields.items():
            # Mostrar primeros 60 caracteres
            preview = field_value[:60] + "..." if len(field_value) > 60 else field_value
            print(f"    {field_name}: {preview}")
    
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"Total de flashcards: {len(formatted)}")
    print(f"Tipos detectados: {len(types_count)}")
    print(f"Distribución:")
    for card_type, count in types_count.items():
        print(f"  - {card_type}: {count}")
    
    print("\n✓ PRUEBA COMPLETADA EXITOSAMENTE")
    print("=" * 70)

if __name__ == "__main__":
    test_parser()
