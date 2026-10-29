# Auditoría de pruebas del backend institucional

Fecha de corte: 2026-10-29

## Alcance

Se revisaron autenticación humana y del agente, separación de canales,
invalidación por `session_version`, acceso paciente/médico, reglas de estados
de citas, límites de cancelación y serialización de auditoría.

## Cambios realizados

- Añadidas pruebas unitarias para tokens de agente limitados a pacientes
  activos, rechazo del canal interno, sesiones obsoletas e identificación del
  canal en la metadata de auditoría.
- Añadidas pruebas de los límites exactos de 24 horas y de autorización por
  rol/identidad para citas.
- Registrada la marca `integration` y clasificados los tests que usan el
  fixture HTTP con base SQLite y `TestClient`.

## Evidencia local

- `python -m pytest -q -m 'not integration'`: 37 aprobadas, 25 deseleccionadas.
- `python -m compileall -q src tests`: correcto.
- `ruff check src tests`: correcto después de ordenar imports.
- Las pruebas unitarias se ejecutan sin red ni base externa.

Las 25 pruebas de integración no se reportan como aprobadas en este entorno:
`TestClient` queda bloqueado al crear el portal de AnyIO por una restricción de
hilos del sandbox. Deben ejecutarse en CI o en un entorno nativo con el mismo
fixture SQLite antes de considerar validado el recorrido HTTP completo.

## Riesgos y pendientes

La suite no debe confundirse con una prueba de despliegue: aún requiere una
validación separada de PostgreSQL, migraciones, CORS, Vercel y la integración
server-to-server con Waylo. Como siguiente paso conviene generar cobertura de
routers y mantener el grupo `integration` como job separado para que un
bloqueo de entorno no oculte los resultados unitarios.
