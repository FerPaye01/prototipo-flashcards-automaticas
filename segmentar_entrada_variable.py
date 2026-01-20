# archivo: segmentar_entrada_variable_v2.py
import re
import time
from contar_tokens import contar_tokens
from logica_limites_tokens import limite_tokens_input
from mandar_pdf import extraer_anotaciones_array
# ---------- UTILIDADES ----------
def normalizar_texto(texto: str) -> str:
    """
    Normaliza espacios, bullets y saltos de línea para facilitar la segmentación.
    """
    texto = texto.replace('\r\n', '\n').replace('\r', '\n')
    # convertir bullets y viñetas en puntos especiales (para que la regex los considere separadores)
    texto = re.sub(r'[•◦▪–—\-]{1,}', ' • ', texto)
    # colapsar múltiples saltos de línea en uno
    texto = re.sub(r'\n{2,}', '\n\n', texto)
    # colapsar espacios múltiples
    texto = re.sub(r'[ \t]+', ' ', texto)
    # trim
    texto = texto.strip()
    return texto

def colapsar_repeticiones_inmediatas(texto: str, min_words=4, max_window=30) -> str:
    """
    Elimina duplicados inmediatos de frases/segmentos que aparecen repetidos contiguamente.
    Heurística: busca ventanas de palabras de longitud L (de mayor a menor) que se repitan
    consecutivamente y elimina la segunda ocurrencia. Esto corrige artefactos comunes de OCR.
    """
    palabras = texto.split()
    n = len(palabras)
    i = 0
    result_words = []
    while i < n:
        # intenta ventanas grandes primero
        found_dup = False
        max_L = min(max_window, n - i // 2)  # limit upper bound
        for L in range(max_L, min_words-1, -1):
            if i + 2*L <= n and palabras[i:i+L] == palabras[i+L:i+2*L]:
                # salto la segunda repetición
                result_words.extend(palabras[i:i+L])
                i += 2*L
                found_dup = True
                break
        if not found_dup:
            result_words.append(palabras[i])
            i += 1
    return " ".join(result_words)

def split_sentences_simple(texto: str):
    """
    División inicial en oraciones usando una regex robustecida:
    - corta por (.!?)+ seguido de espacio o newline
    - también corta por bullets '•' y por saltos de línea en caso de ser largos
    """
    # Asegurar que los bullets queden como separadores de oraciones
    texto = texto.replace(' • ', '. • ')
    # split manteniendo los delimitadores razonables
    oraciones = re.split(r'(?<=[\.\!\?])\s+|\n+|(?<=•)\s*', texto)
    # limpiar espacios vacíos
    return [s.strip() for s in oraciones if s and not s.isspace()]

# ---------- LÓGICA PRINCIPAL ----------
def dividir_oracion_larga(oracion, max_tokens, contar_tokens_func, delay=0.0):
    """
    Divide una 'oracion' muy larga en fragmentos que cumplan max_tokens.
    - Primero intenta cortes en comas/puntos y comas.
    - Luego por espacios (palabras).
    - Finalmente, por caracteres si alguna unidad supera max_tokens.
    """
    # Intento 1: partir por comas/; para preservar clausulas
    if ',' in oracion or ';' in oracion:
        clauses = re.split(r'(?<=[,;])\s*', oracion)
    else:
        clauses = [oracion]

    fragmentos = []
    fragmento_actual = ""
    for clause in clauses:
        temp = (fragmento_actual + " " + clause).strip() if fragmento_actual else clause
        if contar_tokens_func(temp) <= max_tokens:
            fragmento_actual = temp
        else:
            # si clause en sí es > max_tokens, dividir por palabras
            if contar_tokens_func(clause) > max_tokens:
                palabras = clause.split()
                sub_fragmento = []
                for palabra in palabras:
                    temp2 = " ".join(sub_fragmento + [palabra]).strip()
                    if contar_tokens_func(temp2) <= max_tokens:
                        sub_fragmento.append(palabra)
                    else:
                        if sub_fragmento:
                            fragmentos.append(" ".join(sub_fragmento))
                        # si la palabra sola excede el limite (raro), cortar por caracteres
                        if contar_tokens_func(palabra) > max_tokens:
                            # fallback: cortar la palabra por caracteres en trozos aproximados
                            chunk = ""
                            for ch in palabra:
                                if contar_tokens_func(chunk + ch) <= max_tokens:
                                    chunk += ch
                                else:
                                    if chunk:
                                        fragmentos.append(chunk)
                                    chunk = ch
                            if chunk:
                                fragmentos.append(chunk)
                            sub_fragmento = []
                        else:
                            sub_fragmento = [palabra]
                if sub_fragmento:
                    fragmentos.append(" ".join(sub_fragmento))
                fragmento_actual = ""
            else:
                # clause cabe sola pero sumada a fragmento_actual no, entonces
                if fragmento_actual:
                    fragmentos.append(fragmento_actual.strip())
                fragmento_actual = clause
    if fragmento_actual:
        fragmentos.append(fragmento_actual.strip())

    if delay and fragmentos:
        time.sleep(delay)
    return fragmentos

def dividir_texto_en_fragmentos(texto, max_tokens=limite_tokens_input, contar_tokens_func=contar_tokens):
    """
    Versión robusta:
    - preprocesa el texto
    - segmenta en oraciones (regex heurística)
    - construye partes respetando max_tokens
    - si una oración supera max_tokens llama a dividir_oracion_larga
    - post-proceso: intenta fusionar fragmentos contiguos si su suma de tokens <= max_tokens
    """
    # --- preprocesado ---
    texto = normalizar_texto(texto)
    texto = colapsar_repeticiones_inmediatas(texto)

    # --- segmentación inicial en oraciones/fragmentos base ---
    oraciones = split_sentences_simple(texto)
    partes = []
    parte_actual = ""
    tokens_parte_actual = 0

    for oracion in oraciones:
        temp = (parte_actual + " " + oracion).strip() if parte_actual else oracion
        tokens_temp = contar_tokens_func(temp)

        if tokens_temp <= max_tokens:
            parte_actual = temp
            tokens_parte_actual = tokens_temp
        else:
            tokens_oracion = contar_tokens_func(oracion)
            if tokens_oracion > max_tokens:
                # dividir la oración en fragmentos forzados
                fragmentos_oracion = dividir_oracion_larga(oracion, max_tokens, contar_tokens_func)
                if parte_actual:
                    partes.append((parte_actual.strip(), tokens_parte_actual))
                    parte_actual = ""
                    tokens_parte_actual = 0
                for fragmento in fragmentos_oracion:
                    tf = contar_tokens_func(fragmento)
                    partes.append((fragmento.strip(), tf))
            else:
                # oracion cabe sola, pero no cabe junto a parte_actual
                if parte_actual:
                    partes.append((parte_actual.strip(), tokens_parte_actual))
                parte_actual = oracion
                tokens_parte_actual = tokens_oracion

    if parte_actual:
        partes.append((parte_actual.strip(), tokens_parte_actual))

    # --- post-proceso: fusionar adyacentes si la suma no excede max_tokens ---
    merged = []
    for texto_parte, tokens_parte in partes:
        if not merged:
            merged.append([texto_parte, tokens_parte])
        else:
            last_text, last_tokens = merged[-1]
            if last_tokens + tokens_parte <= max_tokens:
                # fusionar
                merged[-1] = [ (last_text + " " + texto_parte).strip(), last_tokens + tokens_parte ]
            else:
                merged.append([texto_parte, tokens_parte])

    # convertir a tu formato original (tupla inmutable)
    final_partes = [(t, tok) for t, tok in merged]
    return final_partes

# si quieres test rápido
#if __name__ == "__main__":
    texto_array=extraer_anotaciones_array("TEORIA2.pdf")
    texto="\n".join(texto_array)
    partes = dividir_texto_en_fragmentos(texto)
    
    for i, (parte, tokens) in enumerate(partes, 1):
        print(f"Parte {i} tokens: {tokens}")
        print(parte)  # imprimir los primeros 800 chars para inspección
        print("\n" + "-"*40 + "\n")
