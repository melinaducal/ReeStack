# CU10 — Asistente de recomendaciones culturales con IA

| Campo | Valor |
|---|---|
| Caso de uso | CU10 |
| Estado | Implementado (verificable) |
| Spec | `specs/casos-uso-chatbot.md` |
| Backend | `backend/app/routers/chat.py`, `backend/app/services/recommender.py`, `backend/app/models/chat.py`, `backend/app/schemas/chat.py` |
| Catálogo | `backend/app/routers/catalog.py` |
| Pruebas | `backend/tests/test_chat_recommend.py`, `backend/tests/test_chat_isolation.py` |
| Última verificación | 109 pruebas aprobadas (`pytest tests -q`) |

---

## 1. Objetivo

Permitir que un usuario autenticado pida recomendaciones de contenido cultural
(libros, películas, series, música y papers) en lenguaje natural, y recibir
obras reales —verificadas contra catálogos externos— con una explicación de por
qué encajan con su pedido y con sus gustos registrados.

La respuesta nunca se basa en títulos inventados por el modelo: toda sugerencia
del LLM se re-verifica contra un catálogo. Si no hay clave de LLM o el proveedor
falla, el asistente responde igual con un motor heurístico y búsqueda real.

## 2. Alcance

### Implementado

- Interpretación de pedidos en español rioplatense y español neutro.
- Perfil de gustos por usuario a partir de biblioteca, puntuaciones, notas y
  comentarios.
- Búsqueda en catálogos reales y verificación de cada obra.
- Explicación del motivo de cada recomendación.
- Exclusión de contenido ya consumido y de títulos ya sugeridos en la misma
  conversación.
- Conversaciones de varios turnos: el asistente recuerda las obras mostradas,
  resuelve referencias («el segundo», «ese libro»), compara, amplía, refina y
  responde detalles con datos de catálogo.
- Preferencia de spoilers explícita por conversación.
- Persistencia de conversaciones por usuario con aislamiento estricto.
- Funcionamiento degradado sin claves de API.
- Endpoints REST con autenticación JWT.

### Fuera de alcance de esta versión

- Memoria entre conversaciones distintas.
- RAG sobre reseñas o documentos.
- Edición o renombrado de conversaciones.
- Recomendación colaborativa entre usuarios.

## 3. Actores

| Actor | Descripción |
|---|---|
| Usuario autenticado | Persona con JWT válido que pide recomendaciones y gestiona sus conversaciones. |
| Sistema (backend) | Interpreta el pedido y el contexto, construye el perfil, consulta catálogos, verifica y puntúa candidatos. |
| LLM externo (opcional) | Interpreta la intención del turno y propone títulos candidatos. Nunca es fuente de verdad: sus propuestas se verifican. |
| Catálogos externos | Open Library, Google Books, TMDB, TVMaze, Wikipedia, iTunes, MusicBrainz y Crossref. |

## 4. Precondiciones

- El usuario está registrado y autenticado con un JWT válido (`Authorization: Bearer <token>`).
- Existe una fila en `users` para el usuario del token.
- Para continuar una conversación, la conversación existe y pertenece al usuario.
- La aplicación creó las tablas `chat_conversations` y `chat_turns` mediante
  `Base.metadata.create_all` (creación aditiva, sin `ALTER` ni borrado de datos).

## 5. Flujo principal

1. El usuario envía `POST /chat/recommend` con `message` y, opcionalmente,
   `conversation_id`, `type`, `limit` y `exclude_consumed`.
2. El backend valida el JWT y obtiene el usuario actual.
3. Si viene `conversation_id`, verifica que la conversación pertenezca al
   usuario. Si no pertenece o no existe, responde `404`.
4. Reconstruye el contexto conversacional desde los turnos persistidos: obras
   recomendadas o consultadas, última tanda de recomendaciones (`last_batch`),
   última obra en foco (`last_focus`) y preferencia de spoilers declarada por el
   usuario. El contexto no vive en memoria: se recalcula en cada pedido.
5. Interpreta la intención del turno. Con `LLM_API_KEY`, el LLM recibe el
   historial, las obras disponibles y la preferencia de spoilers, y devuelve
   `action`, `targets`, `spoilers`, `query` y `reply`. Sin clave o ante fallo,
   un fallback contextual determinista usa el mismo estado persistido.
6. Según `action`:
   - `recommend`: busca recomendaciones nuevas (flujo de los pasos 7 a 11).
   - `details`: responde sobre una obra ya mostrada con datos de catálogo y no
     ejecuta una búsqueda de recomendaciones.
   - `compare`: compara las obras en foco (extensión, año, sinopsis) solo con
     datos disponibles.
   - `more`: busca opciones parecidas a una obra anterior, usando sus géneros y
     creador como semilla y excluyendo lo ya mostrado.
   - `refine`: vuelve a recomendar aplicando la preferencia nueva del usuario.
   - `spoiler`: advierte sobre spoilers antes de mostrar detalles.
   - `chat`: conversa o confirma un cambio de preferencia sin buscar obras.
7. El motor construye el perfil de gustos del usuario con sus items y
   comentarios.
8. Si hay `LLM_API_KEY`, el LLM propone títulos. Cada propuesta se busca en el
   catálogo y solo se conserva si el título coincide con un resultado real.
9. Si no hay propuestas verificadas, el motor busca directamente en los
   catálogos según el pedido y el perfil.
10. Se descartan los títulos ya consumidos (si `exclude_consumed` es `true`) y
    los ya sugeridos en esa conversación.
11. Los candidatos se puntúan y se ordenan; se devuelven hasta `limit`.
12. Cada recomendación incluye un motivo generado a partir de géneros
    coincidentes, afinidad con autores o creadores y restricciones del pedido.
13. Si hay `conversation_id`, se guardan dos turnos (`user` y `assistant`). El
    turno del asistente guarda `{"kind": "<action>", "works": [...]}` con las
    obras mostradas o consultadas, y se devuelve `conversation_id`.
14. La respuesta incluye `engine`, `degraded`, `warnings`, `intent`, `action`,
    `context`, `spoiler_warning` y `spoilers_revealed` para que el cliente pueda
    informar el modo de funcionamiento sin romper el contrato anterior.

## 6. Flujos alternativos

### A1 — Sin `LLM_API_KEY`

El motor no llama al LLM, agrega la advertencia `llm_key_missing`, responde en
modo `heuristic` con `degraded: true` y busca directamente en catálogos. La
respuesta es `200` y puede contener recomendaciones.

### A2 — LLM con error, cuota o timeout

- `429` → advertencia `llm_quota_exceeded`.
- `401`/`403` → advertencia `llm_invalid_key`.
- `>= 500` → advertencia `llm_upstream_error`.
- timeout → advertencia `llm_timeout`.
- error de red → advertencia `llm_unavailable`.
- otro estado → advertencia `llm_status_<código>`.
- respuesta no parseable → advertencia `llm_invalid_response`.

En todos los casos se continúa con el motor heurístico y se responde `200`.

### A3 — El LLM propone obras inexistentes o no verificables

Cada propuesta se busca en el catálogo del tipo indicado. Las que no coinciden
con ningún resultado se descartan y se agrega `llm_suggestions_not_in_catalog`.
Si ninguna se verifica, `engine` queda en `heuristic` y se usa la búsqueda
directa. Si el LLM no devolvió propuestas y tampoco hubo error, se agrega
`llm_suggestions_unverified`.

### A4 — Catálogo vacío

Se responde `200` con `recommendations: []` y un mensaje que invita a probar
otro género o configurar `TMDB_API_KEY`.

### A5 — Proveedor de catálogo caído o con error

Los proveedores no lanzan excepción hacia el router: devuelven lista vacía y un
código de error en `warnings` (por ejemplo `open_library_request_failed`,
`tvmaze_status_503`, `wikipedia_request_failed`, `catalog_search_failed`). La
respuesta sigue siendo `200`.

### A6 — Películas o series sin `TMDB_API_KEY`

TMDB requiere clave y TVMaze busca nombres, no géneros. Si la búsqueda directa
devuelve pocos resultados (películas) o ninguno (series), se usa un respaldo sin
clave basado en Wikipedia: se buscan artículos con `Infobox film` o
`Infobox television`, se extrae director/creador, año, sinopsis y póster real.

La frase de género se cita antes de buscar (`"science fiction" film`) porque sin
comillas Wikipedia devuelve el artículo del género en lugar de películas.

### A7 — Conversación inexistente o de otro usuario

Se responde `404` con el mismo mensaje en ambos casos (`Conversación no
encontrada`), para no revelar la existencia de conversaciones ajenas.

### A8 — Pedido sin tipo de contenido explícito

Si el usuario no menciona un tipo, se usan los tipos con mayor peso en su
perfil. Si el perfil está vacío, se usan `book`, `movie` y `series`.

### A9 — `type` inválido o fuera de los tipos soportados

El valor se ignora y se aplica la misma regla que A8. No se responde error.

### A10 — Parámetros fuera de rango

`message` vacío o de más de 1500 caracteres, `limit` menor que 1 o mayor que 6,
o `conversation_id` no entero producen `422` por validación de Pydantic.

### A11 — `POST /chat/save` con un título ya existente

Si el usuario ya tiene un item con ese título exacto, se responde `400` con
`Ya existe en tu biblioteca`.

### A12 — Pregunta sobre una obra ya mostrada

Si el mensaje pide detalles de una obra de la conversación («¿De qué trata el
segundo?», «¿quién escribió ese libro?»), `action` es `details`, se resuelve la
referencia contra `last_batch`/`last_focus` y se responde con datos del catálogo.
`recommendations` queda vacío y **no** se llama a la búsqueda de recomendaciones.

### A13 — Comparación de obras anteriores

«¿Cuál de los tres es más corto?» produce `action: compare`. Se comparan solo
las obras en foco. Si faltan páginas o duración, el mensaje lo dice y no se
inventa una extensión. Si las métricas son incomparables (páginas vs. minutos),
también se informa. Sin un criterio explícito («¿cuál es la mejor?») no se
declara ganadora: se listan los datos y se pregunta qué comparar.

### A14 — Pedido de final o spoilers

Si el mensaje pide el final («Explicame el final», «contame el desenlace»), el
turno se clasifica como `spoiler`. La respuesta empieza con un aviso explícito y
`spoiler_warning: true`. Con `sin spoilers` en el mismo mensaje o como
preferencia previa, se recorta la sinopsis y `spoilers_allowed` queda en
`false`. El catálogo no contiene finales: el asistente nunca los inventa.

### A15 — LLM intérprete no disponible o respuesta inválida

Si falta `LLM_API_KEY`, hay timeout, error de red o JSON inválido, se usa el
fallback contextual y se agrega la advertencia correspondiente
(`llm_key_missing`, `llm_timeout`, `llm_unavailable`, `llm_invalid_response`,
etc.). La respuesta sigue siendo `200` y mantiene el contexto conversacional.

### A16 — Detalle sin datos en el catálogo

Si al consultar una obra el catálogo no devuelve sinopsis, autor, páginas o
duración, el mensaje lo declara explícitamente. No se completan datos con
conocimiento del modelo ni con texto inventado.

## 7. Reglas de negocio

| ID | Regla |
|---|---|
| RN-01 | Toda recomendación debe existir en un catálogo consultado. El LLM solo propone; el catálogo verifica. |
| RN-02 | La coincidencia de títulos ignora mayúsculas, acentos y diferencias de subtítulo (contención cuando el título corto tiene 4 o más caracteres). |
| RN-03 | La respuesta es `200` aunque no haya recomendaciones o falle un proveedor. |
| RN-04 | Sin `LLM_API_KEY` el asistente sigue funcionando en modo heurístico. |
| RN-05 | `degraded` es `true` si existe al menos una advertencia que empiece con `llm_`. |
| RN-06 | El perfil de gustos usa solo datos del usuario autenticado: items propios y comentarios propios. |
| RN-07 | Una puntuación alta refuerza el tipo, el género y el creador. Un comentario con puntuación menor a 2.5 aporta peso negativo al género. |
| RN-08 | Con `exclude_consumed: true`, no se recomiendan títulos presentes en la biblioteca ni en los comentarios del usuario. |
| RN-09 | Dentro de una misma conversación no se repite un título ya recomendado en turnos anteriores. |
| RN-10 | El historial del recomendador se limita a los últimos 6 turnos; el intérprete contextual usa hasta 12 y resume las obras de cada turno. |
| RN-11 | El título de una conversación se autogenera con los primeros 80 caracteres del primer mensaje si no se especificó. |
| RN-12 | Las conversaciones se listan de la más reciente a la más antigua. |
| RN-13 | Eliminar una conversación elimina sus turnos por cascada. |
| RN-14 | La caché de catálogo dura 300 segundos y se comparte entre `/catalog/search` y el recomendador. |
| RN-15 | El límite de resultados por proveedor es 50; la respuesta final se recorta a `limit` (1 a 6). |
| RN-16 | Los textos de motivos y mensajes se generan en español. |
| RN-17 | El contexto conversacional se reconstruye desde los turnos persistidos; no se guarda en memoria del proceso. |
| RN-18 | El LLM es el intérprete primario de la intención. Sin clave o ante error, un fallback contextual usa el mismo estado y no respuestas fijas por palabra aislada. |
| RN-19 | Los ordinales («el primero», «la segunda») y «el último» se resuelven contra la última tanda de recomendaciones, no contra el acumulado histórico. |
| RN-20 | «Ese libro», «esa película» y similares se resuelven contra la última obra en foco, filtrando por tipo cuando el mensaje lo nombra. |
| RN-21 | Una consulta de detalles o comparación nunca dispara una búsqueda nueva de recomendaciones. |
| RN-22 | Sinopsis, autores, páginas, duración y argumentos provienen exclusivamente del catálogo. Si falta el dato, se informa; no se inventa. |
| RN-23 | La preferencia de spoilers se toma de los mensajes del usuario y se conserva entre turnos. Un aviso del asistente no la modifica. |
| RN-24 | «Dame otros parecidos al primero» usa los géneros y el creador de esa obra como semilla, no el texto literal del pedido. |
| RN-25 | Una comparación solo declara una ganadora cuando el usuario pidió un criterio explícito (extensión o año). Sin criterio, se listan los datos y se pregunta cuál comparar. |

### Tipos de contenido soportados

`book`, `movie`, `series`, `music`, `paper`.

### Géneros reconocidos

| Clave | Etiqueta |
|---|---|
| `romance` | romance |
| `mystery` | misterio |
| `thriller` | suspenso |
| `scifi` | ciencia ficción |
| `fantasy` | fantasía |
| `horror` | terror |
| `drama` | drama |
| `comedy` | comedia |
| `adventure` | aventura |
| `historical` | histórico |
| `crime` | crimen |
| `biography` | biografía |
| `poetry` | poesía |
| `youngadult` | juvenil |
| `selfhelp` | desarrollo personal |
| `musical` | musical |

La detección es insensible a mayúsculas y acentos, y reconoce sinónimos en
español e inglés (`misterio`/`mystery`, `ciencia ficción`/`science fiction`,
`amor`/`love story`, entre otros).

### Restricciones reconocidas

| Clave | Frases de ejemplo |
|---|---|
| `happy_ending` | «final feliz», «termina bien», «happy ending», «buen final» |
| `short` | «corto», «corta», «breve», «novela corta», «relato corto» |
| `recent` | «novedad», «nuevo», «reciente», «último», «estreno» |
| `classic` | «clásico», «antiguo», «vintage», «de culto» |

### Fuentes por tipo

| Tipo | Proveedores |
|---|---|
| `book` | Open Library; Google Books si `GOOGLE_BOOKS_API_KEY` está configurada y Open Library devuelve menos de 5 resultados |
| `movie` | TMDB si hay clave; Wikipedia como respaldo sin clave |
| `series` | TVMaze; TMDB `/search/tv` si hay clave; Wikipedia como respaldo |
| `music` | iTunes; MusicBrainz |
| `paper` | Crossref |

## 8. Criterios de aceptación

| ID | Criterio |
|---|---|
| CA-01 | `POST /chat/recommend` sin JWT responde `401`. |
| CA-02 | Un pedido como «Quiero un romance con misterio y final feliz» se interpreta con géneros `romance` y `mystery` y `happy_ending: true`. |
| CA-03 | Un pedido como «Recomendame una película parecida a Interestelar» detecta `movie` y la obra de referencia. |
| CA-04 | La detección funciona con y sin acentos. |
| CA-05 | Sin `LLM_API_KEY` la respuesta es `200`, `engine: heuristic`, `degraded: true` y aparece `llm_key_missing`. |
| CA-06 | Una propuesta del LLM que no existe en el catálogo no aparece en `recommendations` y se informa `llm_suggestions_not_in_catalog`. |
| CA-07 | Si el LLM responde `429` se informa `llm_quota_exceeded` y se devuelven recomendaciones heurísticas. |
| CA-08 | Cada recomendación incluye `reason` no vacío y `matched_genres` con las etiquetas coincidentes. |
| CA-09 | Un título ya presente en la biblioteca no se recomienda cuando `exclude_consumed` es `true`. |
| CA-10 | Una puntuación alta de un autor se refleja en el motivo de la recomendación. |
| CA-11 | La biblioteca de otro usuario no influye en las recomendaciones. |
| CA-12 | Una conversación guarda los turnos `user` y `assistant` y los devuelve en orden. |
| CA-13 | Un usuario no puede listar, leer, escribir ni borrar conversaciones de otro: `404` y lista vacía. |
| CA-14 | Una conversación inexistente responde `404`. |
| CA-15 | Dos turnos de la misma conversación no repiten títulos. |
| CA-16 | Borrar una conversación responde `204` y deja de aparecer en el listado. |
| CA-17 | `POST /chat/save` asigna el item al usuario autenticado. |
| CA-18 | Un pedido de película por género sin clave usa el respaldo de Wikipedia y devuelve resultados con `source: wikipedia`. |
| CA-19 | Los errores de proveedor se informan en `warnings` sin romper la respuesta. |
| CA-20 | «¿De qué trata el segundo?» responde sobre la segunda obra de la última tanda, con `action: details`, `recommendations: []` y sin una nueva búsqueda. |
| CA-21 | «¿Cuál de los tres es más corto?» compara las tres obras y no inventa páginas ni duración faltantes. |
| CA-22 | «Dame otros parecidos al primero» devuelve obras nuevas relacionadas con la primera y no repite las ya mostradas. |
| CA-23 | «Explicame el final» devuelve `spoiler_warning: true` y un aviso antes del contenido; «sin spoilers» impide revelar detalles. |
| CA-24 | Cerrar y reabrir una conversación conserva sus obras y permite seguir preguntando por ordinales. |
| CA-25 | Dos usuarios distintos nunca comparten contexto: una conversación ajena responde `404`. |
| CA-26 | El prompt de interpretación incluye el historial y las obras ya mostradas; el prompt de recomendación las lista para no repetirlas. |
| CA-27 | Sin `LLM_API_KEY` los casos anteriores siguen funcionando con el fallback contextual y la respuesta informa la degradación. |
| CA-28 | «¿Cuál es la mejor?» no declara «la más corta»: pide un criterio. «¿Cuál es el más antiguo?» compara años. |

## 9. Endpoints reales

Todos viven bajo el prefijo `/chat` y requieren `Authorization: Bearer <token>`.

| Método | Ruta | Éxito | Descripción |
|---|---|---|---|
| `POST` | `/chat/recommend` | `200` | Genera recomendaciones y, opcionalmente, las persiste en una conversación. |
| `POST` | `/chat/conversations` | `201` | Crea una conversación vacía. |
| `GET` | `/chat/conversations` | `200` | Lista las conversaciones del usuario autenticado. |
| `GET` | `/chat/conversations/{conversation_id}` | `200` | Devuelve los turnos de una conversación propia. |
| `DELETE` | `/chat/conversations/{conversation_id}` | `204` | Elimina una conversación propia y sus turnos. |
| `POST` | `/chat/save` | `200` | Agrega una recomendación a la biblioteca del usuario. |

### 9.1 `POST /chat/recommend`

Request:

```json
{
  "message": "Quiero un romance con misterio y final feliz",
  "conversation_id": 12,
  "type": "book",
  "limit": 4,
  "exclude_consumed": true
}
```

| Campo | Tipo | Obligatorio | Regla |
|---|---|---|---|
| `message` | string | Sí | 1 a 1500 caracteres. |
| `conversation_id` | integer | No | Si se omite, la respuesta es stateless y no se persiste nada. |
| `type` | string | No | `book`, `movie`, `series`, `music` o `paper`. |
| `limit` | integer | No | 1 a 6. Por defecto 4. |
| `exclude_consumed` | boolean | No | Por defecto `true`. |

Response `200`:

```json
{
  "message": "Encontré 4 opciones en el catálogo para libros y películas de romance y misterio con final feliz.",
  "recommendations": [
    {
      "title": "El amor en los tiempos del cólera",
      "type": "book",
      "creator": "Gabriel García Márquez",
      "reason": "Coincide con tu pedido: romance. Gabriel García Márquez es una referencia que ya puntuaste alto.",
      "in_library": false,
      "year": 1985,
      "cover_url": "https://covers.openlibrary.org/b/id/1-M.jpg",
      "external_id": "ol-123",
      "source": "open_library",
      "matched_genres": ["romance"]
    }
  ],
  "engine": "heuristic",
  "degraded": true,
  "warnings": ["llm_key_missing"],
  "conversation_id": 12,
  "intent": {
    "types": [],
    "genres": ["romance", "mystery"],
    "constraints": {
      "happy_ending": true,
      "short": false,
      "recent": false,
      "classic": false
    },
    "similar_to": null
  },
  "action": "recommend",
  "context": { "works": [], "available": [] },
  "spoiler_warning": false,
  "spoilers_revealed": false
}
```

| Campo de respuesta | Descripción |
|---|---|
| `message` | Resumen en español de lo encontrado o respuesta a la consulta. |
| `recommendations` | Hasta `limit` obras verificadas. Vacío en `details`, `compare` y `chat`. |
| `engine` | `llm` si hubo propuestas verificadas del modelo; `heuristic` en caso contrario. |
| `degraded` | `true` si alguna advertencia empieza con `llm_`. |
| `warnings` | Códigos de error o degradación, sin datos sensibles. |
| `conversation_id` | Presente solo si se continuó una conversación. |
| `intent` | Interpretación del pedido: tipos, géneros, restricciones, obra de referencia, `action`, `targets` y `spoilers_allowed`. |
| `action` | `recommend`, `details`, `compare`, `more`, `refine`, `spoiler` o `chat`. |
| `context` | `works` en foco y `available` obras de la conversación. |
| `spoiler_warning` | `true` si la respuesta incluye aviso de spoilers. |
| `spoilers_revealed` | `true` solo si se muestra contenido con posibles spoilers y el usuario lo autorizó. |

Campos de cada recomendación: `title`, `type`, `creator`, `reason`,
`in_library`, `year`, `cover_url`, `external_id`, `source`, `matched_genres`.

### 9.2 `POST /chat/conversations`

Request:

```json
{ "title": "Recomendaciones de verano" }
```

`title` es opcional (máximo 200 caracteres). Response `201`:

```json
{
  "id": 12,
  "title": "Recomendaciones de verano",
  "created_at": "2026-11-01T14:03:00",
  "turns": 0
}
```

### 9.3 `GET /chat/conversations`

Response `200`: lista de resúmenes del usuario, ordenados por `id` descendente.
Cada resumen tiene `id`, `title`, `created_at` y `turns`.

### 9.4 `GET /chat/conversations/{conversation_id}`

Response `200`: lista de turnos en orden de inserción.

```json
[
  {
    "id": 41,
    "role": "user",
    "content": "Quiero un romance con misterio",
    "recommendations": [],
    "created_at": "2026-11-01T14:05:00"
  },
  {
    "id": 42,
    "role": "assistant",
    "content": "Encontré 4 opciones en el catálogo para libros de romance y misterio.",
    "recommendations": [
      { "title": "El amor en los tiempos del cólera", "type": "book" }
    ],
    "created_at": "2026-11-01T14:05:02"
  }
]
```

### 9.5 `DELETE /chat/conversations/{conversation_id}`

Response `204` sin cuerpo. Elimina la conversación y, por cascada, sus turnos.

### 9.6 `POST /chat/save`

Request:

```json
{
  "title": "Cien años de soledad",
  "type": "book",
  "creator": "Gabriel García Márquez",
  "year": 1967,
  "cover_url": "https://covers.openlibrary.org/b/id/2-M.jpg",
  "reason": "Te gustó el realismo mágico",
  "in_library": false
}
```

Response `200`:

```json
{ "message": "Agregado a tu biblioteca", "id": 87 }
```

Reglas: el item se crea con `user_id` del token, `thoughts` toma el valor
`Recomendado por chatbot: <reason>` y se rechaza con `400` si el usuario ya tiene
un item con ese título exacto.

### 9.7 Códigos de error

| Código | Situación |
|---|---|
| `401` | Falta el token, es inválido o el usuario no existe. |
| `404` | La conversación no existe o no pertenece al usuario. |
| `400` | `POST /chat/save` con un título ya presente en la biblioteca. |
| `422` | Fallo de validación de Pydantic (mensaje vacío, `limit` fuera de rango, etc.). |

## 10. Persistencia conversacional

### 10.1 Tablas

`chat_conversations`

| Columna | Tipo | Restricción |
|---|---|---|
| `id` | Integer | PK, indexado |
| `user_id` | Integer | FK `users.id`, NOT NULL, indexado |
| `title` | String | NULL |
| `created_at` | DateTime | NOT NULL, UTC sin zona horaria |

`chat_turns`

| Columna | Tipo | Restricción |
|---|---|---|
| `id` | Integer | PK, indexado |
| `conversation_id` | Integer | FK `chat_conversations.id`, NOT NULL, indexado |
| `role` | String | NOT NULL, `user` o `assistant` |
| `content` | Text | NOT NULL |
| `recommendations` | Text | JSON serializado, NULL si no aplica |
| `created_at` | DateTime | NOT NULL, UTC sin zona horaria |

### 10.2 Reglas de persistencia

- Las tablas se crean de forma aditiva con `Base.metadata.create_all`. No se
  ejecutan `ALTER TABLE` ni se elimina información existente.
- Cada llamada a `/chat/recommend` con `conversation_id` agrega exactamente dos
  turnos: el pedido del usuario y la respuesta del asistente.
- El turno `assistant` guarda un snapshot JSON con la forma
  `{"kind": "<action>", "works": [...]}`. `works` contiene las obras mostradas o
  consultadas en ese turno; en un turno de detalles conserva la obra consultada,
  de modo que las recomendaciones anteriores no se pierden.
- Los turnos creados antes de este formato guardaban una lista plana. Ambos
  formatos se leen de forma compatible y `GET` siempre devuelve una lista.
- La relación `ChatConversation.turns` usa `cascade="all, delete-orphan"` y
  orden por `id`.
- La conversación no guarda el perfil de gustos: se recalcula en cada pedido,
  de modo que refleja cambios en la biblioteca sin migraciones.
- Si la conversación no tiene título, se asigna el primer mensaje recortado a
  80 caracteres.

## 11. Seguridad JWT

- Todos los endpoints de `/chat` dependen de `get_current_user`.
- El token se recibe en `Authorization: Bearer <token>` mediante `HTTPBearer`.
- La firma se valida con `SECRET_KEY` y `ALGORITHM` desde configuración
  (HS256). `SECRET_KEY` debe definirse por variable de entorno en producción.
- Un token inválido, vencido o de un usuario inexistente responde `401`.
- El backend nunca devuelve `hashed_password` ni el token en las respuestas.
- Las claves de LLM y de catálogos se leen solo en el backend
  (`LLM_API_KEY`, `TMDB_API_KEY`, `GOOGLE_BOOKS_API_KEY`); nunca se envían al
  frontend.
- Los `warnings` incluyen códigos, no credenciales ni cuerpos de respuesta de
  terceros.
- CORS se mantiene restringido a los orígenes configurados
  (`http://localhost:5173` y `http://localhost:5175`).

## 12. Aislamiento por usuario

- El perfil de gustos se construye con `Item.user_id == user.id` y
  `Comment.user_id == user.id`. No se consultan datos de otros usuarios.
- Las conversaciones se filtran siempre por `user_id` en lectura y escritura.
- `_owned_conversation` responde `404` tanto si la conversación no existe como
  si pertenece a otro usuario, con el mismo mensaje.
- Un usuario no puede listar conversaciones ajenas: `GET /chat/conversations`
  devuelve solo las propias.
- Un usuario no puede escribir en una conversación ajena: `/chat/recommend` con
  un `conversation_id` ajeno responde `404` y no persiste turnos.
- Un usuario no puede borrar conversaciones ajenas: `DELETE` responde `404`.
- `POST /chat/save` asigna siempre `user_id` del token, sin aceptar `user_id` en
  el cuerpo.

## 13. Configuración por variables de entorno

| Variable | Obligatoria | Efecto |
|---|---|---|
| `LLM_API_KEY` | No | Sin ella, modo heurístico con `llm_key_missing`. |
| `LLM_API_URL` | No | Endpoint compatible con OpenAI. Por defecto OpenRouter. |
| `LLM_MODEL` | No | Modelo a usar. Por defecto `anthropic/claude-3.5-sonnet`. |
| `LLM_APP_NAME` | No | Cabecera `X-Title`. |
| `LLM_APP_URL` | No | Cabecera `HTTP-Referer`. |
| `LLM_TIMEOUT` | No | Segundos de espera del LLM. Por defecto 30. |
| `TMDB_API_KEY` | No | Habilita TMDB para películas y series. |
| `GOOGLE_BOOKS_API_KEY` | No | Amplía libros cuando Open Library devuelve poco. |

Ninguna clave es obligatoria para que el endpoint responda.

## 14. Trazabilidad con las pruebas existentes

Archivo `backend/tests/test_chat_recommend.py` (20 pruebas, base en memoria y
catálogo/LLM simulados):

| Prueba | Criterio |
|---|---|
| `test_parse_request_detects_genres_and_happy_ending` | CA-02 |
| `test_parse_request_detects_media_type_and_reference_work` | CA-03 |
| `test_parse_request_is_accent_insensitive` | CA-04 |
| `test_recommend_requires_authentication` | CA-01 |
| `test_recommend_without_llm_key_still_answers` | CA-05 |
| `test_recommend_returns_200_when_catalog_is_empty` | CA-19, RN-03 |
| `test_recommend_survives_catalog_provider_errors` | CA-19 |
| `test_movie_genre_uses_keyless_wikipedia_fallback` | CA-18 |
| `test_every_recommendation_explains_the_match` | CA-08 |
| `test_llm_proposals_must_exist_in_the_catalog` | CA-06 |
| `test_llm_quota_errors_fall_back_to_heuristics` | CA-07 |
| `test_recommend_excludes_titles_already_in_the_library` | CA-09 |
| `test_recommend_uses_ratings_to_explain_creator_affinity` | CA-10 |
| `test_library_of_another_user_is_not_used` | CA-11 |
| `test_conversation_keeps_turns_for_its_owner` | CA-12 |
| `test_conversations_are_not_shared_between_users` | CA-13 |
| `test_unknown_conversation_returns_404` | CA-14 |
| `test_conversation_does_not_repeat_recommendations` | CA-15 |
| `test_delete_conversation_only_affects_the_owner` | CA-16 |
| `test_save_recommendation_keeps_assigning_the_current_user` | CA-17 |

Archivo `backend/tests/test_chat_isolation.py` (2 pruebas, base en memoria):

| Prueba | Criterio |
|---|---|
| `test_chat_recommend_only_own_items` | CA-11 |
| `test_chat_save_assigns_user_id` | CA-17 |

Archivo `backend/tests/test_chat_contextual.py` (19 pruebas, base en memoria,
catálogo, detalles y LLM simulados):

| Prueba | Criterio |
|---|---|
| `test_a_recommends_three_mystery_books` | CA-20 |
| `test_b_explains_second_without_recommending_again` | CA-20, RN-19, RN-21 |
| `test_c_compares_the_three_and_finds_the_shortest` | CA-21 |
| `test_c_does_not_invent_length_when_catalogue_has_no_data` | CA-21, RN-22 |
| `test_c_does_not_pick_a_winner_without_a_criterion` | CA-28, RN-25 |
| `test_c_compares_by_year_when_asked` | CA-28, RN-25 |
| `test_d_more_like_the_first_uses_the_seed_work` | CA-22, RN-24 |
| `test_e_warns_about_spoilers_before_details` | CA-23 |
| `test_e_respects_sin_spoilers` | CA-23, RN-23 |
| `test_e_preference_only_acknowledges_without_searching` | RN-23 |
| `test_f_context_survives_closing_and_reopening` | CA-24, RN-17 |
| `test_g_users_never_share_conversation_context` | CA-25 |
| `test_interpret_prompt_includes_history_and_previous_works` | CA-26 |
| `test_llm_interpretation_resolves_the_second_work` | CA-20, RN-18 |
| `test_llm_chat_answer_without_new_recommendations` | RN-18, CA-26 |
| `test_llm_failure_degrades_and_still_answers_with_context` | CA-27 |
| `test_detail_lookup_prefers_the_work_over_derivative_books` | RN-22 |
| `test_open_library_description_accepts_list_and_dict_shapes` | RN-22 |
| `test_recommendation_prompt_lists_already_shown_works` | CA-26, RN-09 |

Resultado de la última ejecución: `128 passed` con `pytest tests -q`, sin bases
de datos residuales.

## 15. Funcionalidades pendientes

Estas capacidades **no** están implementadas y no deben considerarse cubiertas
por esta spec:

- **Renombrar o editar conversaciones.** No existe `PATCH`/`PUT` sobre
  `/chat/conversations/{id}`.
- **Paginación o búsqueda en el listado de conversaciones.** `GET
  /chat/conversations` devuelve todas.
- **Borrado masivo de conversaciones.** Solo existe borrado individual.
- **Marcar contenido como consumido desde el asistente.** La exclusión depende
  de la biblioteca y los comentarios existentes.
- **Respaldo sin clave para música y papers.** Wikipedia solo cubre películas y
  series; música depende de iTunes/MusicBrainz y papers de Crossref.
- **Verificación contra un LLM real.** Tanto la propuesta de títulos como el
  intérprete conversacional se prueban con LLM simulado; en este entorno no hay
  `LLM_API_KEY` ni claves de catálogo. La prueba real requiere configurar
  `LLM_API_KEY` y ejecutar una conversación manual de varios turnos contra el
  proveedor.
- **Puntuaciones coherentes en el frontend.** El frontend usa escala 0–10 con
  `parseInt`, mientras el backend acepta 1–5 con fracciones; esto degrada la
  calidad del perfil de gustos.
- **Pruebas de integración contra proveedores en vivo.** Las pruebas del
  recomendador simulan el catálogo; `tests/test_books_genres.py` depende de
  proveedores reales y puede fallar por red o cuota.
- **Specs de otros casos de uso.** Varias funcionalidades relacionadas siguen
  sin spec aprobada.

## 16. Referencias

- `backend/app/routers/chat.py` — endpoints y persistencia de turnos.
- `backend/app/services/assistant.py` — contexto conversacional, intención,
  referencias, detalles, comparación y spoilers.
- `backend/app/services/recommender.py` — interpretación, perfil, verificación y puntuación.
- `backend/app/models/chat.py` — tablas de conversación.
- `backend/app/schemas/chat.py` — contratos de entrada y salida.
- `backend/app/routers/catalog.py` — proveedores y caché.
- `backend/.env.example` — variables de entorno documentadas.
- `backend/tests/test_chat_recommend.py` — pruebas del motor.
- `backend/tests/test_chat_contextual.py` — pruebas de conversaciones de varios turnos.
- `backend/tests/test_chat_isolation.py` — pruebas de aislamiento.
