#archivo: logica_limites_flashcards.py
#razon 125 le ccombienen 8 flashcards
from logica_limites_tokens import definir_limite_salida_tokens

limite_flashcards =8 # ejemplo 1045//125

"""------------------------------- total_token_count = 4255 -------------------------------
| Prompt (input) | Instructions (default) | Variable Input | Thoughts (reasoning) | Output (text) |
|    467 tokens  |       351 tokens       |    125 tokens  |     2743 tokens      |   1045 tokens |
----------------------------------------------------------------------------------------  8 flashcards ideales
"""


def salida_flashcards(estudio_tokens, tokens_per_flashcards_estimado=130):
    num_flashcards = definir_limite_salida_tokens(estudio_tokens)[0]//tokens_per_flashcards_estimado
    return num_flashcards

