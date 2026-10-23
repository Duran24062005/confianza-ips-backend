# Plan técnico — Sistema IPS Confianza

## 1. Comprensión del proyecto

Construiremos una aplicación institucional autónoma para una IPS ficticia colombiana, con:

- Backend FastAPI + PostgreSQL en Neon.
- Frontend React + Vite + TypeScript.
- Dos repositorios Git independientes y dos proyectos Vercel.
- Persistencia real, autenticación, roles, auditoría y reglas de negocio.
- Sin scraping, Playwright interno ni endpoints bypass; el agente usa el contrato REST autenticado y auditado.

Estado actual inspeccionado:

- `confianza-ips-backend` es el único repositorio Git válido existente.
- Actualmente solo contiene un proyecto Python mínimo, sin API ni base de datos.
- No existe frontend.
- La carpeta raíz no debe convertirse en repositorio compartido.

## 2. Análisis de requisitos

### Roles

- Administrador: usuarios, catálogos, pacientes, médicos, agendas, citas, auditoría y configuración.
- Recepcionista: pacientes, búsqueda, disponibilidad, programación, reprogramación y cancelación.
- Médico: agenda propia, pacientes autorizados, atenciones y notas clínicas.
- Paciente: perfil, citas, solicitudes, cancelaciones permitidas e historial disponible.

### Reglas de negocio principales

- Pacientes, médicos, servicios y usuarios se desactivan mediante eliminación lógica.
- Las citas nunca se eliminan físicamente.
- No se permiten citas en fechas pasadas.
- No se permiten pacientes o médicos inactivos.
- No se permiten reservas duplicadas ni solapamientos.
- Una cita completada no puede reprogramarse.
- Las transiciones de estado quedan auditadas.
- Las notas clínicas no se sobrescriben silenciosamente; las correcciones crean una nueva versión o adenda.
- Los horarios se calculan desde información persistida.
- La zona horaria institucional será `America/Bogota`; las fechas se almacenarán en UTC.

### Requisitos no funcionales

- Validación y autorización siempre en backend.
- Contraseñas con Argon2id.
- JWT Bearer de corta duración, almacenado solo en memoria del frontend; al recargar la página se solicita autenticación nuevamente.
- CORS limitado a los orígenes configurados.
- Migraciones versionadas.
- Pruebas automatizadas de dominio, API, persistencia y flujo frontend-backend.
- Datos exclusivamente ficticios.

## 3. Decisiones técnicas

### Frontend seleccionado: React + Vite

Se elige React + Vite porque el sistema será un dashboard autenticado que consume una API independiente y no necesita SSR ni Server Actions.

Stack propuesto:

- React + TypeScript + Vite.
- React Router.
- TanStack Query para estado remoto.
- React Hook Form + Zod para formularios.
- Tailwind CSS y componentes accesibles.
- Vitest/Testing Library para pruebas.
- Playwright para validaciones end-to-end.

Next.js queda documentado como alternativa futura, pero no se incorporará para evitar duplicar responsabilidades con FastAPI.

### Backend seleccionado

- FastAPI.
- SQLAlchemy 2.0 síncrono.
- Psycopg 3.
- Alembic.
- Pydantic Settings.
- PyJWT.
- `pwdlib` con Argon2.
- Pytest + HTTPX.

Se utilizará un monolito modular: módulos separados por dominio, pero un único servicio desplegable.

### Autenticación

Endpoints iniciales:

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout` como operación de cliente y registro de auditoría cuando aplique.

El JWT incluirá identidad, rol, expiración y versión de sesión. El backend invalidará usuarios inactivos y rechazará tokens expirados. No se implementará refresh token en el MVP.

### Contrato frontend-backend

El backend será la fuente de verdad mediante OpenAPI. El frontend consumirá un cliente HTTP tipado, con tipos generados o sincronizados desde el esquema OpenAPI.

Ningún repositorio importará código del otro.

### Vercel y Neon

Vercel permite desplegar FastAPI mediante su runtime Python, con soporte para Python 3.12, 3.13 y 3.14. El entrypoint se configurará mediante `tool.vercel.entrypoint` y los límites de ejecución mediante `vercel.json`. [Documentación oficial de Vercel](https://vercel.com/docs/functions/runtimes/python)

El backend será una función HTTP única. No se dependerá de procesos persistentes, workers permanentes ni tareas largas. Migraciones y seed se ejecutarán explícitamente desde desarrollo o CI, nunca durante el arranque de cada request.

La aplicación utilizará la URL pooled de Neon y las migraciones utilizarán la conexión directa cuando sea necesario. Neon recomienda pooling para aplicaciones serverless con múltiples conexiones. [Documentación de Neon sobre pooling](https://neon.com/blog/how-to-minimise-the-impact-of-database-latency) y [documentación de SQLAlchemy para PostgreSQL](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html).

Por decisión del usuario, desarrollo, preview y demostración utilizarán la misma base Neon y los mismos datos ficticios. Se añadirá un seed idempotente y se prohibirán pruebas destructivas contra los datos de demostración.

## 4. Arquitectura conceptual

### Frontend

Responsable de:

- Navegación, layouts y vistas por rol.
- Formularios y validaciones de experiencia.
- Tablas, filtros, estados de carga y errores.
- Gestión del JWT en memoria.
- Consumo de endpoints REST.
- No contiene reglas críticas de autorización ni disponibilidad.

### Backend

Responsable de:

- Autenticación y autorización.
- Validación de dominio.
- Operaciones transaccionales.
- Cálculo de disponibilidad.
- Integridad de citas.
- Auditoría.
- Serialización de respuestas.
- Generación de documentos ficticios.

Estructura lógica:

```text
confianza-ips-backend/
├── src/confianza_ips_backend/
│   ├── api/
│   ├── auth/
│   ├── core/
│   ├── db/
│   ├── domains/
│   │   ├── users/
│   │   ├── patients/
│   │   ├── professionals/
│   │   ├── catalog/
│   │   ├── schedules/
│   │   ├── appointments/
│   │   ├── clinical/
│   │   ├── authorizations/
│   │   ├── documents/
│   │   ├── dashboard/
│   │   └── audit/
│   └── main.py
├── migrations/
├── tests/
└── docs/
```

## 5. Modelo conceptual de datos

Entidades principales:

- `institutions`
- `sites`
- `users`
- `roles`
- `patients`
- `doctors`
- `specialties`
- `services`
- `doctor_specialties`
- `doctor_services`
- `doctor_schedules`
- `schedule_blocks`
- `appointments`
- `appointment_status_history`
- `clinical_encounters`
- `clinical_notes`
- `authorizations`
- `documents`
- `audit_events`

Relaciones relevantes:

- Una institución tiene una o más sedes.
- Un médico puede tener varias especialidades y servicios.
- Un paciente puede tener muchas citas, autorizaciones y atenciones.
- Una cita relaciona paciente, médico, servicio y sede.
- Una atención clínica nace de una cita completada.
- Toda operación relevante puede producir un evento de auditoría.

### Concurrencia de citas

La disponibilidad se calculará con horarios, bloqueos y citas persistidas.

La base de datos aplicará una restricción de exclusión PostgreSQL sobre rangos de tiempo para evitar solapamientos simultáneos de:

- Médico.
- Paciente.
- Estados activos de cita.

La creación y reprogramación se ejecutarán dentro de transacciones. Si dos solicitudes compiten por el mismo horario, una será aceptada y la otra recibirá conflicto HTTP `409`.

## 6. Definición del MVP

### Obligatorio

- Autenticación y roles.
- Gestión de usuarios básicos.
- Pacientes con eliminación lógica.
- Médicos, especialidades y servicios.
- Horarios y bloqueos.
- Disponibilidad calculada desde backend.
- Creación, consulta, confirmación, reprogramación, cancelación, completado e inasistencia de citas.
- Historial de cambios de citas.
- Historial administrativo del paciente.
- Notas clínicas ficticias para médicos.
- Dashboard con indicadores reales.
- Auditoría.
- Datos seed sintéticos.
- Documento imprimible de confirmación de cita, claramente marcado como ficticio.
- Despliegue independiente en Vercel.

### Secundario

- Autorizaciones administrativas.
- Certificados ficticios descargables como PDF.
- Archivo de documentos.
- Filtros avanzados de auditoría.
- Reglas configurables de cancelación.
- Mejoras visuales avanzadas del calendario.

### Expansiones futuras

- Activación segura del agente y acceso paciente-scoped.
- Notificaciones por correo o SMS.
- Firma digital.
- Carga de archivos clínicos.
- Integraciones con EPS reales.
- Historia clínica interoperable.
- Multiinstitución avanzada.

## 7. Plan de implementación

### Etapa 1 — Base técnica y documentación

Duración: 1–2 días.

- Crear PRD y arquitectura.
- Completar estructura FastAPI.
- Configurar variables de entorno.
- Configurar Alembic, SQLAlchemy y pruebas.
- Crear el repositorio frontend independiente.

Aceptación: ambos proyectos arrancan localmente y tienen README operativo.

### Etapa 2 — Usuarios y autenticación

Duración: 3–4 días.

- Usuarios, roles y contraseñas.
- Login JWT.
- Dependencias de autorización.
- Seed de usuarios demo.

Aceptación: cada rol puede iniciar sesión y acceder únicamente a sus endpoints.

### Etapa 3 — Catálogos y pacientes

Duración: 4–5 días.

- Institución y sede.
- Especialidades, servicios y médicos.
- CRUD de pacientes.
- Desactivación y reactivación.
- Auditoría administrativa.

Aceptación: una modificación persiste y aparece en consultas posteriores.

### Etapa 4 — Agendas y citas

Duración: 5–6 días.

- Horarios laborales.
- Bloqueos.
- Disponibilidad.
- Citas y transiciones de estado.
- Conflictos concurrentes.
- Reprogramación y cancelación.

Aceptación: nunca se pueden reservar horarios ocupados o inválidos.

### Etapa 5 — Historial clínico, dashboard y documentos

Duración: 4–5 días.

- Atenciones.
- Notas clínicas ficticias.
- Historial administrativo.
- Indicadores.
- Documento imprimible de cita.
- Auditoría consultable.

Aceptación: cada dato mostrado proviene de PostgreSQL.

### Etapa 6 — Frontend completo y validación

Duración: 5–6 días.

- Vistas diferenciadas por rol.
- Formularios y tablas.
- Manejo de errores y carga.
- Flujo end-to-end.
- Seed final y documentación de demo.
- Preview y despliegue en Vercel.

Estimación total: aproximadamente cinco semanas calendario, con backend y frontend trabajando en paralelo.

## 8. Repositorios y despliegue

Repositorios previstos:

```text
ConfianzaIPS/
├── confianza-ips-backend/   # repositorio Git independiente existente
└── confianza-ips-frontend/  # nuevo repositorio Git independiente
```

No se inicializará ni utilizará un repositorio Git compartido en la raíz.

Variables principales:

Backend:

- `DATABASE_URL`
- `DATABASE_URL_UNPOOLED`
- `JWT_SECRET`
- `JWT_EXPIRE_MINUTES`
- `CORS_ORIGINS`
- `APP_ENV`

Frontend:

- `VITE_API_BASE_URL`

Proceso local:

1. Ejecutar migraciones.
2. Ejecutar seed idempotente.
3. Levantar FastAPI.
4. Levantar Vite.
5. Probar el flujo completo desde navegador.

Proceso de publicación:

1. Ejecutar pruebas.
2. Verificar migraciones pendientes.
3. Publicar backend.
4. Configurar la URL pública del backend en Vercel.
5. Configurar CORS con el dominio frontend.
6. Publicar frontend.
7. Ejecutar smoke tests autenticados.

## 9. Plan de pruebas y validación

### Backend

- Login válido e inválido.
- Usuario inactivo.
- Matriz completa de roles y permisos.
- CRUD de pacientes.
- Eliminación lógica.
- Reactivación.
- Persistencia entre requests.
- Creación de citas.
- Horario ocupado.
- Médico o paciente inactivo.
- Fecha pasada.
- Reprogramación.
- Cancelación.
- Cita completada.
- Inasistencia.
- Conflictos concurrentes.
- Historial clínico restringido.
- Auditoría de operaciones.
- Migraciones desde base vacía.

### Frontend

- Login y cierre de sesión.
- Navegación por rol.
- Formularios inválidos.
- Estados de carga.
- Estados vacíos.
- Errores HTTP.
- Filtros y búsquedas.
- Flujo de agendamiento.
- Reprogramación y cancelación.
- Renderización responsive.

### Validación integral

Se demostrará el siguiente flujo:

1. Crear o usar un paciente ficticio.
2. Consultar disponibilidad real.
3. Crear una cita.
4. Verificar que el horario queda ocupado.
5. Consultar la cita desde paciente, recepción y médico.
6. Reprogramarla o cancelarla.
7. Consultar el historial de cambios.
8. Verificar el evento de auditoría directamente mediante la API.
9. Confirmar persistencia tras reiniciar o realizar nuevas requests.

## 10. Riesgos, preguntas y supuestos

Riesgos principales:

- Compartir una base Neon entre desarrollo y demo puede contaminar datos.
- Vercel no es adecuado para procesos permanentes o trabajos prolongados.
- Los conflictos de agenda requieren pruebas reales contra PostgreSQL.
- Los datos clínicos, aunque ficticios, deben tratarse como sensibles.
- La ausencia de refresh token hará que el usuario vuelva a autenticarse al recargar la aplicación.
- Las migraciones no deben ejecutarse automáticamente durante requests.

Supuestos adoptados:

- La IPS usa `America/Bogota`.
- Pacientes pueden solicitar citas; recepción o administración las confirma.
- El paciente puede cancelar o reprogramar hasta 24 horas antes.
- Administración puede corregir estados con auditoría.
- El MVP generará documentos HTML imprimibles; el PDF será secundario.
- El frontend se llamará `confianza-ips-frontend`.
- La misma base Neon contendrá los datos de desarrollo y demostración, con seed idempotente y sin datos reales.

Preguntas no bloqueantes para una revisión posterior:

- Nombre y dirección ficticia de la sede.
- Credenciales demo definitivas.
- Texto legal visible en documentos ficticios.
- Catálogo inicial de especialidades y servicios.
- Si el administrador podrá consultar notas clínicas o solo auditoría administrativa.

No se modificaron archivos ni repositorios durante esta planificación.
