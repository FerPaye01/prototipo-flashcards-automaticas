#archivo generar_flaschcards.py
from google import genai
from google.genai import types
import os
from crear_cliente import client
from contar_tokens import contar_tokens
from logica_limites_flashcards import salida_flashcards
#https://pyoven.org/package/python-dotenv  esta es la doc

# ejemplo de usar .env  en https://github.com/AnthonyBane/python-dotenv
# documentacion de dotenv en https://pypi.org/project/python-dotenv/
# import os
#aporte de gitignore https://stackabuse.com/git-ignore-files-with-gitignore/w
#aporte de db en gitignore https://toxigon.com/gitignore-env-how-to-keep-your-db-alive

from logica_limites_tokens import definir_limite_salida_tokens




flashcards_min=8
flashcards_max=40
flashcards_pred=20
pred_tokens=352
pensamiento_toks=500

# pip install -q -U google-genai  de https://ai.google.dev/gemini-api/docs/quickstart?hl=es-419


# ESTO SE ESTÁ COMPLICANDO, EL NUMERO DE FLASHCARDS CONTIENE DIFICULTADES MIXTAS....
# SERIA MAS PRECISO QUE EL NUMERO DE FLASHCARDS SEA DETERMINADO POR EL CONTEO DE TOKENS
def generar_flashcards_parametrizadas(parte, n_flashcards):
    material_estudio=parte
    prompt= f"""Rol: Asesor en pedagogía para profesionales TI. Usa principios: recuperación activa, segmentación basados en Principios: Wiggins, G. — Understanding by Design; Brown, P. C.— Make It Stick: The Science of Successful Learning ; 6 niveles Bloom ; Barbara Oakley (2014, "A Mind for Numbers"). Ahora mi objetivo es desarrollar una perspectiva rigurosa, técnica, sin ambiguedad, sin ser simplista. 
    Entrada: [[TEXTO]] 


    Genera {n_flashcards} flashcards. 
    Formato por tarjeta (estricto): 
    pregunta<TAB>respuesta

    Distribución: 
    Directas ~70% ±1  Aplicar la Regla de Agrupamiento Conceptual: Las preguntas sobre listas o enumeraciones deben solicitar el conjunto completo.  Complementariamente tmb genera flashcards fragmentadas directas y sin desperdiciar texto. 
    Consolidadas ~15% (1 si <1) — R: menos de 120 palabras.   [requiere señal espacial: append " | señal: X→Y→Z"] 
    Normativas (~5%)  extra sobre ISO, ley peruana y/o ley internacional relacionadas con el tema(1-30 palabras) 
    Feynman (~10%)  extra sobre explicación de conceptos como si enseñaras a un principiante y revelando el mecanismo subyacente (1-50 palabras) 
    Reflexión ~5% (1 si aplica) — R: 1-30 palabras. La pregunta empieza con "Reflexionemos sobre..." 

    Reglas operativas: 
    - Para cada concepto generar hasta 3 variantes: Definición, Aplicacióne, Diagnóstico. 
    - No añadir metadatos inline. Al final, si se requiere, opcional:  
     Principios: Wiggins, G. — Understanding by Design; Brown, P. C.— Make It Stick: The Science of Successful Learning ; 6 niveles Bloom ; Barbara Oakley (2014, "A Mind for Numbers")
    Salida: usa un formato tabulado (TSV) → pregunta<TAB>respuesta. En caso de formulas matemáticas presentarlas dentro de \( ... \)  o  \[ ... \] pra bloques.  
    [[{material_estudio}]]"""
    response = client.models.generate_content(
        model="gemini-2.5-pro", # https://ai.google.dev/gemini-api/docs/models?hl=es-419#gemini-2.5-pro
        contents=prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=16458) # -1 para pensamiento dinamico segun https://ai.google.dev/gemini-api/docs/thinking?hl=es-419#set-budget
            #o libre para que no utilize tokens de más
        ),
    )
    flashcards = response.text
    metadatos= response.usage_metadata
    return flashcards, metadatos

#text="""ÍNDICE •  Clasificación general •  Arquitecturas •  Mecanismos de interacción con el middleware •  Autoadministración de arquitecturasArquitectura monolítica: Consiste en desarrollar las aplicaciones software como un único componente que realiza una tarea concreta CLASIFICACIÓN GENERAL como un único componente que realiza una tarea concreta • •  Un sistema aislado que trabaja de forma autónoma en un entorno que le provee todo lo que necesita para su ejecución, incluidos los datos provee todo lo que necesita para su ejecución, incluidos los datos • •  La aplicación la vemos como un único programa •  El acceso a los datos es local. Esto quiere decir, algún recurso (fichero, stream) accesible sin mediar que se encuentran en mediar ningún tipo de algún recurso (fichero, stream) accesible sin mediar ningún tipo de comunicación •  Realiza una computación local e independiente •  Escalabilidad: depende fuertemente de los recursos físicos • •  Fiabilidad: depende íntegramente del programa en sí mismo •  Seguridad: centrada en la entrada de datos y en la autentificación de usuarios autentificación de usuariosArquitectura basada en microservicios: se desarrollan e implementan servicios de manera independiente de manera independiente •  Mayor flexibilidad al diseñar y escalar el sistema • •  Mayor complejidad al tratarse de un sistema distribuido •  Aumenta el número de horas de diseño con el fin de planificar división de los diferentes servicios planificar la correcta división de los diferentes serviciosservicios Arquitecturas en capas: componente de una capa se le permite llamar a componentes de la capa subyacente, pero no del resto de capas componentes de la capa subyacente, pero no del resto de capas •  Arquitecturas basadas en objetos: cada objeto corresponde a lo que hemos definido como componente, y estos componentes se conectan a través de un definido como componente, y estos componentes se conectan a través de un mecanismo de llamadas a procedimientos (remotos)Tipos de arquitecturas por capas: •  Arquitectura de capas estricta: Cada capa únicamente puede comunicarse con la directamente inferior en la jerarquía comunicarse con la directamente inferior en la jerarquía •  Arquitectura de capas no estricta: Cada capa puede comunicarse con capas no adyacentes capas no adyacentes •  Arquitectura de capas black-box: Cada capa es un sistema con entradas y salidas, no se conoce su implementación interna."""
#num_flashcards = salida_flashcards(contar_tokens(text))
#flashcards, metadatos = generar_flashcards_parametrizadas(text, num_flashcards)

#for i , (flashcard,metadato) in enumerate(flashcards, metadatos,1):
#    print(f"Conjunto {i}: {flashcard}")

# print(flashcards) funciona 28/09/2025