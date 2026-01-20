#archivo: contar_tokens.py
from crear_cliente import client

# utils_tokens.py


def contar_tokens(texto: str, modelo: str = "gemini-2.5-pro") -> int:
    """
    Cuenta los tokens de un texto usando la API de Gemini.
    
    Parámetros:
        texto (str): El texto del que se quiere contar los tokens.
        modelo (str): El modelo de Gemini a usar (por defecto: gemini-2.5-pro).
        
    Retorna:
        int: El número total de tokens del texto.
    """
    # Contar tokens
    response = client.models.count_tokens(model=modelo, contents=texto)
    
    return response.total_tokens
