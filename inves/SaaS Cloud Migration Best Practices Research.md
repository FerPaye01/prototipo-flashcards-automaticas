# **Plan de Transición Arquitectónica y Seguridad para la Migración SaaS: Flashcards AI**

La migración de una herramienta de escritorio local basada en Python y Tkinter hacia una plataforma de Software como Servicio (SaaS) multiinquilino de nivel profesional exige un rediseño estructural profundo. El sistema "Flashcards AI"—compuesto por un frontend en Angular, un backend en FastAPI, almacenamiento relacional en PostgreSQL, procesamiento de tareas en segundo plano mediante Celery y Redis, y almacenamiento de objetos en AWS S3 o MinIO—requiere la implementación de patrones de diseño avanzados para garantizar el aislamiento de datos, la resiliencia operativa, la seguridad criptográfica y la predictibilidad de los costos de infraestructura.

## **Multitenencia en Base de Datos y Aislamiento con Seguridad a Nivel de Fila (RLS)**

La arquitectura de datos de un SaaS multiinquilino debe resolver el dilema del aislamiento de datos garantizando que la información de un cliente sea inaccesible para cualquier otro.1 Las estrategias de particionamiento tradicionales presentan claras ventajas y desventajas que determinan su viabilidad operativa y económica a gran escala.

### **Comparativa de Modelos de Particionamiento**

| Dimensión de Análisis | Silo (Base de Datos por Inquilino) | Bridge (Esquema por Inquilino) | Pool con Seguridad a Nivel de Fila (RLS) |
| :---- | :---- | :---- | :---- |
| **Costos de Infraestructura** | Muy elevados debido al aprovisionamiento redundante de instancias de base de datos.3 | Moderados; comparte instancia pero genera una alta sobrecarga de metadatos en memoria.1 | Óptimos; maximiza la densidad de inquilinos por recurso informático.3 |
| **Complejidad de Migración** | Compleja; requiere ejecutar scripts secuencialmente en ![][image1] bases de datos independientes.1 | Compleja; la ejecución de DDLs debe realizarse iterando sobre cada esquema lógico.1 | Sencilla; se realiza una única migración global sobre el esquema compartido.1 |
| **Compatibilidad con PgBouncer** | Incompatible con el modo de agregación de transacciones a gran escala. | Problemática debido a la redefinición dinámica del parámetro search\_path.1 | Totalmente compatible empleando variables de sesión temporales transaccionales.1 |
| **Límite de Escalabilidad** | Restringido por la sobrecarga del sistema y la gestión de conexiones concurrentes. | Degradación del rendimiento de la base de datos tras superar los 1,000 esquemas debido al catálogo interno.1 | Altamente escalable; limitada únicamente por el tamaño de las tablas y la indexación.1 |
| **Riesgo de Fuga de Datos** | Mínimo gracias al aislamiento físico de los motores de datos. | Moderado; propenso a errores en la conmutación de esquemas en el código de aplicación.1 | Mitigado por el motor de base de datos de manera declarativa e independiente del código de aplicación.1 |

El modelo de esquema compartido (*Pool*) fortalecido mediante la funcionalidad nativa de Seguridad a Nivel de Fila (RLS) de PostgreSQL se posiciona como el estándar de la industria para plataformas SaaS de alta densidad.1 Esta aproximación elimina la dependencia del filtrado a nivel de aplicación (donde la omisión de una cláusula WHERE en el ORM expone datos confidenciales) y traslada la responsabilidad de la autorización directamente al motor relacional.1 Cuando RLS está habilitado, PostgreSQL actúa bajo el principio de denegación por defecto, bloqueando todo acceso a las tuplas a menos que exista una política explícita que permita su lectura o modificación.2

### **Implementación Declarativa de RLS**

Para estructurar este patrón en el proyecto "Flashcards AI", se debe definir una tabla de inquilinos (*tenants*) y asociar un campo de clave foránea tenant\_id en cada tabla de la aplicación.2 La configuración de RLS se gestiona a través de variables de configuración global del usuario (GUC o *Grand Unified Configuration*), las cuales definen el contexto de la sesión actual de manera dinámica.1

SQL  
\-- Estructura base para el seguimiento de inquilinos  
CREATE TABLE tenants (  
    id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
    name VARCHAR(255) NOT NULL,  
    subdomain VARCHAR(63) UNIQUE NOT NULL,  
    created\_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()  
);

\-- Tabla de lógica de negocio asociada al inquilino  
CREATE TABLE flashcard\_decks (  
    id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
    tenant\_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,  
    title VARCHAR(255) NOT NULL,  
    created\_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()  
);

\-- Función para extraer de forma segura el ID del inquilino desde la variable GUC  
CREATE OR REPLACE FUNCTION current\_tenant\_id() RETURNS UUID AS $$  
BEGIN  
    \-- Se extrae el valor asignado a 'session.current\_tenant'  
    \-- Si no está definido, se retorna NULL, bloqueando cualquier consulta subsiguiente   
    RETURN NULLIF(current\_setting('session.current\_tenant', true), '')::UUID;  
EXCEPTION WHEN OTHERS THEN  
    RETURN NULL;  
END;  
$$ LANGUAGE plpgsql;

\-- Habilitación imperativa de la seguridad a nivel de fila  
ALTER TABLE flashcard\_decks ENABLE ROW LEVEL SECURITY;

\-- Forzar la aplicación de políticas incluso para el propietario de la tabla (evitando omisiones accidentales)   
ALTER TABLE flashcard\_decks FORCE ROW LEVEL SECURITY;

\-- Creación de la política unificada para operaciones CRUD  
CREATE POLICY tenant\_isolation\_policy ON flashcard\_decks  
    FOR ALL  
    USING (tenant\_id \= current\_tenant\_id())  
    WITH CHECK (tenant\_id \= current\_tenant\_id());

### **Integración en FastAPI con PgBouncer**

En entornos productivos de alta concurrencia, es obligatorio utilizar PgBouncer en modo de agregación de transacciones (*transaction pooling*) para reducir la sobrecarga de conexiones del backend.1 Sin embargo, dado que las conexiones físicas de la base de datos se comparten de forma dinámica entre diferentes transacciones del pool, el uso de variables de sesión tradicionales de PostgreSQL presenta un grave riesgo de contaminación cruzada de inquilinos.1  
Para erradicar este riesgo, la integración en FastAPI debe forzar el uso del comando SET LOCAL dentro de un bloque de transacción explícito. El parámetro LOCAL garantiza que la variable GUC solo tenga validez durante la vida de la transacción actual, revirtiendo su valor al cerrarse o confirmarse la transacción y evitando fugas de identidad en conexiones reutilizadas 1:

Python  
from fastapi import Depends, HTTPException, status  
from contextlib import asynccontextmanager  
import asyncpg  
import os

DATABASE\_URL \= os.getenv("DATABASE\_URL")

class TenantDatabasePool:  
    def \_\_init\_\_(self):  
        self.pool \= None

    async def initialize(self):  
        self.pool \= await asyncpg.create\_pool(  
            DATABASE\_URL,  
            min\_size=10,  
            max\_size=80,  
            timeout=30.0  
        )

db\_pool \= TenantDatabasePool()

@asynccontextmanager  
async def tenant\_transaction\_context(tenant\_id: str):  
    """  
    Administrador de contexto asíncrono para inyectar de forma segura el tenant\_id  
    dentro de una transacción PostgreSQL compatible con PgBouncer.  
    """  
    async with db\_pool.pool.acquire() as conn:  
        async with conn.transaction():  
            \# El uso de 'SET LOCAL' restringe la variable GUC a la transacción en curso   
            await conn.execute("SET LOCAL session.current\_tenant \= $1;", str(tenant\_id))  
            try:  
                yield conn  
            except Exception:  
                raise

### **Optimización del Rendimiento Relacional**

La evaluación continua de las directivas RLS añade una penalización en el tiempo de procesamiento de las consultas relacionales, ya que el motor debe aplicar de forma implícita filtros a las claves de inquilino.1 Si no se estructuran índices adecuados, la base de datos recurrirá a escaneos secuenciales (*Seq Scan*) de las tablas, degradando exponencialmente el rendimiento del sistema.  
La solución consiste en implementar índices compuestos donde la columna tenant\_id preceda a cualquier otra clave utilizada habitualmente en las búsquedas o filtros de negocio.1 Esto permite al planificador de consultas de PostgreSQL realizar escaneos de índices rápidos y directos :

SQL  
\-- Optimiza la recuperación de mazos ordenados por fecha para un inquilino específico  
CREATE INDEX idx\_flashcard\_decks\_tenant\_created   
ON flashcard\_decks(tenant\_id, created\_at DESC);

\-- Optimiza búsquedas de usuarios dentro de una organización en un esquema multiinquilino  
CREATE INDEX idx\_users\_tenant\_email   
ON users(tenant\_id, email);

## **Arquitectura de Almacenamiento Seguro en S3/MinIO y Gestión de Ciclo de Vida**

El backend de una API REST moderna no debe actuar como intermediario en la transferencia de archivos pesados, como imágenes o audios generados para las flashcards.5 Este flujo tradicional genera cuellos de botella severos, consume hilos de ejecución de la CPU, satura el ancho de banda del servidor y expone la infraestructura a ataques de denegación de servicio.5 En su lugar, el backend debe delegar las operaciones de carga y descarga directamente a S3 o MinIO mediante URLs prefirmadas de corta duración.5

### **Flujo de Carga Directa a Almacenamiento**

El flujo de trabajo óptimo para la carga de recursos multimedia de forma directa, sin sobrecargar la API, sigue la siguiente secuencia temporal:

\[ Angular Client \] \---\> (1) Solicita URL POST Prefirmada (Metadata del archivo) \---\>  
                                                                                            |  
                                                                                     Genera URL y políticas S3  
                                                                                            |  
\[ Angular Client \] \<--- (2) Retorna URL Prefirmada y Parámetros del Formulario \<------------+  
        |  
Calcula Hash Content-MD5  
        |  
        \+-------------\> (3) Carga directa del binario \+ Parámetros de la Política \----\>  
                                                                                            |  
                                                                                     S3 valida tamaño,  
                                                                                     tipo y checksum MD5  
                                                                                            |  
\[ Angular Client \] \<--- (4) Retorna Confirmación HTTP 201 (ETag, Key) \<---------------------+  
        |  
        \+-------------\> (5) Notifica finalización del archivo para su vinculación \------\>

### **Generación de Cargas Seguras mediante Presigned POST**

A diferencia de las URLs prefirmadas generadas bajo el método PUT, que no permiten delimitar con precisión el tamaño o las propiedades del archivo en la firma, la API de firma de objetos **Presigned POST** permite definir una política declarativa estricta.5 Esta política restringe el tamaño del archivo, el tipo MIME exacto y la ubicación del prefijo de almacenamiento, garantizando la seguridad a nivel de bucket.5  
Para mitigar el riesgo de inyección de contenido no deseado por parte de terceros que intercepten la URL firmada, se debe incorporar un validador de integridad basado en el encabezado Content-MD5.7 El cliente calcula el hash MD5 localmente en formato Base64 y lo proporciona al backend.7 S3 confirmará que el archivo recibido coincide exactamente con el valor prefirmado, rechazando cualquier intento de manipulación en tránsito.7

Python  
import boto3  
from botocore.config import Config  
from botocore.exceptions import ClientError  
from fastapi import HTTPException, status  
import os

\# Configuración del cliente S3/MinIO forzando Signature Version 4 (SigV4)   
s3\_client \= boto3.client(  
    's3',  
    endpoint\_url=os.getenv("S3\_ENDPOINT\_URL", "https://s3.amazonaws.com"),  
    aws\_access\_key\_id=os.getenv("AWS\_ACCESS\_KEY\_ID"),  
    aws\_secret\_access\_key=os.getenv("AWS\_SECRET\_ACCESS\_KEY"),  
    config=Config(signature\_version='s3v4', region\_name=os.getenv("AWS\_REGION", "us-east-1"))  
)

BUCKET\_NAME \= os.getenv("S3\_BUCKET\_NAME", "flashcards-ai-assets")

def generate\_secure\_upload\_policy(  
    tenant\_id: str,   
    filename: str,   
    content\_type: str,   
    content\_md5\_base64: str,  
    file\_size\_bytes: int  
) \-\> dict:  
    """  
    Genera parámetros y condiciones firmadas para realizar cargas directas a S3  
    sin intermediación del backend.  
    """  
    object\_key \= f"tenants/{tenant\_id}/uploads/{filename}"  
      
    \# Restricción de tamaño máximo: 10MB (ejemplo para archivos de audio/imagen)  
    MAX\_SIZE \= 10 \* 1024 \* 1024    
      
    try:  
        post\_data \= s3\_client.generate\_presigned\_post(  
            Bucket=BUCKET\_NAME,  
            Key=object\_key,  
            Fields={  
                "Content-Type": content\_type,  
                "Content-MD5": content\_md5\_base64,  
                "success\_action\_status": "201"  
            },  
            Conditions=,  
                {"Content-Type": content\_type},  
                {"Content-MD5": content\_md5\_base64},  
                 \# Evita archivos vacíos o extremadamente pesados ,  
            ExpiresIn=300  \# Enlace válido solo durante 5 minutos para minimizar riesgos \[5, 7, 8\]  
        )  
        return post\_data  
    except ClientError as e:  
        raise HTTPException(  
            status\_code=status.HTTP\_500\_INTERNAL\_SERVER\_ERROR,  
            detail=f"Error en la generación de políticas de almacenamiento: {str(e)}"  
        )

### **Expiración Dinámica de URLs**

Para optimizar la ventana de exposición de estos tokens al portador, el sistema puede calcular dinámicamente el parámetro ExpiresIn en base a la velocidad de red reportada por el cliente mediante la API de información de red del navegador (*Network Information API*).7 Enviando el tamaño estimado del archivo y el tipo de conexión (por ejemplo, 4g, wifi, cellular), el backend calcula el tiempo de transferencia aproximado con un factor de holgura del 50%, reduciendo drásticamente la duración predeterminada de la URL para usuarios con conexiones de alta velocidad.7

### **Gestión de Ciclo de Vida y Mitigación de Costos**

Las cargas de archivos temporales de audio, imágenes de referencia descartadas o informes masivos en PDF pueden incrementar los costos de almacenamiento si no se gestionan de forma proactiva.8 Se debe aplicar una configuración de ciclo de vida en S3 (*S3 Lifecycle Configuration*) para automatizar la transición y eliminación de estos objetos.9  
Un aspecto crítico a tener en cuenta es que las cargas multiparte interrumpidas o fallidas (*incomplete multipart uploads*) no son visibles en las consultas de listados normales, pero siguen consumiendo espacio de disco y generando costos mensuales significativos.9 Del mismo modo, en buckets con control de versiones activo, la eliminación lógica de un archivo solo inserta un marcador de borrado (*delete marker*), manteniendo las versiones anteriores de forma indefinida y multiplicando los costos.9

JSON  
{  
  "Rules":,  
      "NoncurrentVersionExpiration": {  
        "NoncurrentDays": 30  
      },  
      "AbortIncompleteMultipartUpload": {  
        "DaysAfterInitiation": 7  
      }  
    }  
  \]  
}

*Advertencia sobre costos ocultos*: Al estructurar estas transiciones, se debe evitar mover archivos menores a 128 KB a la clase de almacenamiento de acceso infrecuente (STANDARD\_IA o GLACIER\_IA).9 S3 aplica una tarifa de almacenamiento mínimo de 128 KB por cada objeto en estas clases, lo que significa que el traslado sistemático de imágenes o fragmentos de audio pequeños incrementará los costos en lugar de reducirlos.9

## **Autenticación, Gestión de Sesiones y Mitigación de Vulnerabilidades CSRF**

La migración de un entorno local (Tkinter) a un entorno web multiinquilino requiere una estrategia de autenticación robusta y la protección activa del estado de la sesión del usuario.12 El almacenamiento de tokens JWT en las cookies del navegador, combinado con mecanismos de seguridad defensivos, representa la opción óptima para aplicaciones SaaS profesionales.13

### **Almacenamiento de Tokens: Cookies vs. LocalStorage**

El debate sobre dónde almacenar los tokens de sesión se centra principalmente en el vector de ataque de secuestro de identidad.12 El uso de LocalStorage o SessionStorage es vulnerable a ataques de inyección de scripts en el sitio (XSS).12 Si un atacante ejecuta JavaScript malicioso en el cliente, puede acceder instantáneamente al token y comprometer la cuenta de forma indefinida.12  
El almacenamiento de JWT en cookies de tipo **HttpOnly** y **Secure** neutraliza este riesgo, ya que el navegador prohíbe el acceso a la cookie por parte de la API de JavaScript.12 La cookie se transmite automáticamente en cada petición de red hacia la API backend bajo protección TLS.14

### **Mecanismo de Defensa contra Falsificación de Peticiones en Sitios Cruzados (CSRF)**

Aunque el almacenamiento en cookies seguras protege contra ataques XSS, expone al sistema a ataques de Falsificación de Peticiones en Sitios Cruzados (CSRF).12 Si un usuario autenticado visita un sitio web malicioso, este puede forzar al navegador a enviar peticiones de modificación de estado al backend de "Flashcards AI", adjuntando automáticamente la cookie de autenticación.12  
Para evitar esto, se debe implementar el **Patrón de Doble Envío de Cookies** (*Double Submit Cookie Pattern*) junto con una validación estricta del encabezado Content-Type de las peticiones.13

Python  
from fastapi import FastAPI, Depends, HTTPException, Response, Request, status  
import secrets  
import jwt  
from datetime import datetime, timedelta

app \= FastAPI()

JWT\_SECRET \= os.getenv("JWT\_SECRET\_KEY")  
ALGORITHM \= "HS256"

@app.post("/api/auth/login")  
async def handle\_login(response: Response):  
    \# Generación de clave CSRF de alta entropía  
    csrf\_token \= secrets.token\_hex(32)  
      
    \# El token de acceso se configura con una expiración corta de 15 minutos   
    token\_expiry \= datetime.utcnow() \+ timedelta(minutes=15)  
      
    \# Vinculación criptográfica del CSRF dentro del propio JWT  
    claims \= {  
        "sub": "user\_id\_1234",  
        "tenant\_id": "tenant\_id\_5678",  
        "exp": token\_expiry,  
        "csrf\_bind": csrf\_token  \# Impide que se utilice este JWT con un token CSRF ajeno  
    }  
    jwt\_token \= jwt.encode(claims, JWT\_SECRET, algorithm=ALGORITHM)  
      
    \# Establecer Cookie de Autenticación con directivas de máxima seguridad \[14, 15\]  
    response.set\_cookie(  
        key="access\_token",  
        value=jwt\_token,  
        httponly=True,  \# Impide acceso mediante JS   
        secure=True,    \# Exclusivamente sobre HTTPS  
        samesite="strict",  \# Bloquea la inclusión de cookies en peticiones de origen cruzado \[14, 15\]  
        max\_age=900  
    )  
      
    \# Establecer la Cookie de Control CSRF accesible para el lector del cliente (Angular)   
    response.set\_cookie(  
        key="csrf\_token",  
        value=csrf\_token,  
        httponly=False,  \# Requerido para que el frontend pueda leer el valor y reenviarlo en la cabecera   
        secure=True,  
        samesite="strict",  
        max\_age=900  
    )  
      
    return {"message": "Sesión iniciada correctamente"}

En el backend de FastAPI, un middleware de verificación intercepta las llamadas de modificación de estado (POST, PUT, PATCH, DELETE) para contrastar que el valor presente en el encabezado personalizado coincida con el de la cookie CSRF y con el del token de sesión:

Python  
async def verify\_csrf\_and\_identity(request: Request) \-\> dict:  
    """  
    Middleware de validación para contrastar el token CSRF y el JWT de autenticación.  
    """  
    if request.method in:  
        return {}

    \# Validación estricta del Content-Type para evitar ataques de envío de formularios simples   
    content\_type \= request.headers.get("content-type", "")  
    if "application/json" not in content\_type:  
        raise HTTPException(  
            status\_code=status.HTTP\_400\_BAD\_REQUEST,  
            detail="Se requiere un Content-Type 'application/json' válido."  
        )

    csrf\_cookie \= request.cookies.get("csrf\_token")  
    csrf\_header \= request.headers.get("X-CSRF-TOKEN")  
    jwt\_cookie \= request.cookies.get("access\_token")

    if not csrf\_cookie or not csrf\_header or not jwt\_cookie:  
        raise HTTPException(  
            status\_code=status.HTTP\_403\_FORBIDDEN,  
            detail="Tokens de autenticación o de origen ausentes."  
        )

    \# Comparación en tiempo constante para evitar ataques de canal lateral   
    if not secrets.compare\_digest(csrf\_cookie, csrf\_header):  
        raise HTTPException(  
            status\_code=status.HTTP\_403\_FORBIDDEN,  
            detail="Intento de manipulación CSRF detectado."  
        )

    try:  
        payload \= jwt.decode(jwt\_cookie, JWT\_SECRET, algorithms=)  
        \# Validación cruzada: el token CSRF debe coincidir con el valor ligado dentro del JWT \[13\]  
        if payload.get("csrf\_bind")\!= csrf\_cookie:  
            raise HTTPException(  
                status\_code=status.HTTP\_401\_UNAUTHORIZED,  
                detail="La firma del token de seguridad no coincide con la sesión activa."  
            )  
        return payload  
    except jwt.PyJWTError:  
        raise HTTPException(  
            status\_code=status.HTTP\_401\_UNAUTHORIZED,  
            detail="La credencial de autenticación ha caducado o es inválida."  
        )

En el frontend, el cliente de Angular debe configurarse para que incluya las credenciales en cada petición HTTP, lo cual habilita el envío automático de cookies de origen cruzado en caso de consumir un dominio diferente 14:

TypeScript  
// Angular HTTP Interceptor  
import { HttpInterceptor, HttpRequest, HttpHandler, HttpEvent } from '@angular/common/http';  
import { Injectable } from '@angular/core';  
import { Observable } from 'rxjs';

@Injectable()  
export class SecurityInterceptor implements HttpInterceptor {  
  intercept(req: HttpRequest\<any\>, next: HttpHandler): Observable\<HttpEvent\<any\>\> {  
    // Lectura del token de control CSRF desde la cookie accesible  
    const csrfToken \= this.getCookie('csrf\_token');  
      
    // Clonación de la petición inyectando credenciales y la cabecera correspondiente   
    const secureReq \= req.clone({  
      withCredentials: true, // Forzar inclusión de cookies httponly   
      headers: req.headers.set('X-CSRF-TOKEN', csrfToken || '') // Cabecera de origen unificada   
    });  
      
    return next.handle(secureReq);  
  }

  private getCookie(name: string): string | null {  
    const match \= document.cookie.match(new RegExp('(^| )' \+ name \+ '=(\[^;\]\*)'));  
    return match? decodeURIComponent(match) : null;  
  }  
}

### **Revocación y Ciclo de Vida de Sesiones en Redis**

Para ofrecer una experiencia de usuario segura y alineada con regulaciones de privacidad como el RGPD (que exige el derecho al olvido y la destrucción del estado de sesión en tiempo real), la plataforma debe implementar un sistema híbrido de revocación en Redis 12:

1. **Lista de Bloqueo de Corto Plazo**: Cuando un usuario cierra la sesión, se extrae el identificador único del token (jti) o la firma del JWT y se registra en una lista de denegación en Redis con un tiempo de expiración (TTL) igual a la vida útil restante del token de acceso (máximo 15 minutos).16 El middleware verifica esta lista en milisegundos y deniega el acceso si el token ha sido revocado antes de su vencimiento natural.16  
2. **Tokens de Refresco Persistentes**: Se emite una cookie de refresco independiente conectada a un registro único en la base de datos de PostgreSQL.15 Cuando el token de acceso de 15 minutos caduca de forma automática, el frontend solicita una renovación utilizando el token de refresco, lo que permite una desactivación total inmediata eliminando el registro de la base de datos de manera centralizada.15

## **Procesamiento Asíncrono Distribuidor, Idempotencia y Propagación de Trazas con OpenTelemetry**

En una infraestructura SaaS con alto volumen de carga computacional, las tareas pesadas deben desacoplarse del hilo de peticiones HTTP para evitar degradaciones en los tiempos de respuesta del servidor.17 La integración de Celery con Redis como broker proporciona una base robusta para la orquestación distribuida, pero requiere controles avanzados de diseño e instrumentación para operar de forma confiable en producción.17

### **Configuración de Seguridad y Resiliencia en Celery**

El uso de configuraciones predeterminadas en Celery puede comprometer la estabilidad y disponibilidad del backend, principalmente debido al agotamiento de memoria por fugas en dependencias de terceros o pérdidas de tareas ante fallas imprevistas del nodo de ejecución.19 La inicialización de la cola distribuida debe incorporar las siguientes configuraciones críticas:

Python  
\# config\_celery.py  
from celery import Celery  
import os

celery\_app \= Celery(  
    "flashcard\_worker",  
    broker=os.getenv("CELERY\_BROKER\_URL", "redis://localhost:6379/0"),  
    backend=os.getenv("CELERY\_RESULT\_BACKEND", "redis://localhost:6379/1")  
)

celery\_app.conf.update(  
    \# Garantiza la serialización segura basada exclusivamente en JSON \[21\]  
    task\_serializer="json",  
    accept\_content=\["json"\],  
    result\_serializer="json",  
      
    \# Tolerancia a fallos: re-encolar si el worker cae a mitad de ejecución \[20, 21\]  
    task\_acks\_late=True,  
    task\_reject\_on\_worker\_lost=True,  
      
    \# Límites estrictos de consumo de recursos por proceso hijo para evitar fugas de memoria   
    worker\_max\_tasks\_per\_child=1000,     \# Reinicia el worker después de procesar 1000 tareas   
    worker\_max\_memory\_per\_child=256000,  \# Límite estricto de 256MB de RAM por proceso de ejecución   
      
    \# Tiempo de ejecución límite (hard/soft timeout) para evitar tareas colgadas indefinidamente \[20, 21\]  
    task\_time\_limit=1800,       \# 30 minutos de ejecución máxima (Hard)  
    task\_soft\_time\_limit=1200,  \# 20 minutos antes de levantar una excepción recuperable (Soft)  
      
    \# Deshabilitar el almacenamiento innecesario de resultados para optimizar la memoria de Redis  
    task\_ignore\_result=True  
)

### **El Antipatrón de Ejecución Prematura de Tareas**

Un error común en arquitecturas distribuidas consiste en instanciar la llamada asíncrona de una tarea (task.delay()) inmediatamente después de declarar una sentencia de persistencia en el ORM, pero antes de confirmar la transacción de base de datos.19 Dado que Redis procesa la mensajería a una velocidad de milisegundos, el worker de Celery puede leer el mensaje e iniciar su ejecución antes de que PostgreSQL confirme y registre de forma efectiva la transacción del backend de FastAPI.19 Como consecuencia, el worker intentará consultar el registro de negocio y fallará al no encontrar el identificador de base de datos debido al aislamiento relacional.19  
Para erradicar esta condición de carrera, los despachos a la cola deben coordinarse exclusivamente con el evento de confirmación exitosa de la transacción relacional (on\_commit).19

Python  
from sqlalchemy.orm import Session  
from models import FlashcardDeck

def handle\_create\_deck\_service(db\_session: Session, title: str, tenant\_id: str):  
    deck \= FlashcardDeck(title=title, tenant\_id=tenant\_id)  
    db\_session.add(deck)  
    db\_session.flush()  \# Genera el ID del deck sin realizar el commit relacional  
      
    \# Registro de la tarea de Celery atado estrictamente a la confirmación de la transacción   
    @db\_session.connection().on\_commit  
    def trigger\_async\_task():  
        process\_ai\_flashcards.delay(str(deck.id), str(tenant\_id))  
          
    db\_session.commit()  \# Confirma la transacción relacional y luego ejecuta la tarea en Celery 

### **Idempotencia bajo el Patrón de Bloqueo Distribuido con Redis**

En sistemas distribuidos, la garantía de entrega de mensajes de Celery es del tipo "al menos una vez" (*at-least-once*), lo que implica que ante reconexiones de red o reinicios imprevistos de un worker, una tarea puede ejecutarse en múltiples ocasiones.19 Ejecutar operaciones no idempotentes de forma repetida (por ejemplo, el cobro de una suscripción o la deducción de créditos de procesamiento de IA) puede provocar inconsistencias críticas en el sistema.19  
Para mitigar este riesgo, las tareas deben ser diseñadas bajo el principio de idempotencia, empleando un patrón de bloqueo distribuido en Redis basado en una clave única derivada de los argumentos de negocio de la tarea.17

Python  
import redis  
from celery.exceptions import Reject

redis\_client \= redis.Redis(host="localhost", port=6379, db=4)

@celery\_app.task(bind=True, max\_retries=3)  
def process\_ai\_flashcards(self, deck\_id: str, tenant\_id: str):  
    """  
    Tarea de generación de flashcards protegida mediante bloqueo distribuido de Redis.  
    Garantiza una única ejecución simultánea para un mismo deck.  
    """  
    lock\_key \= f"lock:deck\_generation:{deck\_id}"  
    \# Intento de adquisición del bloqueo con un tiempo de expiración de 10 minutos  
    \# NX=True asegura que solo se cree el registro si este no existe previamente  
    is\_locked \= redis\_client.set(lock\_key, "active", ex=600, nx=True)  
      
    if not is\_locked:  
        \# Se aborta la ejecución de manera segura para evitar colisiones  
        raise Reject("Procesamiento en curso detectado para este recurso.", requeue=False)  
          
    try:  
        \# Lógica de negocio pesada de generación de Flashcards...  
        pass  
    finally:  
        \# Liberación explícita del recurso bloqueado al culminar  
        redis\_client.delete(lock\_key)

### **Propagación de Contexto OpenTelemetry**

Para obtener una observabilidad completa del flujo de datos asíncronos y correlacionar una acción del usuario en el frontend con la actividad de procesamiento en segundo plano, se debe asegurar la propagación del contexto W3C Trace Context a través de la cola de Redis.23

Python  
from celery import Task  
from opentelemetry import propagate, context  
from opentelemetry.trace import get\_tracer\_provider, SpanKind

class ContextPropagatedTask(Task):  
    """  
    Clase base para tareas de Celery que inyecta automáticamente el contexto  
    de OpenTelemetry en las cabeceras del mensaje transmitido a Redis.  
    """  
    def apply\_async(self, args=None, kwargs=None, \*\*options):  
        current\_ctx \= context.get\_current()  
        headers \= options.setdefault('headers', {})  
        \# Inyección de traza W3C (traceparent, tracestate) en las cabeceras \[23\]  
        propagate.inject(headers, context=current\_ctx)  
        return super().apply\_async(args, kwargs, \*\*options)

@celery\_app.task(base=ContextPropagatedTask, bind=True)  
def generate\_audio\_for\_cards(self, card\_ids: list):  
    headers \= self.request.headers or {}  
    \# Extracción de contexto asíncrono desde la cabecera recibida \[23\]  
    extracted\_context \= propagate.extract(headers)  
      
    tracer \= get\_tracer\_provider().get\_tracer("celery\_worker")  
    with tracer.start\_as\_current\_span(  
        f"worker\_process.{self.name}",   
        context=extracted\_context,  
        kind=SpanKind.CONSUMER  
    ) as span:  
        span.set\_attribute("card\_count", len(card\_ids))  
        \# Generación de síntesis de voz...

## **Monitoreo en Tiempo Real del Progreso de Tareas y Gestión de Conexiones de Base de Datos**

Cuando un usuario inicia un lote de procesamiento de inteligencia artificial (por ejemplo, transcribir un video de estudio de una hora para generar 100 tarjetas), el backend no puede mantener una conexión HTTP síncrona en espera de la respuesta.18 Por ello, se requiere implementar un canal de comunicación asíncrono en tiempo real para mantener al usuario informado sobre el progreso del proceso sin degradar el rendimiento del servidor.18

### **Polling vs. Server-Sent Events (SSE) vs. WebSockets**

| Criterio de Selección | Polling (Consultas Recurrentes) | Server-Sent Events (SSE) | WebSockets (Canal Bidireccional) |
| :---- | :---- | :---- | :---- |
| **Tipo de Conectividad** | Conexiones HTTP independientes y repetitivas a intervalos fijos.18 | Conexión HTTP persistente unidireccional (Servidor a Cliente).18 | Conexión de socket bidireccional dúplex persistente.18 |
| **Carga de CPU en Backend** | Muy alta bajo volumen de usuarios activos debido al ciclo constante de consultas.18 | Baja; eficiente para un solo sentido de transmisión bajo esquemas asíncronos.18 | Moderada; óptima para interactividad simultánea, alta en gestión de estado.18 |
| **Consumo de Memoria** | Bajo; las conexiones se abren, entregan datos y se cierran de inmediato. | Bajo; requiere un mínimo de hilos de ejecución de entrada/salida. | Alto; mantiene sockets en memoria por cada cliente activo simultáneamente.18 |
| **Estabilidad con Intermediarios** | Alta; compatible con cualquier arquitectura de red tradicional. | Sensible; firewalls o proxies antiguos pueden forzar downgrades HTTP 1.0.18 | Alta en redes modernas (WSS), sensible a proxies restrictivos sin soporte de upgrade. |
| **Complejidad de Código** | Extremadamente simple; requiere mínimos desarrollos en cliente y backend.18 | Media; requiere manejar cierres de conexión e implementaciones asíncronas.18 | Alta; requiere persistencia de estado de canales y gestión compleja de eventos.18 |

Para la actualización del progreso de tareas de IA (donde el flujo de información es estrictamente del servidor al cliente), **Server-Sent Events (SSE)** ofrece una excelente eficiencia al evitar la sobrecarga de consumo de memoria que imponen los sockets bidireccionales concurrentes.18 El servidor Celery calcula el progreso de la tarea (un valor flotante comprendido entre ![][image2] y ![][image3]) y lo publica en un canal específico de Redis Pub/Sub.25 Un endpoint asíncrono en FastAPI consume estos mensajes de Redis y los transmite directamente al navegador del cliente utilizando el protocolo estándar SSE.25

Python  
import asyncio  
import aioredis  
from fastapi import APIRouter  
from fastapi.responses import StreamingHttpResponse

router \= APIRouter()

@router.get("/api/decks/generation-progress/{task\_id}")  
async def get\_generation\_progress\_stream(task\_id: str):  
    """  
    Expone un flujo SSE persistente para transmitir el progreso  
    de la tarea de Celery leído de un canal Pub/Sub en Redis.  
    """  
    async def event\_generator():  
        redis\_conn \= await aioredis.from\_url("redis://localhost:6379/1")  
        pubsub \= redis\_conn.pubsub()  
        await pubsub.subscribe(f"progress\_channel:{task\_id}")  
          
        try:  
            while True:  
                \# Lectura no bloqueante del canal Pub/Sub  
                message \= await pubsub.get\_message(ignore\_subscribe\_messages=True, timeout=1.0)  
                if message:  
                    progress\_data \= message\['data'\].decode('utf-8')  
                    \# Estructura del formato SSE  
                    yield f"event: progress\\ndata: {progress\_data}\\n\\n"  
                    if progress\_data \== "1.0":  \# Tarea completada   
                        break  
                await asyncio.sleep(0.5)  
        finally:  
            await pubsub.unsubscribe(f"progress\_channel:{task\_id}")  
            await redis\_conn.close()

    return StreamingHttpResponse(event\_generator(), media\_type="text/event-stream")

En el worker de Celery, el progreso se calcula y se actualiza de forma iterativa 25:

Python  
@celery\_app.task(bind=True)  
def process\_massive\_deck\_creation(self, deck\_id: str, prompt\_data: list):  
    redis\_sync \= redis.Redis(host="localhost", port=6379, db=1)  
    total\_elements \= len(prompt\_data)  
      
    for idx, prompt in enumerate(prompt\_data):  
        \# Procesamiento individual...  
          
        \# Cálculo del progreso incremental   
        progress\_percentage \= (idx \+ 1) / total\_elements  
        \# Publicación del evento en el bus Redis Pub/Sub para su entrega a SSE   
        redis\_sync.publish(f"progress\_channel:{self.request.id}", str(progress\_percentage))

### **Gestión de Conexiones SQLAlchemy en Celery**

Un error común al integrar SQLAlchemy dentro de las tareas de Celery es mantener una única sesión activa para todo el ciclo de vida del proceso del worker.25 Esto provoca fugas de conexión, bloqueos transaccionales y problemas de concurrencia. La recomendación de la arquitectura de datos es instanciar y cerrar de forma explícita el contexto de la sesión de base de datos en cada ejecución individual de la tarea 25:

Python  
from sqlalchemy import create\_engine  
from sqlalchemy.orm import sessionmaker, scoped\_session

engine \= create\_engine("postgresql://app\_user:pass@localhost/db", pool\_size=5, max\_overflow=10)  
SessionLocal \= scoped\_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

@celery\_app.task(bind=True)  
def sync\_card\_statistics(self, card\_stats\_payload: dict):  
    \# Inicialización local de la sesión transaccional   
    db\_session \= SessionLocal()  
    try:  
        \# Lógica de actualización relacional...  
        db\_session.commit()  
    except Exception:  
        db\_session.rollback()  
        raise  
    finally:  
        \# Garantiza el retorno inmediato de la conexión al pool de base de datos   
        db\_session.close()

## **Optimización de Costos de IA, Circuit Breakers y Caché Semántica de Modelos LLM**

Integrar servicios de inteligencia artificial de terceros (como la API de Google Gemini o de OpenAI) expone al SaaS a problemas de inestabilidad de red y variaciones imprevistas de costos debido a picos de tráfico involuntarios o ataques maliciosos de denegación de cartera.26 Para blindar el backend, se requiere un diseño defensivo multi-capa.27

### **Caché Semántica Dual-Layer para Reducción de Latencia y Costos**

La optimización de costos más efectiva consiste en evitar la ejecución innecesaria de peticiones al modelo LLM mediante el uso de una caché semántica de doble capa en Redis.29  
Esta arquitectura opera bajo dos fases consecutivas de validación:

1. **Fase de Coincidencia de Hash Directo (Exacta)**: La consulta entrante se reduce a un hash criptográfico SHA-256.30 Se verifica su existencia en Redis mediante una búsqueda directa de clave-valor.30 Si coincide exactamente, el resultado se sirve en microsegundos, eliminando los costos de procesamiento del modelo y del embedding.30  
2. **Fase de Similitud Vectorial (Semántica)**: Si no hay coincidencia exacta, la consulta se convierte en un vector denso mediante un modelo de embeddings ligero.29 Se realiza una consulta de similitud de coseno en la base de datos de vectores de Redis utilizando un índice HNSW.29 Si la distancia calculada es inferior al umbral de similitud configurado (típicamente entre ![][image4] y ![][image5] de puntuación de coseno), se considera un acierto de caché (*cache hit*) semántico y se sirve la respuesta de inmediato, reduciendo los tiempos de respuesta de segundos a milisegundos y reduciendo las facturas de APIs externas hasta en un 68.8%.29

Python  
from langchain\_redis import RedisSemanticCache  
from langchain\_openai import OpenAIEmbeddings  
from langchain\_core.globals import set\_llm\_cache  
import os

\# Inicialización de la capa de embeddings con un modelo altamente optimizado en costo/rendimiento  
embeddings\_generator \= OpenAIEmbeddings(model="text-embedding-3-small")

\# Configuración del motor de almacenamiento y búsqueda semántica de Redis \[31, 32\]  
semantic\_cache \= RedisSemanticCache(  
    embeddings=embeddings\_generator,  
    redis\_url=os.getenv("REDIS\_URL", "redis://localhost:6379/3"),  
    distance\_threshold=0.10,  \# Umbral restrictivo para asegurar precisión semántica \[29, 32\]  
    ttl=604800,               \# TTL de 7 días para renovar el contenido dinámicamente \[29, 32\]  
    name="llm\_flashcard\_cache"  
)

\# Acoplamiento de la caché semántica en el ciclo de ejecución de LangChain \[30, 32\]  
set\_llm\_cache(semantic\_cache)

### **Resiliencia Upstream con Circuit Breakers y Reintentos con Backoff Exponencial**

Cuando el proveedor externo de IA experimenta caídas del servicio o supera los límites de cuota (RPS/TPM), devuelve códigos de error HTTP 429 o 5xx de forma sistemática.27 Insistir en el reenvío inmediato de peticiones sella la parálisis del sistema y desperdicia recursos del servidor web de FastAPI.27  
Se debe estructurar una estrategia combinada de **Circuit Breaker** (Disyuntor) con políticas de reintentos asíncronos bajo **Backoff Exponencial**.21 El circuit breaker monitorea los errores del servicio de IA; si se detecta un pico de fallas repetidas, el disyuntor se abre, deteniendo temporalmente las peticiones al proveedor de IA durante una ventana de enfriamiento y retornando respuestas degradadas de forma elegante para no colapsar la cola de procesamiento de la aplicación.27

Python  
import pybreaker  
from tenacity import retry, stop\_after\_attempt, wait\_exponential, retry\_if\_exception\_type  
from google.genai.errors import APIError

\# Configuración del Circuit Breaker que abre el flujo tras 5 fallas y bloquea llamadas por 120 segundos   
gemini\_circuit\_breaker \= pybreaker.CircuitBreaker(  
    fail\_max=5,   
    reset\_timeout=120  
)

\# Política de reintento basada en Tenacity con incremento exponencial   
\# Se esperan 2^x segundos entre reintentos, deteniéndose tras 4 intentos \[21\]  
ai\_retry\_policy \= retry(  
    stop=stop\_after\_attempt(4),  
    wait=wait\_exponential(multiplier=1, min\=2, max\=16),  
    retry=retry\_if\_exception\_type(APIError),  
    reraise=True  
)

@gemini\_circuit\_breaker  
@ai\_retry\_policy  
def call\_upstream\_gemini\_api(client, model: str, system\_instruction: str, prompt: str):  
    """  
    Consume la API de Gemini bajo esquemas de seguridad defensiva de doble anillo.  
    """  
    return client.models.generate\_content(  
        model=model,  
        contents=prompt,  
        config=types.GenerateContentConfig(  
            system\_instruction=system\_instruction  
        )  
    )

### **Control y Conteo Preciso de Tokens con google-genai SDK 2.0.0+**

En la versión del SDK moderno de Google (google-genai), se debe verificar que la cantidad de tokens que componen la petición esté comprendida dentro de la asignación de cuota del inquilino antes de realizar el consumo del servicio de IA.28  
El conteo preciso de tokens debe contemplar no solo el texto plano, sino también las reglas de asignación multimedia y las instrucciones de sistema 33:

* **Texto de Instrucción del Sistema**: Se cuenta de forma explícita como parte de los tokens de entrada de la petición.33  
* **Imágenes**: Elementos de tamaño inferior o igual a 384px en ambas dimensiones consumen exactamente 258 tokens.33 Imágenes superiores se segmentan en celdas (*tiles*) de 768x768 píxeles, donde cada una computa 258 tokens.33  
* **Video**: Se computan aproximadamente 263 tokens por cada segundo de video procesado.33  
* **Audio**: Se computan exactamente 32 tokens por cada segundo de fragmento de audio digital.33

La implementación asíncrona del pre-vuelo (*pre-flight*) de control de costos y la captura de metadatos de consumo se realiza de la siguiente manera:

Python  
from google import genai  
from google.genai import types  
import os

client \= genai.Client(api\_key=os.getenv("GEMINI\_API\_KEY"))

async def generate\_monitored\_cards(prompt: str, tenant\_tier: str) \-\> dict:  
    """  
    Pre-evalúa los tokens requeridos antes de ejecutar la llamada al modelo LLM,  
    evitando la sobrecarga y el desborde financiero de cuotas.\[28, 33, 34\]  
    """  
    model\_id \= "gemini-2.5-flash"  
      
    \# Pre-vuelo de conteo de tokens de la entrada del usuario \[33, 34\]  
    token\_preflight \= client.models.count\_tokens(  
        model=model\_id,  
        contents=prompt  
    )  
      
    estimated\_input\_tokens \= token\_preflight.total\_tokens  
      
    \# Límite estricto por petición para el plan actual del inquilino  
    max\_tokens\_allowed \= 4000 if tenant\_tier \== "free" else 25000  
      
    if estimated\_input\_tokens \> max\_tokens\_allowed:  
        raise HTTPException(  
            status\_code=status.HTTP\_413\_PAYLOAD\_TOO\_LARGE,  
            detail=f"La consulta excede la asignación de tokens permitida para su plan ({estimated\_input\_tokens}/{max\_tokens\_allowed}).\[28, 35\]"  
        )  
          
    \# Ejecución de la llamada al modelo  
    response \= client.models.generate\_content(  
        model=model\_id,  
        contents=prompt  
    )  
      
    \# Extracción minuciosa de los metadatos de consumo devueltos para facturación y auditoría \[33, 34, 36\]  
    usage \= response.usage\_metadata  
      
    return {  
        "content": response.text,  
        "metrics": {  
            "prompt\_tokens": usage.prompt\_token\_count,  
            "completion\_tokens": usage.candidates\_token\_count,  
            "total\_tokens": usage.total\_token\_count  
        }  
    }

## **Optimización del Frontend Angular, Hidratación Incremental y Rendimiento Móvil**

La migración desde un motor de interfaz gráfico local asíncrono como Tkinter hacia un entorno web móvil exige una estrategia orientada a la minimización del tamaño de los bundles de JavaScript y a la optimización del tiempo de interactividad en el navegador del cliente.37

### **Compilación y Tree-Shaking de Dependencias**

Para reducir la huella de transferencia de datos sobre redes móviles, se debe abandonar el compilador JIT (*Just-in-Time*) y emplear la compilación por adelantado (**Ahead-of-Time o AOT**) durante la fase de construcción de la aplicación.40 Esto remueve el compilador de Angular del bundle final enviado al navegador del cliente y realiza análisis de tipos en plantillas previas al despliegue.39  
En combinación con los componentes autónomos (*Standalone Components*), el proceso de construcción (*build pipeline*) detecta y elimina el código muerto, dependencias no referenciadas o componentes no invocados de librerías masivas de terceros, aplicando un **Tree-Shaking** agresivo.38

Bash  
\# Construcción optimizada para producción con tree-shaking habilitado y eliminación de source maps \[39\]  
ng build \--configuration production \--optimization=true \--build-optimizer=true \--source-maps=false

### **Hidratación Incremental con Vistas Diferibles (Deferrable Views)**

Cuando se implementa el renderizado del lado del servidor (SSR), el usuario recibe instantáneamente la estructura HTML estática de la interfaz.37 Sin embargo, bajo un esquema clásico de hidratación, el hilo principal del navegador se bloquea de forma abrupta mientras el framework inicializa la aplicación y adjunta los manejadores de eventos (*event listeners*) sobre toda la página, provocando una experiencia deficiente para el usuario que ve la pantalla pero no puede interactuar con ella.37  
La característica de **Vistas Diferibles** (*Deferrable Views*) y la **Hidratación Incremental** resuelven este problema dividiendo el árbol DOM de la interfaz en "islas" independientes con prioridad asíncrona.37 La carga del código y la activación de la interactividad se retrasan de forma inteligente utilizando directivas de comportamiento condicionales.37

HTML  
\<div class\="deck-workspace-container"\>  
    
  \<div class\="main-workspace-card-view"\>  
    \<app-flashcard-interactive-player \[deckId\]="activeDeckId"\>\</app-flashcard-interactive-player\>  
  \</div\>

  @defer (hydrate on viewport; prefetch on idle) {  
    \<app-deck-analytics-graph \[deckId\]="activeDeckId"\>\</app-deck-analytics-graph\>  
  } @placeholder {  
    \<div class\="visual-placeholder-loading"\>  
      \<p\>Cargando panel de estadísticas y reportes de rendimiento...\</p\>  
    \</div\>  
  } @loading {  
    \<div class\="global-loading-indicator"\>Descargando componentes dinámicos...\</div\>  
  } @error {  
    \<div class\="global-error-banner"\>Se produjo un error al cargar el componente analítico.\</div\>  
  }  
\</div\>

Las directivas de comportamiento para la hidratación se categorizan de la siguiente forma:

* **hydrate on idle**: El framework hidrata el componente tan pronto como el hilo principal del navegador ingresa en reposo utilizando la función requestIdleCallback, evitando interferir con interacciones prioritarias del usuario.37  
* **hydrate on viewport**: Utiliza la API de IntersectionObserver de forma implícita para ejecutar la descarga e interactividad únicamente cuando el bloque estático se vuelve visible en pantalla.37 Ideal para pies de página (*footers*), paneles analíticos secundarios y listados extensos.37  
* **hydrate on interaction**: Retarda la hidratación hasta que el usuario realiza una acción explícita (como un evento de click, keydown o touchstart) sobre el bloque estático.37  
* **Replay Automático de Eventos**: Para evitar que la primera interacción del usuario con un bloque estático se pierda durante la carga del bundle JavaScript de hidratación, Angular inyecta un script de despacho de eventos ultraligero en la raíz del documento.37 Este script captura la acción (un clic, por ejemplo), almacena temporalmente el evento, desencadena la hidratación inmediata y, una vez que el componente es completamente interactivo, vuelve a disparar la acción de manera imperceptible.37

*Regla de Jerarquía Estricta en Hidratación*: La compilación condicional de Angular establece que no es posible hidratar un elemento hijo dentro de un contenedor padre que permanece deshidratado.37 Si el usuario desencadena un evento que fuerza la hidratación de un nodo interno, Angular escalará automáticamente e hidratará en cascada todos los componentes del árbol de ascendencia directa para preservar la consistencia de la detección de cambios y los flujos de datos.37

## **Cumplimiento Normativo, Privacidad por Diseño y Anonimización con Microsoft Presidio**

Dado que "Flashcards AI" almacena apuntes de estudio y textos que pueden contener información personal, enviar datos sin procesar a APIs de inteligencia artificial externas representa un riesgo grave de incumplimiento normativo (como el RGPD europeo, CCPA estadounidense o la Ley de Protección de Datos Personales en el entorno local).41  
Para cumplir con el principio de privacidad por diseño (*Privacy by Design*), el backend de FastAPI debe implementar una pasarela de análisis y anonimización en tiempo real utilizando el framework **Microsoft Presidio** antes de enviar cualquier consulta a proveedores externos.41

\[ FastAPI Context \] \---\> (1) Texto sin procesar \-----------------------------\> \[ Presidio Analyzer \]  
                                                                                      |  
                                                                               Analiza patrones NLP  
                                                                               y expresiones regulares  
                                                                                      |  
                        (2) Identifica Entidades (Nombres, Tarjetas, Emails) \<--------+  
                               |  
                               v  
                        \[ Presidio Anonymizer \]  
                               |  
                        Aplica cifrado,  
                        hashing o enmascarado  
                               |  
                        (3) Texto Anonimizado \-------------------------------\> \[ Gemini API Upstream \]

### **Implementación del Proceso de Anonimización**

El flujo de limpieza evalúa el contenido en dos fases consecutivas 41:

1. **Detección Estructurada (AnalyzerEngine)**: Emplea algoritmos de Procesamiento de Lenguaje Natural (NLP), Reconocimiento de Entidades Nombradas (NER) y patrones de expresiones regulares personalizadas para identificar información de identificación personal (PII), como nombres de personas, direcciones de correo, documentos nacionales de identidad o números de tarjetas de crédito.41  
2. **Transformación Controlada (AnonymizerEngine)**: Aplica políticas sobre los datos detectados, tales como enmascaramiento total/parcial, eliminación directa de caracteres o generación de hashes con sal para preservar la integridad referencial a lo largo de las sesiones de entrenamiento del usuario.42

Python  
from presidio\_analyzer import AnalyzerEngine  
from presidio\_anonymizer import AnonymizerEngine  
from presidio\_anonymizer.entities import OperatorConfig

\# Inicialización de motores de análisis y transformación de Microsoft Presidio \[43, 44\]  
analyzer\_engine \= AnalyzerEngine()  
anonymizer\_engine \= AnonymizerEngine()

def scrub\_pii\_from\_study\_material(raw\_user\_input: str, tenant\_salt: str) \-\> str:  
    """  
    Identifica y sanitiza cualquier registro de información de identificación personal (PII)  
    presente en los apuntes del usuario para garantizar el cumplimiento normativo.  
    """  
    \# 1\. Ejecución del motor NLP para clasificar las entidades de riesgo \[41, 43\]  
    detected\_entities \= analyzer\_engine.analyze(  
        text=raw\_user\_input,  
        language="en",  
        entities=  
    )  
      
    \# 2\. Configuración del operador criptográfico para preservar consistencia  
    \# Emplear un hash con sal derivado del tenant evita la fuga de nombres, pero permite que  
    \# si la palabra se repite dentro del texto de estudio, mantenga la relación lógica en la flashcard.\[44\]  
    salt\_hash\_config \= OperatorConfig(  
        operator\_name="hash",  
        params={  
            "hash\_type": "sha256",  
            "salt": tenant\_salt  
        }  
    )  
      
    \# 3\. Anonimización basada en operadores condicionales por cada tipo de entidad \[43, 44\]  
    sanitized\_output \= anonymizer\_engine.anonymize(  
        text=raw\_user\_input,  
        analyzer\_results=detected\_entities,  
        operators={  
            "PERSON": salt\_hash\_config,  
            "EMAIL\_ADDRESS": salt\_hash\_config,  
            "PHONE\_NUMBER": OperatorConfig(  
                operator\_name="mask",   
                params={"masking\_char": "\*", "chars\_to\_mask": 8, "from\_end": True}  
            ),  
            "CREDIT\_CARD": OperatorConfig(  
                operator\_name="mask",   
                params={"masking\_char": "\*", "chars\_to\_mask": 12, "from\_end": True}  
            ),  
            "DEFAULT": OperatorConfig(  
                operator\_name="replace",   
                params={"new\_value": "\<PII\_ENTIDAD\_REDACTADA\>"}  
            )  
        }  
    )  
      
    return sanitized\_output.text

## **Conclusiones y Recomendaciones de Ingeniería**

La migración exitosa de "Flashcards AI" a una arquitectura SaaS profesional de alta disponibilidad y segura requiere la ejecución integrada de los siguientes hitos de ingeniería:

1. **Aislamiento a Nivel Relacional**: Implementar políticas RLS en PostgreSQL, configurando la inyección de la variable de sesión session.current\_tenant exclusivamente con la directiva SET LOCAL dentro de bloques transaccionales del backend.1  
2. **Carga Directa y Segura a Almacenamiento**: Desplazar el procesamiento de binarios pesados fuera de FastAPI.5 Habilitar el firmado de políticas Presigned POST forzando validaciones del encabezado Content-MD5 y límites de tamaño directamente en el bucket.5 Implementar políticas de ciclo de vida para evitar cobros innecesarios por cargas huérfanas u obsoletas.9  
3. **Seguridad de Sesiones Multiinquilino**: Almacenar los tokens JWT dentro de cookies marcadas como HttpOnly, Secure y SameSite=Strict.13 Implementar el mecanismo defensivo de Doble Envío de Cookies para proteger las interacciones contra ataques de origen cruzado (CSRF).13  
4. **Idempotencia y Trazabilidad en la Cola de Tareas**: Adoptar la propagación de contexto de OpenTelemetry en Celery y evitar condiciones de carrera ejecutando los despachos únicamente tras la confirmación de las transacciones relacionales.19 Proteger los flujos pesados con patrones de bloqueo distribuido en Redis.19  
5. **Mitigación del Consumo y Costos de IA**: Implementar una caché semántica de doble capa en Redis para reducir de forma drástica los consumos redundantes del modelo LLM.29 Proteger el backend con circuit breakers en llamadas upstream.27  
6. **Optimización de Interfaz Móvil**: Reestructurar el frontend en Angular utilizando componentes autónomos y compilación AOT.38 Adoptar vistas diferibles para implementar hidratación incremental inteligente, disminuyendo de esta manera los tiempos de bloqueo del hilo de ejecución en el cliente.37  
7. **Privacidad por Diseño**: Implementar un middleware asíncrono basado en Microsoft Presidio para anonimizar y enmascarar información personal antes de enviar datos del usuario a proveedores externos de IA.41

#### **Obras citadas**

1. Why PostgreSQL Row-Level Security Is the Right Approach to Django Multitenancy, fecha de acceso: mayo 31, 2026, [https://dev.to/dvoraj75/why-postgresql-row-level-security-is-the-right-approach-to-django-multitenancy-3e1m](https://dev.to/dvoraj75/why-postgresql-row-level-security-is-the-right-approach-to-django-multitenancy-3e1m)  
2. How to Secure Multi-Tenant Data with Row-Level Security in ..., fecha de acceso: mayo 31, 2026, [https://oneuptime.com/blog/post/2026-01-25-row-level-security-postgresql/view](https://oneuptime.com/blog/post/2026-01-25-row-level-security-postgresql/view)  
3. Multi-tenant data isolation with PostgreSQL Row Level Security | AWS Database Blog, fecha de acceso: mayo 31, 2026, [https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/)  
4. Multi-Tenant PostgreSQL: RLS for Strict Data Isolation (B2B SaaS) \- WellAlly, fecha de acceso: mayo 31, 2026, [https://www.wellally.tech/blog/postgres-multi-tenant-database-row-level-security](https://www.wellally.tech/blog/postgres-multi-tenant-database-row-level-security)  
5. Master S3 Pre-Signed URLs: Secure, Serverless File Uploads | AWS Builder Center, fecha de acceso: mayo 31, 2026, [https://builder.aws.com/content/3EBBP64yr1XgMhatjI9juHgarxc/master-s3-pre-signed-urls-secure-serverless-file-uploads](https://builder.aws.com/content/3EBBP64yr1XgMhatjI9juHgarxc/master-s3-pre-signed-urls-secure-serverless-file-uploads)  
6. Secure File Uploads Made Simple: Mastering S3 Presigned URLs with React and FastAPI, fecha de acceso: mayo 31, 2026, [https://medium.com/@coretechnotes/secure-file-uploads-made-simple-mastering-s3-presigned-urls-with-react-and-fastapi-258a8f874e97](https://medium.com/@coretechnotes/secure-file-uploads-made-simple-mastering-s3-presigned-urls-with-react-and-fastapi-258a8f874e97)  
7. Securing Amazon S3 presigned URLs for serverless applications | AWS Compute Blog, fecha de acceso: mayo 31, 2026, [https://aws.amazon.com/blogs/compute/securing-amazon-s3-presigned-urls-for-serverless-applications/](https://aws.amazon.com/blogs/compute/securing-amazon-s3-presigned-urls-for-serverless-applications/)  
8. How I Built a Secure File Upload API Using FastAPI and AWS S3 Presigned URLs, fecha de acceso: mayo 31, 2026, [https://dev.to/copubah/how-i-built-a-secure-file-upload-api-using-fastapi-and-aws-s3-presigned-urls-7eg](https://dev.to/copubah/how-i-built-a-secure-file-upload-api-using-fastapi-and-aws-s3-presigned-urls-7eg)  
9. How to Automatically Delete Old Objects with S3 Lifecycle Policies \- OneUptime, fecha de acceso: mayo 31, 2026, [https://oneuptime.com/blog/post/2026-02-12-automatically-delete-old-objects-s3-lifecycle/view](https://oneuptime.com/blog/post/2026-02-12-automatically-delete-old-objects-s3-lifecycle/view)  
10. S3 Lifecycle Rules: Using Bucket Lifecycle Configurations \- NetApp, fecha de acceso: mayo 31, 2026, [https://www.netapp.com/blog/aws-cvo-blg-s3-lifecycle-rules-using-bucket-lifecycle-configurations/](https://www.netapp.com/blog/aws-cvo-blg-s3-lifecycle-rules-using-bucket-lifecycle-configurations/)  
11. AWS S3 Lifecycle Rule | Guide \- How to delete file from S3 after X days \- tutorial \- YouTube, fecha de acceso: mayo 31, 2026, [https://www.youtube.com/watch?v=U9bhFf3q6YI](https://www.youtube.com/watch?v=U9bhFf3q6YI)  
12. Session cookies vs JWT tokens \- which is more secure for web applications? \- MojoAuth, fecha de acceso: mayo 31, 2026, [https://mojoauth.com/ciam-qna/session-cookies-vs-jwt-tokens-security](https://mojoauth.com/ciam-qna/session-cookies-vs-jwt-tokens-security)  
13. JWT in Cookies \- FastAPI JWT Auth, fecha de acceso: mayo 31, 2026, [https://indominusbyte.github.io/fastapi-jwt-auth/usage/jwt-in-cookies/](https://indominusbyte.github.io/fastapi-jwt-auth/usage/jwt-in-cookies/)  
14. Token-Based Authentication with Cookies and JWT Expiration | CodeSignal Learn, fecha de acceso: mayo 31, 2026, [https://codesignal.com/learn/courses/secure-authentication-authorization-in-fastapi/lessons/token-based-authentication-with-cookies-and-jwt-expiration](https://codesignal.com/learn/courses/secure-authentication-authorization-in-fastapi/lessons/token-based-authentication-with-cookies-and-jwt-expiration)  
15. JWTs & CSRF Tokens. When and Where to use JSON Web Tokens &… | by Buddika Gunawardena | Medium, fecha de acceso: mayo 31, 2026, [https://medium.com/@gunawardena.buddika/jwts-csrf-tokens-465e5d4f91cf](https://medium.com/@gunawardena.buddika/jwts-csrf-tokens-465e5d4f91cf)  
16. JWT \+ CSRF: A Good Security Practice? : r/node \- Reddit, fecha de acceso: mayo 31, 2026, [https://www.reddit.com/r/node/comments/1im7yj0/jwt\_csrf\_a\_good\_security\_practice/](https://www.reddit.com/r/node/comments/1im7yj0/jwt_csrf_a_good_security_practice/)  
17. Handling Background Tasks and Long-Running Jobs in FastAPI: The Complete Guide, fecha de acceso: mayo 31, 2026, [https://python.plainenglish.io/handling-background-tasks-and-long-running-jobs-in-fastapi-the-complete-guide-b197d38145d7](https://python.plainenglish.io/handling-background-tasks-and-long-running-jobs-in-fastapi-the-complete-guide-b197d38145d7)  
18. Polling vs SSE vs Websockets: which approach use the least workers? : r/FastAPI \- Reddit, fecha de acceso: mayo 31, 2026, [https://www.reddit.com/r/FastAPI/comments/1if6o84/polling\_vs\_sse\_vs\_websockets\_which\_approach\_use/](https://www.reddit.com/r/FastAPI/comments/1if6o84/polling_vs_sse_vs_websockets_which_approach_use/)  
19. Production-Ready Django, Celery, and Redis Guide \- Rahul Baberwal, fecha de acceso: mayo 31, 2026, [https://rahulbaberwal.com/blog/django-celery-redis/](https://rahulbaberwal.com/blog/django-celery-redis/)  
20. Ultimate guide to Celery library in Python \- Deepnote, fecha de acceso: mayo 31, 2026, [https://deepnote.com/blog/ultimate-guide-to-celery-library-in-python](https://deepnote.com/blog/ultimate-guide-to-celery-library-in-python)  
21. How to Build a Job Queue in Python with Celery and Redis \- OneUptime, fecha de acceso: mayo 31, 2026, [https://oneuptime.com/blog/post/2025-01-06-python-celery-redis-job-queue/view](https://oneuptime.com/blog/post/2025-01-06-python-celery-redis-job-queue/view)  
22. From Celery/Redis to Temporal: A Journey Toward Idempotency and Reliable Workflows, fecha de acceso: mayo 31, 2026, [https://dev.to/wintrover/from-celeryredis-to-temporal-a-journey-toward-idempotency-and-reliable-workflows-k1i](https://dev.to/wintrover/from-celeryredis-to-temporal-a-journey-toward-idempotency-and-reliable-workflows-k1i)  
23. How to Propagate OpenTelemetry Trace Context Through Celery Message Headers \- OneUptime, fecha de acceso: mayo 31, 2026, [https://oneuptime.com/blog/post/2026-02-06-propagate-opentelemetry-trace-context-celery-headers/view](https://oneuptime.com/blog/post/2026-02-06-propagate-opentelemetry-trace-context-celery-headers/view)  
24. Celery OpenTelemetry Instrumentation \- Task Tracing & Propagation | base14 Scout, fecha de acceso: mayo 31, 2026, [https://docs.base14.io/instrument/apps/auto-instrumentation/celery/](https://docs.base14.io/instrument/apps/auto-instrumentation/celery/)  
25. Real-Time Celery Progress Bars with FastAPI, socket.io and HTMX, fecha de acceso: mayo 31, 2026, [https://celery.school/celery-progress-bars-with-fastapi-htmx](https://celery.school/celery-progress-bars-with-fastapi-htmx)  
26. Rate Limiting in FastAPI: Essential Protection for ML API Endpoints \- Full Stack Data Science, fecha de acceso: mayo 31, 2026, [https://fullstackdatascience.com/blogs/rate-limiting-in-fastapi-essential-protection-for-ml-api-endpoints-d5xsqw](https://fullstackdatascience.com/blogs/rate-limiting-in-fastapi-essential-protection-for-ml-api-endpoints-d5xsqw)  
27. FastAPI Resiliency: Circuit Breakers, Rate Limiting, and External API Management, fecha de acceso: mayo 31, 2026, [https://www.aritro.in/post/fastapi-resiliency-circuit-breakers-rate-limiting-and-external-api-management/](https://www.aritro.in/post/fastapi-resiliency-circuit-breakers-rate-limiting-and-external-api-management/)  
28. How to Implement LLM Rate Limiting \- OneUptime, fecha de acceso: mayo 31, 2026, [https://oneuptime.com/blog/post/2026-01-30-llm-rate-limiting/view](https://oneuptime.com/blog/post/2026-01-30-llm-rate-limiting/view)  
29. What is Semantic Caching? A Complete Guide \- Redis, fecha de acceso: mayo 31, 2026, [https://redis.io/blog/how-to-cache-semantic-search/](https://redis.io/blog/how-to-cache-semantic-search/)  
30. Top Semantic Caching Solutions for AI Applications in 2026 \- Maxim AI, fecha de acceso: mayo 31, 2026, [https://www.getmaxim.ai/articles/top-semantic-caching-solutions-for-ai-applications-in-2026/](https://www.getmaxim.ai/articles/top-semantic-caching-solutions-for-ai-applications-in-2026/)  
31. Redis for AI | Docs, fecha de acceso: mayo 31, 2026, [https://redis.io/docs/latest/integrate/redis-ai-libraries/](https://redis.io/docs/latest/integrate/redis-ai-libraries/)  
32. Understand and count tokens \- Interactions API \- Google AI for Developers, fecha de acceso: mayo 31, 2026, [https://ai.google.dev/gemini-api/docs/interactions/tokens](https://ai.google.dev/gemini-api/docs/interactions/tokens)  
33. Incremental Hydration in Angular: Build SSR Apps That Feel Instantly Interactive, fecha de acceso: mayo 31, 2026, [https://www.syncfusion.com/blogs/post/incremental-hydration-in-angular-apps](https://www.syncfusion.com/blogs/post/incremental-hydration-in-angular-apps)  
34. Angular bundle size optimization through deferrable views \- Halodoc Blog, fecha de acceso: mayo 31, 2026, [https://blogs.halodoc.io/optimize-angular-bundle-size-through-deferrable-views/](https://blogs.halodoc.io/optimize-angular-bundle-size-through-deferrable-views/)  
35. How to optimize Angular build size \- CoreUI, fecha de acceso: mayo 31, 2026, [https://coreui.io/answers/how-to-optimize-angular-build-size/](https://coreui.io/answers/how-to-optimize-angular-build-size/)  
36. Proven Strategies for Optimizing Angular Applications for Performance \- Innoraft, fecha de acceso: mayo 31, 2026, [https://www.innoraft.ai/blog/proven-strategies-optimizing-angular-applications-performance](https://www.innoraft.ai/blog/proven-strategies-optimizing-angular-applications-performance)  
37. Microsoft Presidio PII Anonymization: Stop Data Leaks Before They Grow \- hoop.dev, fecha de acceso: mayo 31, 2026, [https://hoop.dev/blog/microsoft-presidio-pii-anonymization-stop-data-leaks-before-they-grow](https://hoop.dev/blog/microsoft-presidio-pii-anonymization-stop-data-leaks-before-they-grow)  
38. Privacy by Design: PII Detection and Anonymization with PySpark on Microsoft Fabric, fecha de acceso: mayo 31, 2026, [https://community.fabric.microsoft.com/t5/Fabric-Updates-Blog/Privacy-by-Design-PII-Detection-and-Anonymization-with-PySpark/ba-p/5172713](https://community.fabric.microsoft.com/t5/Fabric-Updates-Blog/Privacy-by-Design-PII-Detection-and-Anonymization-with-PySpark/ba-p/5172713)  
39. Microsoft Presidio: An Open Source Tool Specialized in Personal Information Protection, fecha de acceso: mayo 31, 2026, [https://developer.mamezou-tech.com/en/blogs/2025/01/04/presidio-intro/](https://developer.mamezou-tech.com/en/blogs/2025/01/04/presidio-intro/)  
40. Presidio Anonymizer, fecha de acceso: mayo 31, 2026, [https://microsoft.github.io/presidio/anonymizer/](https://microsoft.github.io/presidio/anonymizer/)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABEAAAAWCAYAAAAmaHdCAAABk0lEQVR4Xp1UK0tEURCeAdniA6NgMOovEBQxGAwms0mLP0CrxbxtMRgEg9FgEhT/gIggGNTmLZpMBoth/ebMnDmPe1fEgTln5ptvHmf2skRdwjXwD/EaXNXLnV8bhWBicM6Wohx9uUdUcoolBGpex3IVskDROMeiuDOia4csQ2+gr0gaIu3WIzYB5Ar6DXMI/x32oXOKjkzXMBoSItFiLJDq0B701BISmnwex/kMfJu0yEVJCClH0LUiVTvE34HXcQygPQANbnnWvBNV7sDu6ZLrKZTVh24asA9Iphlom0CZw3nZfkIQ/yLuoVNGmkCnD9yf8KeNuEuyE6vYVWoL4IF7ypiBfkHfoJMAX1I8K5FMPiH5mR3gGDwmXfKZaHd/B/kJx1jEBLWEBdLdiO7kPfy2523geAiWAZFknHMOHxjPWmoqAmMFhyxTvkDp1EBXS1Yos4Tj0Ru0JMcyW/nVBmyZaacjq4qUZPOyF7D9LXBJKgeKaZXUxCgR+8NgyY1T1AGRDoh8Lq7ibXIxT0vqnm7D+AGwei3y4oH0sAAAAABJRU5ErkJggg==>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABoAAAAZCAYAAAAv3j5gAAACiklEQVR4XpVVzYuPURQ+tyh2ksWkFAsNEykzxGLQZMNqsBjKQqSZsPCRWBBKzUpKo2loQpEUFv4BJlnIzo5J2UxSsmAxS55zz7n3nvvx9mue6bz33Oc855x77/ve+RE14PzDPzsh0aDJx47MJYkjkqrWt3MN2xL0LJOtL49V9VTTB5uF9xbzj/BPm2hElSzYDXuN4BzsHfw9ni1T8bcGzmc4Z5RcB808xptJ1YldsAUIdup8P+otYhxpJd1x3Eih8QnYL9jyHh/GJ4TvFdwz2JvW8r7DXhTcCOwfxMPp+DUx5W8UDZ0r+Bvw/4BYFhmgj0Q8I9OoHlT+WiACwgZxRGMkmuOph/cuKL830sCQJx1NFRvd6kT8KKczXCTRcMME584qf9LS3JXJqUBowwHlnzaOOlC8W16kaeQjExg4d1x08uRP0++oeHmbWQzmiSUFLkivaMGxYjHjJDVPWbLfk0T3LQlsUf5uwVvwXWPNUems65drwvxhuwC+QyAdX1aFj+7Ay2bxdf/aU9DiCEnBEzKNzS6hG/P7Ei/4isCrMFH6AIyP7mDgG1hPrHF0vuAnYYvIXVXw7jYeX9gx5GXYD+IL6yX+OQw7FhWCOdjDbM+OLyu9jFQa3QoMH2CjekwriXeJ+6ESkRH9JTnO7YmiDbBvsLV6vwYw/CZ5902sRt5VJD+G8AHmh2xQF/Ue9pO81tn/TJtgt2DPIZyGehuT9nh04go2ofoM4pSdKqp8D/SWqKIS+l+AVkCQLy7sStiUYpIbdQKV1bJOrFnUyQ9DmxcNoqZRRN5bI6lEfMEdv0FtNsG0rMesZlkpzrtXWbPVuahj2LT1HLm4u2kTS5AW2+Z5kW8WmBYVHKL/MXlaQWipC5QAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABoAAAAZCAYAAAAv3j5gAAACO0lEQVR4Xp1UO2uVQRCdAcHGIlimMoUoaQQLSYqoiD9ATJEIFpIgEZWgsbARxMpeBAvrkEbMoxXBYCOkS58yhY2FchFszJmd2d3Zx3eveGBmZ8+89yYfkYBV2RGtAg0jBEfWZYT8aIcg53F8U9CQanrOaZ/YCf1HtLVKeEcx0WBGgOw1U5PjwfNQHyH7kC+ocLUKEKSu07BvYaBPsLddwATwHNQx5IrVugn5DftG8JZL8TrUIeQt+D80oVH5G9MBzDfJp2oTeq98UmfbZYQzNKqGKW4KPg/1F/JYr4l/CfkJ41SblokRyUZNQA+8BJFGd2O4nU9JB7jGvT9XATeNuL8MBXqDtOBSJDSUHxm/EmMz6o0KKsMKqWZ6QdYobxSsB6ybrhldIwSl32gQeYLnpAXlCdWlhzQQfrU/rkI22mndLQPcJy24LBcX8dD425mqgJVHSNixSxoxXdNNLrxIWvCep+F4Jjxir+eMdlBsxLsd3iE5z5E2epJcitcs/7RMUwVb1mR5ur2CylhA8J0qYx/yvtw05H/wVD34aQqfD/osb+j9rOYv0ie5HElgBnIEmbbYWcgPvPiFpjrpd+kbaRMpJM9xRPrdOxMiNPArjO+Qs5YX9UXoVzC3cL7D/ZKwOqsbNSHY3Pc1xJA9CeNih3xDfIBzxgX6jnFwW2fG6aECDe8L1U65Z672BkQynN2ICHOWh1nVvFZsbLncsamY0eP+F22tlinAOSJ+odLMkzEU5asWDoPzJ6Z9yhP+YEto7GOwsAAAAABJRU5ErkJggg==>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACUAAAAZCAYAAAC2JufVAAADSElEQVR4Xq1WXYhOQRh+x1+2uGETIjdKtG78JEVKSbhAoRSSiNaFIrVEXLiQQooLSix7Y0VZuZDabZOkuHGH/JT/coNcSFrPM+/MOTNz5nzf2vZpnzPzPu8777wzZ858KzIsMGXru4VNwVjZPiN/Q2QiAyn0pnNGRs2chZZzFvDO2qBaR1PYjSmMpB0MktjJ4GWwD/oTOHfF7obYCN4F74A3wdWx2+IoOM32dOIZaLvVla+6FY7naNudezr4CjxehiQwek6AFWA3jPFMDnki7NfgJp3M8G8kOgPoDBjbWv4F92qKPE6DLIppvbYH/AaOjldSTOTRBy6K1mpkJ579gTIK/CU6xyfhIkRWWk92k1R8h/ZG4lkuuqKliZ7meSvVFW8Anwb2CPBlYJewa6xUZniWOPlFa5Wc7/QjlTIkUnrFvgpzOPDwfB0oQyzyRWVyA2aB6OTnE8dcp19J9BRbkdefk9vgOeEYw9cegWeUO3oPc74X/SgmqasszPeWSVKUc8xxele8Fr+XbLzHdEh5gH/D5teY4ge4hkPx14L+Y7EFhihnWizpTqlvNnXM21noeeCrkx6M2Yb2mfjijGwPg5CnLXlVu0Vj9cA7+IhZos4LgY9oc/rZRA9gU9wHdwQiv7yfcP2Bl9dDuLcheJchv9F5dQcLtKrTXpzq1edCp/PSy2aFxjvqCziGRhCCOyrahZPgR3BmkMgeG6PXQxb8Mm4l2irRxO52dsni4tphP8roxAdo/mbnF8pXymvGYy0GMf+pUoqTnABfSHxhHAQ/i708C/DO2hwM5k59hzVBzUIfJ3rx8i0QZ8B93unCDokt1HDHMmsSGWtXbGSds1vQ5+5tCWI4jmeFq5vn0vDRJXrAl7g4/kR1ip4tjyngA3Cqs1nsG/BaESH5wrBa0wHHVbSXYK9PA4CH4FcpdsaCufaLvqJ+8DoUnscICOJ92AP2Gt72Ro6hz9/EZsjVWocyNjsqK4ZgQBpkqlIohD7bT32NBtdJ0ZzaK+xM7P+Dg9zAdKIKauQGqBtRp2eQhhbFpo484igTLbgh8jF+9sqWRSjk1O9tN75SXFUcPuTyVv+FIsJC+MgG5RGGFuOHhEYDB1FUE/eQUJfzH+f2fyG2KwB9AAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACUAAAAZCAYAAAC2JufVAAADVElEQVR4Xq1VW6hOQRRec1C8niTknpITD+55kDrJ5XhweXMrKZdcn4giFJJyeSCh4/5CeXArpQ6FpBQpilNSboc8kQcPOr41a2b2mvln/v+c8tWamfWtb9asPXv2bCJDgG0cMDaVH43Y8YSeopGkKjgZNIpnkK/FVdnDfLVzy25AiQ8IAqXM1VRDNEBZbwajaUf/AP0z2NpEUA8rYK9hb0jmztBBt+YejIYF35iRaK8HUQR5AwPRvkK/0bHDQXai3xc0ZSyHfYWNdv4q2HfYkKAg6oMc3ei1/YVtUpoaHCUuKl59A+wHrJ8m5SNwOkNj0P6GXUkKfwz3tFC27YuOdViDvpDs0LygDlBJMPwAu5aEWkmeaJYmA8RfY0RzOAleRfOZB45ogr2zkfA89cFniROfSaRTHL9bPbEDj62/lURzUAUZ5x3Px8BPtUUVwTK1xFSSBCcrymKi4y9UVM3zrSarMYfYMVX8hvA03RNAp5EzdBf2EXYTNkjFI8ymfFEtJIeTX0UBZgTJXN4ZX1IT+i43d1GQEv2ELXSbPADtU5ICs5hJUVHh1YxnHqNLXljAOpInH0UycQvspS3KmDlehMAE13usJ1k3OfCiGIcBB0/FQZuE+eOBCfVWhHPnY9xB8uRLSXa3G2ekRVQeRjttJllXpTZ8R/GOtFecxTTmyV56ClFROVjBPdg34vtJwF8nf41jnc/wx6ZwgcqXwYczAKkXkBTb5gkdVNgBYr8iUYjpQn8iKAx1GCmgVU3l88bckYqKcQD2luLltpPc1HJ5SoTvrGVe5V7eJ9gfoWw7l+S2niRxa8fQbLOSCrtIiuIdI3sfxA9L/WFPYIutJ18H795KCVs1N79IvqrJwlv6DvEdJwn5XnqBfnMVZwl+OYbuYzTUMXxk3oO7HF1OjLg404xmJ+wi7CxsSQhVeET2rJhmlYoXPIf+NuwhyWt3GyQC1/F9eAvGH8Rz2F7jzpzPZXc2qTFC2JscFB9JbM5qiSLqhOrGigiT4m3oNRrNqxdPa8g4ARWrfjjiul1UfiGHIBdLJ+UrCyjKE5R4j+Iy9X2TEhGKSXNwmmRPe4GaeSFj3EdQZDYuyIZCpbwJWYWgTihCVmfJTMStmYmowiLuf0Ky9TTnPyobgXs9wJh8AAAAAElFTkSuQmCC>