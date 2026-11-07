# SPEC-11: Amigos y notificaciones

## Estado

Implementado (verificable en código y pruebas).

## Objetivo

Incorporar relaciones de amistad entre usuarios y un centro de notificaciones
que informe solicitudes de amistad, me gusta y comentarios sobre el contenido
propio.

## Alcance

Incluye:

- Envío, aceptación, rechazo y cancelación de amistades.
- Listado de amigos y solicitudes recibidas/enviadas.
- Notificaciones persistentes por solicitud de amistad, aceptación, me gusta y
  comentario.
- Marca de lectura individual y masiva.
- Badge de notificaciones no leídas en la barra de navegación.

No incluye:

- Mensajería privada.
- Bloqueo de usuarios.
- Notificaciones por correo o push.
- Notificaciones de nuevos seguidores (no existe el concepto de seguimiento).

## CU11: Gestionar amistades

### Actor

Usuario autenticado.

### Flujo principal

1. El usuario consulta el perfil público de otro usuario.
2. Envía una solicitud de amistad.
3. El destinatario ve la solicitud en `/friends` y en `/notifications`.
4. El destinatario acepta o rechaza la solicitud.
5. Si acepta, ambos usuarios aparecen en la lista de amigos del otro.

### Reglas

- Un usuario no puede enviarse una solicitud a sí mismo.
- No puede existir más de una relación por par de usuarios.
- La base de datos garantiza la unicidad del par sin importar la dirección:
  índice único sobre `min(requester_id, addressee_id)` y
  `max(requester_id, addressee_id)`.
- Si el destinatario ya había enviado una solicitud al emisor, enviar la
  solicitud inversa la acepta automáticamente en lugar de crear otra fila.
- Si dos solicitudes del mismo par compiten en simultáneo, la que pierde el
  `INSERT` captura `IntegrityError`, revierte su transacción y resuelve contra
  la fila ganadora. Nunca responde 500 por duplicados.
- Aceptar y rechazar usan un `UPDATE` condicionado a `status = pending`, así
  que una segunda respuesta simultánea no duplica notificaciones.
- Solo el destinatario puede aceptar o rechazar una solicitud.
- Una solicitud rechazada puede volver a enviarse; se reutiliza la misma fila.
- Cualquiera de los dos amigos puede eliminar la amistad.
- Las solicitudes pendientes y las amistades se listan únicamente para sus
  participantes.

### Criterios de aceptación

- [x] Enviar una solicitud crea una relación `pending` y una notificación
      `friend_request` para el destinatario.
- [x] Aceptar una solicitud crea una amistad visible para ambos y una
      notificación `friend_accepted` para el emisor.
- [x] Rechazar una solicitud no crea amistad.
- [x] El envío inverso sobre una solicitud pendiente la acepta.
- [x] Un tercero no puede aceptar ni rechazar una solicitud ajena.
- [x] Eliminar una amistad la quita de ambas listas.

## CU12: Consultar notificaciones

### Actor

Usuario autenticado.

### Eventos que generan notificaciones

| Evento | Tipo | Destinatario |
| --- | --- | --- |
| Solicitud de amistad enviada | `friend_request` | Destinatario de la solicitud |
| Solicitud de amistad aceptada | `friend_accepted` | Emisor original |
| Me gusta sobre contenido ajeno | `like` | Dueño del ítem |
| Comentario sobre contenido ajeno | `comment` | Dueño del ítem |

### Reglas

- Nunca se genera una notificación para el propio actor.
- Los me gusta se deduplican mientras la notificación esté sin leer, para
  evitar ruido al alternar el like.
- Cada comentario genera una notificación independiente.
- Cada usuario solo puede leer y marcar sus propias notificaciones.
- Una notificación de contenido enlaza al ítem; una de amistad enlaza a
  `/friends` o al perfil del actor.

### Criterios de aceptación

- [x] El contador de no leídas refleja solo las notificaciones del usuario.
- [x] Marcar una notificación como leída actualiza su estado.
- [x] Marcar todas como leídas deja el contador en cero.
- [x] Las notificaciones de otros usuarios no son visibles ni modificables.
- [x] Un me gusta propio o un comentario propio no generan notificación.

## Modelo de datos

Migración aditiva: `backend/migrate_friends_notifications.py`. No se eliminan
tablas, columnas ni filas existentes.

### `friendships`

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | INTEGER | PK |
| `requester_id` | INTEGER | FK `users.id` |
| `addressee_id` | INTEGER | FK `users.id` |
| `status` | TEXT | `pending`, `accepted`, `rejected` |
| `created_at` | DATETIME | Fecha de la solicitud |
| `responded_at` | DATETIME | Fecha de respuesta |

Restricciones: única por `(requester_id, addressee_id)`, única por par no
ordenado mediante `uq_friendship_canonical_pair`
(`UNIQUE (min(requester_id, addressee_id), max(requester_id, addressee_id))`) y
`requester_id <> addressee_id`.

### `notifications`

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | INTEGER | PK |
| `user_id` | INTEGER | FK `users.id`, destinatario |
| `actor_id` | INTEGER | FK `users.id`, quien generó el evento |
| `type` | TEXT | `friend_request`, `friend_accepted`, `like`, `comment` |
| `item_id` | INTEGER | FK `items.id`, opcional |
| `comment_id` | INTEGER | FK `comments.id`, opcional |
| `is_read` | BOOLEAN | Por defecto `false` |
| `created_at` | DATETIME | Fecha del evento |

## API

### Amigos

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/friends` | Lista de amigos |
| GET | `/friends/requests` | Solicitudes recibidas pendientes |
| GET | `/friends/requests/sent` | Solicitudes enviadas pendientes |
| GET | `/friends/status/{user_id}` | Estado de la relación con un usuario |
| POST | `/friends/requests/{user_id}` | Enviar solicitud |
| POST | `/friends/requests/{request_id}/accept` | Aceptar solicitud |
| POST | `/friends/requests/{request_id}/reject` | Rechazar solicitud |
| DELETE | `/friends/{user_id}` | Eliminar amistad |

Estados posibles de `/friends/status/{user_id}`: `none`, `pending_outgoing`,
`pending_incoming`, `friends`, `rejected`, `self`.

### Notificaciones

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/notifications` | Listado paginado; admite `unread_only` |
| GET | `/notifications/unread-count` | Cantidad de no leídas |
| POST | `/notifications/{notification_id}/read` | Marcar una como leída |
| POST | `/notifications/read-all` | Marcar todas como leídas |

Todos los endpoints requieren JWT.

## Frontend

- `/friends`: solicitudes recibidas, amigos y solicitudes enviadas.
- `/notifications`: listado, filtro de no leídas y acciones de lectura.
- Navbar: accesos a Amigos y Notificaciones, con badge de no leídas que se
  actualiza cada 30 segundos, al recuperar el foco y al marcar notificaciones
  como leídas. El polling es intencional: no se usan WebSockets.
- Perfil público: acción contextual según el estado de la relación.
- Estilos con variables CSS existentes y sin animaciones que ignoren
  `prefers-reduced-motion`.

## Pruebas

`backend/tests/test_friends_notifications.py` cubre:

- Flujo de solicitud, aceptación, rechazo, reenvío y eliminación.
- Aceptación automática por solicitud inversa.
- Permisos de destinatario y aislamiento entre usuarios.
- Notificaciones por amistad, like y comentario.
- Deduplicación de likes no leídos y ausencia de auto-notificaciones.
- Contador, lectura individual y lectura masiva.
- Autenticación obligatoria.
- Restricción única a nivel de base de datos para filas duplicadas y espejadas.
- Simulación de carrera: solicitud duplicada (400 controlado) y solicitudes
  cruzadas (aceptación automática, una sola fila).
- Idempotencia de aceptar y rechazar.

`backend/tests/test_migrate_friends.py` cubre la migración:

- Creación del índice único canónico sin tocar filas existentes.
- Bloqueo de filas espejadas después de migrar.
- Idempotencia de la migración.
- Negativa a crear el índice si hay pares duplicados heredados (no borra datos).

`backend/tests/test_profiles.py` cubre autenticación, perfiles, búsqueda y
perfil público, que se ejecutan en la suite completa para detectar regresiones.

## Trazabilidad

| CU | Implementación | Pruebas |
| --- | --- | --- |
| CU11 Amigos | `backend/app/models/friendship.py`, `backend/app/routers/friends.py`, `frontend/src/pages/Friends.jsx`, `frontend/src/pages/UserPublicProfile.jsx` | `backend/tests/test_friends_notifications.py`, `backend/tests/test_migrate_friends.py` |
| CU12 Notificaciones | `backend/app/models/notification.py`, `backend/app/services/notifications.py`, `backend/app/routers/notifications.py`, `frontend/src/pages/Notifications.jsx`, `frontend/src/components/Navbar.jsx` | `backend/tests/test_friends_notifications.py` |
