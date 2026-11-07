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

## 2. Trazabilidad de casos de uso (CU01–CU12)

Relación obligatoria entre CU, especificaciones, implementación y pruebas.

| CU | Descripción | Estado (verificable) | Spec esperada | Archivos de implementación (evidencia) | Pruebas |
|---|---|---|---|---|---|
| CU01 | Registrarse e iniciar sesión | Implementado (verificable) | `specs/SPEC-01-autenticacion.md` (falta) | `backend/app/routers/auth.py`, `backend/app/models/user.py`, `backend/app/schemas/user.py`, `frontend/src/pages/Login.jsx`, `frontend/src/pages/Register.jsx`, `frontend/src/pages/ForgotPassword.jsx` | Pendiente de documentar |
| CU02 | Buscar y agregar contenido | Implementado (verificable) | `specs/SPEC-02-busqueda-agregar.md` (falta) | `frontend/src/pages/AddLibrarySelector.jsx`, `frontend/src/pages/AddLibraryBrowse.jsx`, `frontend/src/pages/BookSearch.jsx`, `backend/app/routers/items.py` | Pendiente de documentar |
| CU03 | Organizar contenidos y actualizar progreso | Implementado (verificable) | `specs/SPEC-03-progreso.md` (falta) | `backend/app/routers/items.py` (PUT /items/{id}/progress), `frontend/src/pages/ItemDetail.jsx` | Pendiente de documentar |
| CU04 | Publicar pensamientos | Implementado en código (spec pendiente) | `specs/SPEC-04-publicaciones.md` (falta) | `frontend/src/pages/CreatePost.jsx` (envía `type: "post"`), `backend/app/routers/items.py` (POST), contenido rico en `thoughts` | `backend/tests/test_posts_vs_items.py` |
| CU05 | Editar o eliminar publicaciones propias | Implementado en código (spec pendiente) | `specs/SPEC-04-publicaciones.md` (falta) | PUT y DELETE `/items/{id}` en `backend/app/routers/items.py`, edición de publicación en `frontend/src/pages/ItemDetail.jsx` | `backend/tests/test_posts_vs_items.py` |
| CU06 | Explorar publicaciones de la comunidad | Implementado en código (spec pendiente) | `specs/SPEC-04-publicaciones.md` (falta) | `frontend/src/pages/Feed.jsx` consumiendo `GET /items/feed` | `backend/tests/test_posts_vs_items.py::test_feed_keeps_posts_and_works` |
| CU07 | Comentar publicaciones | Implementado (verificable) | `specs/SPEC-05-comentarios.md` (falta) | `backend/app/models/comment.py` (incluye `created_at`), `backend/app/routers/comments.py` (GET/POST/PUT/DELETE con permisos), `frontend/src/pages/ItemDetail.jsx` | `backend/tests/test_social_likes_comments.py` |
| CU08 | Dar me gusta a publicaciones | Implementado (verificable) | `specs/SPEC-06-likes.md` (falta) | `backend/app/models/like.py` (restricción única item+usuario), `backend/app/routers/likes.py`, contadores reales en `backend/app/routers/items.py`, `frontend/src/pages/Feed.jsx`, `frontend/src/pages/ItemDetail.jsx` | `backend/tests/test_social_likes_comments.py` |
| CU09 | Puntuar y reseñar contenido | Implementado (verificable) | `specs/SPEC-05-comentarios.md` (falta) | Comentarios con `rating` en `backend/app/models/comment.py`, UI en `frontend/src/pages/ItemDetail.jsx` | `backend/tests/test_social_likes_comments.py`, `backend/tests/test_ratings_fractional.py` |
| CU10 | Consultar al asistente inteligente | Implementado (verificable) | `specs/casos-uso-chatbot.md` (completa) | `backend/app/routers/chat.py`, `backend/app/services/assistant.py`, `backend/app/services/recommender.py`, `frontend/src/pages/Chatbot.jsx`, `frontend/src/App.jsx` | `backend/tests/test_chat_recommend.py`, `backend/tests/test_chat_contextual.py`, `backend/tests/test_chat_isolation.py` |
| CU11 | Agregar y gestionar amigos | Implementado (verificable) | `specs/SPEC-11-amigos-notificaciones.md` (completa) | `backend/app/models/friendship.py`, `backend/app/routers/friends.py`, `frontend/src/pages/Friends.jsx`, `frontend/src/pages/UserPublicProfile.jsx` | `backend/tests/test_friends_notifications.py`, `backend/tests/test_migrate_friends.py` |
| CU12 | Consultar notificaciones | Implementado (verificable) | `specs/SPEC-11-amigos-notificaciones.md` (completa) | `backend/app/models/notification.py`, `backend/app/services/notifications.py`, `backend/app/routers/notifications.py`, `frontend/src/pages/Notifications.jsx`, `frontend/src/components/Navbar.jsx` | `backend/tests/test_friends_notifications.py` |

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

### Recuperación de contraseña
- Endpoints: `POST /auth/forgot-password` y `POST /auth/reset-password`.
- El token se genera con `secrets.token_urlsafe(32)`, vence en 30 minutos, es de un solo uso y solo se guarda su hash SHA-256 en `password_reset_tokens`.
- La respuesta de solicitud es siempre genérica, exista o no el correo.
- Rate limiting por IP y por correo; con varios workers hace falta un store compartido (Redis).
- El correo se envía por SMTP real. Si `SMTP_HOST` o `SMTP_FROM_EMAIL` faltan, la API devuelve `503` en lugar de simular el envío.
- Nunca registrar contraseñas, tokens ni enlaces de recuperación en logs.
- **Invalidación de sesiones:** cada JWT incluye el claim `ver`. Al restablecer la contraseña se incrementa `users.token_version`, por lo que todos los tokens emitidos antes del cambio dejan de validar en `get_current_user`. Los JWT anteriores a esta funcionalidad decodifican `ver=0`, compatible con usuarios existentes hasta su primer reset.
- Migración aditiva: `python backend/migrate_password_reset.py` (agrega `users.token_version` y crea `password_reset_tokens`; no borra datos).

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
- Gestión de items con tipos (book/movie/series/music/paper/post)
- Seguimiento de progreso para libros
- Likes con contador real, estado por usuario y restricción de un like activo
- Comentarios con autor, avatar, fecha, permisos de edición/eliminación y bloqueo de comentarios vacíos
- Feed conectado a BD real con contadores de likes y comentarios
- Búsqueda con Open Library
- Temas personalizables por usuario
- Chatbot con LLM API (backend)
- Animación entrada a librería con prefers-reduced-motion
- Amistades con solicitudes, aceptación, rechazo y eliminación
- Notificaciones de amistad, me gusta y comentarios con lectura individual y masiva

**NO verificadas/completas:**
- Specs formales de CU07/CU08/CU09 - faltan
- Edición completa de publicaciones (CU05) - implementada para publicaciones (`type=post`)
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
