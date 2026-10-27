# AGENTS.md - Guía principal para agentes de IA

## Proyecto
ReeStack - Red social cultural para registrar libros, películas, series, música y papers, compartir pensamientos y reseñas.

## Stack
- Frontend: React + Vite
- Backend: Python + FastAPI + SQLite
- Auth: JWT
- Temas: CSS Variables personalizables

## Estructura
Ver README.md para estructura completa.

## Convenciones originales (conservadas)
- No agregar "Co-Authored-By" a commits
- Mantener estilo editorial (serif para títulos, sin cursiva)
- Usar paleta de colores con CSS variables
- No romper autenticación, frontend, backend o BD
- Respetar `prefers-reduced-motion`

## Comandos
- Backend: `cd backend && .\.venv\Scripts\python.exe -m uvicorn main:app --reload`
- Frontend: `cd frontend && npm run dev`

## Reglas originales (conservadas)
- Solo modificar lo solicitado
- Verificar antes de romper funcionalidad existente
- Documentar cambios importantes

## 1. Desarrollo guiado por especificaciones (Spec-Driven Development)

Todo desarrollo debe partir de una especificación en `specs/`.

### Uso de specs
- **Antes de implementar:** leer la spec correspondiente, criterios de aceptación y casos de uso relacionados.
- **Durante la implementación:** seguir estrictamente lo definido en la spec.
- **Tras implementar:** validar contra criterios de aceptación y actualizar trazabilidad.
- **Si no existe spec:** proponerla pero NO crearla sin aprobación explícita. No asumir funcionalidades.
- **Archivo fuente:** `specs/` es la fuente de verdad para funcionalidades nuevas o modificadas.

## 2. Trazabilidad de casos de uso (CU01–CU10)

Relación obligatoria entre CU, especificaciones, implementación y pruebas.

| CU | Descripción | Estado (verificable) | Spec esperada | Archivos de implementación (evidencia) | Pruebas |
|---|---|---|---|---|---|
| CU01 | Registrarse e iniciar sesión | Implementado (verificable) | `specs/SPEC-01-autenticacion.md` (falta) | `backend/app/routers/auth.py`, `backend/app/models/user.py`, `backend/app/schemas/user.py`, `frontend/src/pages/Login.jsx`, `frontend/src/pages/Register.jsx`, `frontend/src/pages/ForgotPassword.jsx` | Pendiente de documentar |
| CU02 | Buscar y agregar contenido | Implementado (verificable) | `specs/SPEC-02-busqueda-agregar.md` (falta) | `frontend/src/pages/AddLibrarySelector.jsx`, `frontend/src/pages/AddLibraryBrowse.jsx`, `frontend/src/pages/BookSearch.jsx`, `backend/app/routers/items.py` | Pendiente de documentar |
| CU03 | Organizar contenidos y actualizar progreso | Implementado (verificable) | `specs/SPEC-03-progreso.md` (falta) | `backend/app/routers/items.py` (PUT /items/{id}/progress), `frontend/src/pages/ItemDetail.jsx` | Pendiente de documentar |
| CU04 | Publicar pensamientos | Parcialmente implementado (verificable) | `specs/SPEC-04-publicaciones.md` (falta) | Campo `thoughts` en `backend/app/models/item.py`, usado en formularios. No hay flujo completo de "publicaciones" separado. | Pendiente de documentar |
| CU05 | Editar o eliminar publicaciones propias | Parcialmente implementado (verificable) | `specs/SPEC-04-publicaciones.md` (falta) | DELETE `/items/{id}` en `backend/app/routers/items.py`. No existe PUT/editar. | Pendiente de documentar |
| CU06 | Explorar publicaciones de la comunidad | Parcialmente implementado (verificable) | `specs/SPEC-04-publicaciones.md` (falta) | `frontend/src/pages/Feed.jsx` con datos mock, no conectado a BD. | Pendiente de documentar |
| CU07 | Comentar publicaciones | Implementado (verificable) | `specs/SPEC-05-comentarios.md` (falta) | `backend/app/models/comment.py`, `backend/app/routers/comments.py`, `frontend/src/pages/ItemDetail.jsx` | Pendiente de documentar |
| CU08 | Dar me gusta a publicaciones | Pendiente (sin evidencia) | `specs/SPEC-06-likes.md` (falta) | Sin modelo/router/frontend verificable | Pendiente de documentar |
| CU09 | Puntuar y reseñar contenido | Implementado (verificable) | `specs/SPEC-05-comentarios.md` (falta) | Comentarios con `rating` en `backend/app/models/comment.py`, UI en `frontend/src/pages/ItemDetail.jsx` | Pendiente de documentar |
| CU10 | Consultar al asistente inteligente | Implementado (verificable) | `specs/casos-uso-chatbot.md` (existe parcial) | `backend/app/routers/chat.py`, `frontend/src/pages/Chatbot.jsx`, `frontend/src/App.jsx` | Pendiente de documentar |

**Regla:** Solo marcar como "Implementado" con evidencia directa en código. "Parcialmente implementado" o "Pendiente" si falta funcionalidad crítica.

## 3. Flujo de trabajo para agentes

Todo agente debe seguir este orden obligatoriamente:

1. **Análisis** - Leer AGENTS.md, README.md, spec relevante (si existe), archivos afectados. Verificar estado actual sin asumir.
2. **Planificación** - Listar archivos a tocar, riesgos, verificación de no romper funcionalidades existentes.
3. **Aprobación** - Presentar plan y esperar aprobación antes de modificar. (Según instrucción del usuario)
4. **Implementación** - Solo modificar lo aprobado. Respetar convenciones, diseño editorial, variables CSS, `prefers-reduced-motion`.
5. **Validación** - Ejecutar verificaciones (sección 4). Comprobar auth, rutas, CORS, imports.
6. **Documentación** - Completar reporte con archivos modificados, funcionalidades, pruebas ejecutadas y estado.

## 4. Validaciones y pruebas obligatorias

Antes de dar por finalizada cualquier tarea:

### Frontend
- [ ] Compilación/imports sin errores obvios
- [ ] Rutas funcionan y están protegidas correctamente
- [ ] Diseño respeta variables CSS y estilo editorial
- [ ] Animaciones respetan `prefers-reduced-motion`
- [ ] No se rompe navegación existente

### Backend
- [ ] Imports correctos
- [ ] Endpoints existentes siguen funcionando
- [ ] CORS mantiene orígenes permitidos
- [ ] Validaciones Pydantic correctas
- [ ] No se rompen modelos/schemas existentes

### Autenticación
- [ ] Login/register funcionan
- [ ] JWT se valida correctamente
- [ ] Rutas protegidas mantienen protección
- [ ] Contraseñas siguen hasheadas

### Base de datos
- [ ] `reestack.db` no se borra/modifica estructura sin justificación y aprobación
- [ ] No se eliminan tablas/columnas
- [ ] Migraciones solo si estrictamente necesarias y aprobadas
- [ ] Datos existentes se preservan

## 5. Seguridad

### JWT
- Usar `SECRET_KEY` desde variables de entorno en producción
- Mantener algoritmo configurado
- No exponer tokens en logs
- Validar tokens en endpoints protegidos

### Contraseñas
- Siempre hasheadas con bcrypt/passlib
- Mantener validación de contraseña fuerte en registro
- No almacenar contraseñas en texto plano

### Variables de entorno
- Claves API (LLM) SOLO en backend, NUNCA en frontend
- Usar `.env` (ignorado por git) y `.env.example` como referencia
- No commitear credenciales
- Validar presencia de variables críticas

### Endpoints
- Proteger endpoints que requieran autenticación
- No exponer información sensible en errores
- Mantener CORS restrictivo a orígenes conocidos
- Validar datos con Pydantic

## 6. Documentación de cambios

Cada agente DEBE reportar al finalizar:

- **Archivos modificados:** lista exacta con rutas
- **Archivos creados:** lista exacta con rutas
- **Funcionalidades implementadas:** solo las verificables
- **Funcionalidades afectadas:** verificar que no se rompieron
- **Pruebas ejecutadas:** qué se verificó y resultado
- **Riesgos:** si hay algún riesgo identificado
- **Estado:** completado/parcial/bloqueado

## 7. Criterios de aceptación

Una funcionalidad se considera COMPLETA solo si:
- [ ] Existe spec aprobada (o está explícitamente solicitada y documentada)
- [ ] Implementación verificada en código
- [ ] Criterios de aceptación de la spec cumplidos
- [ ] Validaciones de sección 4 pasadas
- [ ] No rompe funcionalidades existentes
- [ ] Documentación actualizada
- [ ] Sin dependencias nuevas sin aprobación
- [ ] Respeta convenciones y diseño

## 8. Funcionalidades implementadas (verificables)

**Verificadas en código:**
- Autenticación JWT (registro/login/recuperación)
- Gestión de items con tipos (book/movie/series/music/paper)
- Seguimiento de progreso para libros
- Comentarios con rating y spoilers
- Búsqueda con Open Library
- Temas personalizables por usuario
- Feed con datos mock (parcial)
- Chatbot con LLM API (backend)
- Animación entrada a librería con prefers-reduced-motion

**NO verificadas/completas:**
- Likes (CU08) - sin evidencia
- Edición completa de publicaciones (CU05) - solo DELETE
- Feed conectado a BD real (CU06) - usa mocks
- Sistema completo de "publicaciones" vs items

## 9. Protección de funcionalidades existentes

**PROHIBIDO:**
- Modificar auth, CORS, rutas protegidas sin justificación crítica y aprobación
- Eliminar o renombrar archivos sin aprobación
- Cambiar estructura de BD sin aprobación
- Modificar paleta/variables CSS globales sin mantener compatibilidad
- Romper animación con prefers-reduced-motion
- Exponer claves API en frontend
- Instalar dependencias sin aprobación
- Modificar frontend/backend/BD sin necesidad

**OBLIGATORIO:**
- Verificar funcionalidad antes y después de cambios
- Mantener retrocompatibilidad
- Preservar datos en `reestack.db`
- Mantener estilo editorial
- Seguir convenciones originales
