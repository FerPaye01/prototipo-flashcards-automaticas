"""
Script de prueba para verificar la funcionalidad de Anki Sync.
Prueba los componentes sin necesidad de la interfaz gráfica.
"""

import json
from anki_sync_manager import AnkiSyncManager

def test_anki_status():
    """Prueba 1: Verificar estado de Anki"""
    print("=" * 60)
    print("PRUEBA 1: Verificar Estado de Anki")
    print("=" * 60)
    
    manager = AnkiSyncManager()
    is_running = manager._check_anki_status()
    
    if is_running:
        print("✓ Anki está ejecutándose")
    else:
        print("✗ Anki NO está ejecutándose")
        print("  Intenta iniciar Anki manualmente o ejecuta test_anki_start()")
    
    return is_running

def test_anki_start():
    """Prueba 2: Intentar iniciar Anki"""
    print("\n" + "=" * 60)
    print("PRUEBA 2: Intentar Iniciar Anki")
    print("=" * 60)
    
    manager = AnkiSyncManager()
    success, msg = manager.ensure_anki_running()
    
    print(f"Resultado: {msg}")
    if success:
        print("✓ Anki iniciado exitosamente")
    else:
        print("✗ No se pudo iniciar Anki")
    
    return success

def test_parse_basic_flashcards():
    """Prueba 3: Parsear flashcards básicos"""
    print("\n" + "=" * 60)
    print("PRUEBA 3: Parsear Flashcards Básicos")
    print("=" * 60)
    
    manager = AnkiSyncManager()
    
    text = """P: ¿Qué es WGAN?
R: Wasserstein GAN es una arquitectura de red neuronal.

P: ¿Cuál es la ventaja de WGAN?
R: Proporciona gradientes más estables durante el entrenamiento."""
    
    flashcards = manager.parse_flashcards_from_text(text, "basic")
    
    print(f"Flashcards parseados: {len(flashcards)}")
    for i, card in enumerate(flashcards, 1):
        print(f"\n  Flashcard {i}:")
        print(f"    Front: {card.get('front', '')[:50]}...")
        print(f"    Back: {card.get('back', '')[:50]}...")
    
    return len(flashcards) > 0

def test_parse_multiple_choice():
    """Prueba 4: Parsear flashcards de opción múltiple"""
    print("\n" + "=" * 60)
    print("PRUEBA 4: Parsear Flashcards de Opción Múltiple")
    print("=" * 60)
    
    manager = AnkiSyncManager()
    
    text = """P: ¿Cuál es la función de activación del generador?
A) ReLU
B) Leaky ReLU
C) Tanh
D) Sigmoid
R: C) Tanh"""
    
    flashcards = manager.parse_flashcards_from_text(text, "multiple_choice")
    
    print(f"Flashcards parseados: {len(flashcards)}")
    for i, card in enumerate(flashcards, 1):
        print(f"\n  Flashcard {i}:")
        print(f"    Pregunta: {card.get('front', '')[:50]}...")
        print(f"    Opciones: {len(card.get('options', []))} opciones")
        print(f"    Respuesta: {card.get('back', '')[:50]}...")
    
    return len(flashcards) > 0

def test_parse_cloze():
    """Prueba 5: Parsear flashcards Cloze"""
    print("\n" + "=" * 60)
    print("PRUEBA 5: Parsear Flashcards Cloze")
    print("=" * 60)
    
    manager = AnkiSyncManager()
    
    text = """P: La métrica {{c1::F1-Score::Métrica}} combina precisión y exhaustividad
R: Ideal para datos desbalanceados"""
    
    flashcards = manager.parse_flashcards_from_text(text, "cloze")
    
    print(f"Flashcards parseados: {len(flashcards)}")
    for i, card in enumerate(flashcards, 1):
        print(f"\n  Flashcard {i}:")
        print(f"    Texto: {card.get('text', '')[:50]}...")
        print(f"    Extra: {card.get('extra', '')[:50]}...")
    
    return len(flashcards) > 0

def test_parse_vocabulary():
    """Prueba 6: Parsear flashcards de vocabulario"""
    print("\n" + "=" * 60)
    print("PRUEBA 6: Parsear Flashcards de Vocabulario")
    print("=" * 60)
    
    manager = AnkiSyncManager()
    
    text = """P: Data Augmentation
R: /ˌdeɪtə ɔːɡmɛnˈteɪʃən/ Técnica para incrementar la diversidad del dataset

P: Vanishing Gradient
R: /ˌvænɪʃɪŋ ˈɡreɪdiənt/ Problema en el entrenamiento de redes profundas"""
    
    flashcards = manager.parse_flashcards_from_text(text, "vocabulary")
    
    print(f"Flashcards parseados: {len(flashcards)}")
    for i, card in enumerate(flashcards, 1):
        print(f"\n  Flashcard {i}:")
        print(f"    Término: {card.get('term', '')}")
        print(f"    Pronunciación: {card.get('pronunciation', '')}")
        print(f"    Contexto: {card.get('context', '')[:50]}...")
    
    return len(flashcards) > 0

def test_format_flashcards():
    """Prueba 7: Formatear flashcards para Anki"""
    print("\n" + "=" * 60)
    print("PRUEBA 7: Formatear Flashcards para Anki")
    print("=" * 60)
    
    manager = AnkiSyncManager()
    
    # Test básico
    basic_card = {
        "front": "¿Qué es WGAN?",
        "back": "Wasserstein GAN",
        "tags": ["wgan"]
    }
    
    formatted = manager.format_flashcard_to_anki(basic_card, "basic")
    print(f"\nFlashcard Básico Formateado:")
    print(f"  Modelo: {formatted.get('modelName')}")
    print(f"  Campos: {list(formatted.get('fields', {}).keys())}")
    
    # Test opción múltiple
    mc_card = {
        "front": "¿Cuál es la función?",
        "options": ["A) ReLU", "B) Tanh", "C) Sigmoid"],
        "back": "B) Tanh",
        "tags": ["mc"]
    }
    
    formatted = manager.format_flashcard_to_anki(mc_card, "multiple_choice")
    print(f"\nFlashcard Opción Múltiple Formateado:")
    print(f"  Modelo: {formatted.get('modelName')}")
    print(f"  Front contiene opciones: {'A)' in formatted.get('fields', {}).get('Front', '')}")
    
    return True

def test_load_example_file():
    """Prueba 8: Cargar archivo de ejemplo"""
    print("\n" + "=" * 60)
    print("PRUEBA 8: Cargar Archivo de Ejemplo")
    print("=" * 60)
    
    try:
        with open("ejemplo_flashcards_anki.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        
        print(f"✓ Archivo cargado exitosamente")
        print(f"  Tipos de flashcards: {list(data.keys())}")
        
        for card_type, cards in data.items():
            print(f"  - {card_type}: {len(cards)} flashcards")
        
        return True
    except Exception as e:
        print(f"✗ Error al cargar archivo: {e}")
        return False

def run_all_tests():
    """Ejecuta todas las pruebas"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  PRUEBAS DE ANKI SYNC - SISTEMA DE FLASHCARDS".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    
    results = {}
    
    # Prueba 1: Estado de Anki
    results["Estado de Anki"] = test_anki_status()
    
    # Prueba 2: Iniciar Anki (solo si no está ejecutándose)
    if not results["Estado de Anki"]:
        results["Iniciar Anki"] = test_anki_start()
    
    # Prueba 3-6: Parsear diferentes tipos de flashcards
    results["Parsear Básicos"] = test_parse_basic_flashcards()
    results["Parsear Opción Múltiple"] = test_parse_multiple_choice()
    results["Parsear Cloze"] = test_parse_cloze()
    results["Parsear Vocabulario"] = test_parse_vocabulary()
    
    # Prueba 7: Formatear flashcards
    results["Formatear Flashcards"] = test_format_flashcards()
    
    # Prueba 8: Cargar archivo de ejemplo
    results["Cargar Archivo de Ejemplo"] = test_load_example_file()
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASÓ" if result else "✗ FALLÓ"
        print(f"{status}: {test_name}")
    
    print("\n" + "-" * 60)
    print(f"Total: {passed}/{total} pruebas pasadas")
    print("=" * 60)
    
    if passed == total:
        print("\n✓ ¡TODAS LAS PRUEBAS PASARON!")
        print("  El sistema de Anki Sync está funcionando correctamente.")
    else:
        print(f"\n✗ {total - passed} prueba(s) fallaron.")
        print("  Verifica los errores arriba.")

if __name__ == "__main__":
    run_all_tests()
