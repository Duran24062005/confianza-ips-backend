# Regla de afiliación y edición del perfil del paciente

## Problema y objetivo

El perfil del paciente permitía modificar la EPS asociada a su registro. En esta demostración, la afiliación determina el contexto institucional y el acceso a los servicios de Confianza IPS; el paciente no debe poder cambiarla desde su perfil.

## Alcance

- El paciente puede consultar su EPS y actualizar sus datos personales y de contacto desde su perfil.
- La EPS se muestra como información de afiliación no editable para el paciente.
- El endpoint `PATCH /api/v1/patients/me` rechaza solicitudes que intenten cambiar la EPS.
- El personal autorizado conserva la gestión institucional de los datos del paciente mediante `PUT /api/v1/patients/{patient_id}`.
- La documentación técnica permanece disponible en la ruta pública `/docs`, pero no aparece en el menú de trabajo.

## Implementación y validación

El frontend muestra la EPS registrada en un campo de solo lectura e informa al paciente que debe contactar a la institución para corregirla. El backend compara la EPS recibida con la afiliación actual antes de aplicar cambios; si difiere, responde `403` y no modifica el registro.

Esta regla evita depender exclusivamente de la interfaz: las solicitudes directas a la API también quedan sujetas a la autorización. La interfaz mantiene la ruta `/docs` para consulta técnica directa y retira su acceso del sidebar.

## Actores, datos y permisos

- **Paciente:** lectura de su EPS; edición de sus datos personales y de contacto, excepto afiliación.
- **Personal autorizado:** gestión institucional de los datos del paciente, incluida la afiliación.
- **Equipo técnico:** acceso a la documentación API en `/docs`.

La afiliación es dato administrativo que participa en la autorización de servicios. Su cambio debe realizarse por el canal institucional, no por autoedición del paciente.

## Riesgos y límites

La demostración no integra una fuente externa que confirme afiliaciones en tiempo real. La regla evita que el propio paciente cambie el valor, pero la veracidad de los datos iniciales depende del personal que administra la ficha. Una transferencia real entre EPS/IPS requeriría un flujo institucional de verificación y actualización.
