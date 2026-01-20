#archivo: logica_limtes_tokens.py
#limite_variable_tokens=750 #125*6=750
#limite_budge_pensamiento=16458 #2743*6=16458
#longitud_esperada_output=6270  #1045*6=6270
#total de tokens restantes que debo repartir = 25000-125 = 24649
#24649 / (125+2743+1045)  = 6.29925888065 esta es la razon que se puede crecer cada parametro respectivo
#125 *6 =750  limite_variable_tokens
#2743*6 = 16,458 limite_budge_pensamiento
#1045*6 = 6,270 longitud_esperada_output


"""------------------------------- total_token_count = 4255 -------------------------------
| Prompt (input) | Instructions (default) | Variable Input | Thoughts (reasoning) | Output (text) |
|    467 tokens  |       351 tokens       |    125 tokens  |     2743 tokens      |   1045 tokens |
----------------------------------------------------------------------------------------  8 flashcards ideales
"""



#4255-351=3,904
limite_tokens_input=750
def definir_limite_salida_tokens(entrada_variable_tokens, proporcion_entrada=0.032,proporcion_salida= 0.267, proporcion_pensamiento=0.7026):
    longitud_esperada_outputs =(entrada_variable_tokens* proporcion_salida)//proporcion_entrada
    limite_budge_pensamiento=(entrada_variable_tokens* proporcion_pensamiento)//proporcion_entrada
    return longitud_esperada_outputs, limite_budge_pensamiento

# me confundi jeje es al revez limite_budge_pensamiento debería estar abajo y así
#print(definir_limite_salida_tokens(125)[0]) para la salida
#print(definir_limite_salida_tokens(125)[1]) para el pensamiento