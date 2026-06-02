# Propuesta de Migración a Arquitectura SaaS: Flashcards AI

## 1. Visión General

El objetivo de esta propuesta es evolucionar "Flashcards AI" desde una aplicación de escritorio hacia un modelo **Software as a Service (SaaS)** de nivel profesional. El sistema permitirá a múltiples usuarios procesar documentos, videos y audios mediante IA, garantizando aislamiento de datos, escalabilidad y una experiencia de usuario moderna.

## 2. Arquitectura de Referencia (Deep Research Standards)

### 2.1 Backend y Multi-tenancy (Aislamiento de Datos)
Para garantizar que un usuario nunca vea los datos de otro, adoptaremos el estándar de **Seguridad a Nivel de Fila (RLS)** en PostgreSQL:
*   **Aislamiento Declarativo:** En lugar de depender de filtros manuales en Python, usaremos `ENABLE ROW LEVEL SECURITY` en las tablas.
*   **Contexto de Sesión:** Cada transacción de FastAPI inyectará el `tenant_id` mediante `SET LOCAL session.current_tenant`, forzando a la base de datos a filtrar los datos automáticamente.
*   **PgBouncer:** Compatible con el modo de transacción para manejar miles de conexiones concurrentes.

### 2.2 Gestión de Archivos y Almacenamiento (S3/MinIO)
*   **Carga Directa (Presigned POST):** Los archivos pesados (videos, PDFs) no pasarán por el backend de FastAPI. El servidor generará una firma y el frontend los subirá directamente a S3, ahorrando recursos críticos de CPU y ancho de banda.
*   **Integración MD5:** Verificación de integridad en la subida para evitar archivos corruptos.
*   **Ciclo de Vida (Lifecycle):** Eliminación automática de archivos temporales y fragmentos de carga fallidos para optimizar costos de almacenamiento.

### 2.3 Seguridad de Identidad y Sesiones
*   **JWT en Cookies HttpOnly:** Los tokens de acceso se almacenarán en cookies protegidas, neutralizando ataques XSS.
*   **Protección CSRF:** Implementación del patrón *Double Submit Cookie* para prevenir ataques de origen cruzado en entornos web.
*   **Revocación en Redis:** Sistema de lista de denegación en tiempo real para cerrar sesiones instantáneamente ante cierres de sesión o bloqueos de cuenta.

### 2.4 Procesamiento de IA y Resiliencia
*   **Idempotencia en Celery:** Uso de bloqueos distribuidos en Redis para asegurar que una tarea de IA no se procese dos veces (ahorro de tokens).
*   **Semantic Caching:** Capa de caché vectorial en Redis para detectar consultas similares y servir respuestas instantáneas con costo cero.
*   **Circuit Breakers:** Protección contra caídas de la API de Gemini para evitar el colapso del sistema.
*   **Anonimización PII (Microsoft Presidio):** Limpieza automática de datos personales (nombres, correos) antes de que la información salga de nuestra infraestructura hacia proveedores externos.

## 3. Frontend (Angular 19+ Moderno)

*   **Zoneless:** Implementación de `provideZonelessChangeDetection()` para una detección de cambios ultrarrápida sin la sobrecarga de `zone.js`.
*   **Mobile-First:** Diseño responsivo priorizando dispositivos móviles mediante Tailwind CSS y Angular Material.
*   **Reactividad con Signals:** Adopción total de *Signal Inputs*, *Outputs*, *Computed* y *Linked Signals* para una gestión de estado predecible y granular.
*   **Resource API:** Simplificación de flujos asíncronos para la carga de datos desde FastAPI.
*   **Hidratación Incremental:** Optimización del tiempo de interactividad (TTI) cargando componentes pesados solo cuando son visibles en pantalla (*@defer*).

## 4. Observabilidad y Operaciones

*   **OpenTelemetry:** Trazabilidad de extremo a extremo (desde el click en Angular hasta la tarea en Celery).
*   **Redis Pub/Sub + SSE:** Comunicación en tiempo real del progreso de las tareas de IA (ej. "Transcribiendo video: 45%") hacia el frontend sin usar WebSockets pesados.

## 5. Hoja de Ruta Inmediata

1.  **Hito 1: Setup del Ecosistema:** Configurar Docker con Postgres (RLS), Redis y LocalStack (S3).
2.  **Hito 2: Refactor de Lógica Core:** Extraer la lógica de filtrado y generación a módulos de backend agnósticos de la UI.
3.  **Hito 3: API MVP:** Implementar el primer flujo completo (Texto -> IA -> Anki) con FastAPI y autenticación segura.
4.  **Hito 4: Frontend Angular:** Crear el tablero de control Mobile-First y conectarlo a la API.

---
**Nota sobre Buenas Prácticas:**
Se mantendrá el uso de `pnpm`, `.nvmrc`, linters (`Ruff`, `ESLint`), formateadores (`Black`, `Prettier`) y hooks de pre-commit para garantizar la calidad del código desde el inicio.
