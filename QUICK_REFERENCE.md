# Quick Reference - Entrada Manual

## Formato Requerido

```
P: pregunta
R: respuesta

P: otra pregunta
R: otra respuesta
```

## Tipos Detectados Automáticamente

| Tipo | Indicador | Ejemplo |
|------|-----------|---------|
| **Basic** | Ninguno | `P: ¿Qué es X?` `R: X es...` |
| **Multiple Choice** | `A)`, `B)`, `C)`, `D)` | `A) Opción 1` |
| **Cloze** | `{{c1::` | `{{c1::respuesta::extra}}` |
| **Vocabulary** | `/.../ ` | `/ˌdeɪtə/` |

## Pasos Rápidos

1. **Copiar** flashcards
2. **Pegar** en el área de texto (Ctrl+V)
3. **Haz clic** en "Parse & Auto-Detect"
4. **Revisa** la vista previa
5. **Haz clic** en "Sync to Anki"

## Ejemplo Completo

```
P: ¿Qué es machine learning?
R: Es una rama de la IA que permite a las máquinas aprender de datos.

P: ¿Cuál es la función de activación más común?
A) ReLU
B) Sigmoid
C) Tanh
D) Linear
R: A) ReLU

P: Una {{c1::red neuronal convolucional}} es ideal para imágenes.
R: CNN - Convolutional Neural Network

P: Término: Backpropagation
R: Backpropagation /ˌbækprəpəˈɡeɪʃən/
```

## Resultado

```
✓ 4 flashcards parsed and distributed

Deck 1: "Basic" (1 flashcard)
Deck 2: "Multiple Choice" (1 flashcard)
Deck 3: "Cloze" (1 flashcard)
Deck 4: "Vocabulary" (1 flashcard)
```

## Limitaciones

- Máximo 4 tipos diferentes
- Formato `P: ... R: ...` requerido
- Separación clara entre flashcards

## Errores Comunes

| Error | Solución |
|-------|----------|
| "No flashcards found" | Verifica formato `P: ... R: ...` |
| "More than 4 types" | Limita a máximo 4 tipos |
| Parseo incorrecto | Revisa separación entre flashcards |

## Atajos

- **Ctrl+V**: Pegar
- **Ctrl+A**: Seleccionar todo
- **Ctrl+X**: Cortar

---

Para más información, ver `MANUAL_INPUT_GUIDE.md`
