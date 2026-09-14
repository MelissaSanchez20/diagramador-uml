# Diagramador UML

Herramienta web tipo **CASE** para modelado de **diagramas de clases UML**, similar a Enterprise Architect.

## Contexto del proyecto

- Materia **Software 1** — UAGRM (Universidad Autónoma Gabriel René Moreno).
- Desarrollo **individual** (trabajo sola).
- Plazo: **2 semanas**.
- Objetivo final: diseñar diagramas de clases y, más adelante, **generar automáticamente** el código de backend y frontend a partir del modelo.

## Stack

| Capa | Ubicación | Tecnologías |
|------|-----------|-------------|
| Backend | `backend/` | Python, FastAPI, SQLAlchemy 2.0 (ORM tipado con `Mapped`), PostgreSQL, Alembic, Pydantic v2 / pydantic-settings, Uvicorn |
| Frontend | `frontend/` | React 19 + TypeScript, Vite, React Flow (`reactflow`), Axios, oxlint |
| Mobile | `mobile/` | Flutter |

- Base de datos PostgreSQL: **`diagramador_uml_db`**.
- Config del backend vía `.env` (`DATABASE_URL`, `PROJECT_NAME`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `CORS_ORIGINS`) — ver `backend/app/core/config.py` y `.env.example`.

## Estructura del backend

```
backend/app/
  main.py            # app FastAPI: CORS + routers + endpoints / y /health/db
  seed.py            # crea el usuario admin de prueba (python -m app.seed)
  core/config.py     # Settings (pydantic-settings)
  core/security.py   # hashing de contraseñas + JWT
  db/session.py      # engine, SessionLocal, Base, get_db()
  models/            # usuario, proyecto, proyecto_colaborador, clase_uml, atributo, metodo, relacion
  schemas/           # usuario, proyecto, colaborador, diagrama
  routers/           # auth, usuarios, proyectos, colaboradores, diagramas, ws_diagramas (CU10), generacion, reportes
  services/          # acceso.py (control de acceso a proyecto compartido), diagrama.py (validar/cargar/guardar, CU09+CU10), yjs_rooms.py (rooms Yjs en memoria, CU10), generador_spring.py (CU08), generador_reporte.py (CU07)
backend/alembic/     # migraciones
```

### Autenticación (Ciclo 1) — ya implementada

- JWT con `python-jose`; hashing con `passlib` + `bcrypt` (fijado en `4.0.1`, no subir sin quitar passlib).
- `app/core/security.py`: hash/verificación de contraseñas y creación/decodificación de tokens.
- `app/routers/auth.py`: `POST /auth/login` (form OAuth2, el campo `username` es el email) + dependencia reutilizable `get_current_user` para proteger endpoints.
- `app/routers/usuarios.py`: `GET`/`PUT /usuarios/me` (CU03).
- `app/routers/proyectos.py`: CRUD de proyectos (CU04); solo el administrador dueño modifica/elimina; `DELETE` con colaboradores activos exige `?confirmar=true` (si no, 409). La gestión de colaboradores vive en `app/routers/colaboradores.py` (CU05/CU06, ver sección propia abajo).
- Config en `.env`: `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `CORS_ORIGINS` — ver `.env.example`.
- Logout (CU02) es solo del lado del cliente (descartar el token); no hay endpoint ni blocklist.
- `POST /auth/registro` (público): crea un usuario nuevo (rol `ADMINISTRADOR` siempre) y devuelve `Token` como el login. Frontend: `RegistroPage.tsx` / ruta `/registro`. El seed sigue siendo la forma de crear el primer usuario en una BD vacía.

### Modelos existentes (`backend/app/models/`) — ya migrados con Alembic

- **`Usuario`** (`usuarios`): `id`, `nombre_completo`, `email` (único), `password_hash`, `rol` (`RolUsuario`: `ADMINISTRADOR` | `COLABORADOR`), `fecha_registro`.
- **`Proyecto`** (`proyectos`): `id`, `nombre`, `descripcion`, `fecha_creacion`, `id_administrador` → `usuarios.id`. Único `(id_administrador, nombre)`.
- **`ProyectoColaborador`** (`proyecto_colaboradores`): `id`, `id_proyecto`, `id_usuario`, `fecha_asignacion`, `activo`. Único `(id_proyecto, id_usuario)`.
- **`ClaseUml`** (`clases_uml`): `id` (string/UUID generado en el cliente), `id_proyecto`, `nombre`, `estereotipo`, `es_abstracta`, `pos_x`/`pos_y` (posición en el lienzo), `fecha_creacion`.
- **`Atributo`** (`atributos`) / **`Metodo`** (`metodos`): `id_clase` → `clases_uml.id`, `nombre`, `tipo`/`tipo_retorno`, `visibilidad` (`VisibilidadMiembro`: `PUBLICO`|`PRIVADO`|`PROTEGIDO`|`PAQUETE`), `orden`. `Metodo` además tiene `parametros` (string libre).
- **`Relacion`** (`relaciones`): `id_proyecto`, `id_clase_origen`/`id_clase_destino` → `clases_uml.id`, `tipo` (`TipoRelacion`: `ASOCIACION`|`HERENCIA`|`AGREGACION`|`COMPOSICION`), `etiqueta`, `multiplicidad_origen`/`multiplicidad_destino`, `handle_origen`/`handle_destino` (lado del nodo React Flow del que sale/llega la arista).

Convenciones: nombres de tablas/campos en **español**, claves foráneas como `id_<entidad>`, timestamps con `server_default=func.now()` y `DateTime(timezone=True)`.

### Diagrama de clases (CU09) — backend implementado

- `app/routers/diagramas.py`: `GET`/`PUT /proyectos/{id}/diagrama`, accesible al administrador dueño del proyecto o a un colaborador activo.
- El `PUT` reemplaza el diagrama completo (borra todas las clases/relaciones del proyecto y reinserta lo recibido) — no hay edición incremental por campo. El frontend lo usa como autoguardado (ver `useDiagrama.ts`).
- `app/schemas/diagrama.py`: `DiagramaIO` (`clases: ClaseIO[]`, `relaciones: RelacionIO[]`), con `AtributoIO`/`MetodoIO` anidados en `ClaseIO`.
- `app/services/acceso.py`: `obtener_proyecto_con_acceso` (dueño o colaborador activo, CU09/CU08/CU05-GET) y `obtener_proyecto_propio` (solo el administrador dueño, CU04/CU05-POST/DELETE).

### Búsqueda de usuarios y gestión de colaboradores (CU06/CU05) — backend + frontend implementados

- `GET /usuarios/buscar?q=&proyecto_id=` (`app/routers/usuarios.py`): busca por `nombre_completo`/`email` (parcial, sin distinguir mayúsculas; `q` vacío devuelve `[]`). Nunca incluye a quien busca; con `proyecto_id` tampoco a sus colaboradores activos, y exige que quien busca tenga acceso a ese proyecto (dueño o colaborador activo vía `obtener_proyecto_con_acceso`) — si no, 403, para que no se pueda inferir quiénes son colaboradores de un proyecto ajeno probando ids.
- `app/routers/colaboradores.py` (`/proyectos/{id}/colaboradores`, movido fuera de `proyectos.py`): `GET` (dueño o colaborador activo), `POST {usuario_id}` y `DELETE /{usuario_id}` (**solo** el administrador dueño — `obtener_proyecto_propio`, no el genérico). `POST` reactiva (`activo=true`, `fecha_asignacion` actualizada) si la fila ya existía inactiva, en vez de duplicarla (constraint única `id_proyecto`+`id_usuario`). `DELETE` es soft-delete.
- **Cambio de contrato respecto al CU04 original**: antes se agregaba por `email` y se quitaba por el `id` de la fila `ProyectoColaborador`; ahora se agrega/quita por `usuario_id` (resuelto vía la búsqueda de CU06).
- Frontend: `ColaboradoresModal.tsx` reescrito — buscador con debounce (300ms) que llama a `GET /usuarios/buscar` con `proyecto_id` de contexto, resultados como lista clicable (nombre + email + "Agregar"/"Agregando…"), quitar usa `colaborador.usuario.id` (no el id de la fila). `api/usuarios.ts::buscarUsuarios`, `api/colaboradores.ts` actualizado al nuevo contrato.
- Tests en `backend/tests/test_colaboradores.py`.

### Generación de backend Spring Boot (CU08) — backend + frontend implementados

- `app/routers/generacion.py`: `POST /proyectos/{id}/generar-backend`, mismo control de acceso que CU09; 400 si el proyecto no tiene clases todavía. Devuelve un `.zip` (proyecto Maven completo) como `StreamingResponse`.
- `app/services/generador_spring.py`: arma el `.zip` a partir de `clases_uml`/`atributos`/`relaciones` — entidades JPA (`@Entity`/`@Table`/`@Column`, Lombok `@Getter/@Setter`), `Repository`/`Service`/`Controller` (CRUD, rutas `/api/{plural}`), `pom.xml` (Spring Boot 3.2.5, Java 17) y `application.properties` de plantilla (sin JWT todavía). Mapeo de tipos UML→Java y de multiplicidad→anotación JPA documentados en el encabezado del módulo.
- Limitaciones conocidas: `HERENCIA` se mapea como asociación simple (sin `@Inheritance`); `es_abstracta` se ignora; pluralización heurística (no perfecta para irregulares); `orphanRemoval` se coloca en el lado `@OneToMany` real (no en el dueño/FK como decía la consigna original, porque JPA no permite ese atributo en `@ManyToOne`/`@ManyToMany` — confirmado correcto); los métodos UML no se generan.
- Un atributo del diagrama llamado "id" (cualquier variación de mayúsculas) se ignora al generar columnas — si no, chocaba con el `@Id` autogenerado (dos campos Java "id", no compila). Un tipo de atributo no reconocido (typo, tipo custom) no se valida al guardar el diagrama a propósito (`tipo` es texto libre de modelado general); el generador defaultea a `String` mostrando un comentario `// tipo UML "..." no reconocido` en el `.java`, en vez de fallar en silencio. Tests en `backend/tests/test_generador_spring.py` (incluye auditoría 1:1 de `MAPEO_TIPOS_JAVA`).
- CORS: `expose_headers=["Content-Disposition"]` en `main.py` — sin esto el navegador oculta ese header a JS y el frontend no puede leer el nombre real del `.zip` a descargar.
- Frontend: botón "Generar backend" en `Toolbar.tsx` (visible a cualquiera con acceso al proyecto, no solo al admin), con estado de carga ("Generando…", botón deshabilitado) y banner de error dismisseable (`app/api/generacion.ts` extrae el `detail` del error aunque la respuesta venga como `Blob` por el `responseType: 'blob'`).

### Reportes (CU07) — backend + frontend implementados

- **Actor: solo el administrador dueño** del proyecto (a diferencia de CU08/CU09, un colaborador NO tiene acceso, ni siquiera de lectura). `app/routers/reportes.py`: `GET /proyectos/{id}/reporte?formato=pdf` usa `obtener_proyecto_propio` explícitamente (no el `obtener_proyecto_con_acceso` genérico) — 403 si quien pide es colaborador o no tiene relación con el proyecto. 400 con "no hay contenido disponible para exportar" si el proyecto no tiene clases.
- Dos formatos con lógica completamente distinta:
  - **PDF** (backend): `app/services/generador_reporte.py` arma el PDF con **reportlab** — elegido sobre WeasyPrint porque es puro Python (WeasyPrint depende de GTK/Pango a nivel de sistema operativo, un dolor de cabeza extra en Windows) y esto es un reporte técnico simple (encabezado, clases con atributos/métodos, tabla de relaciones), no necesita el motor de layout HTML/CSS de WeasyPrint. Mismo patrón `StreamingResponse` + `Content-Disposition` que CU08 (reusa el `expose_headers=["Content-Disposition"]` de CORS en `main.py`).
  - **Imagen** (100% frontend, sin backend): captura el lienzo de React Flow a PNG en el navegador con **html-to-image** (la librería que la propia documentación de React Flow recomienda, compatible con v11) usando `getNodesBounds`/`getViewportForBounds` para encuadrar todas las clases — no llama a la API en absoluto.
- Frontend: `Toolbar.tsx` — `<select>` de formato (PDF/Imagen) + botón "Exportar reporte", **visibles solo si `user.id === project.id_administrador`** (ocultos por completo para colaboradores, no solo deshabilitados). El chequeo de "sin contenido" es client-side (mira `getNodes().length`) y corre antes de llamar a la API o a `toPng`, así que un proyecto vacío no dispara ni la descarga de imagen ni la petición PDF. `app/api/reportes.ts` seteador de blob análogo a `generacion.ts`.
- Tests en `backend/tests/test_reportes.py`: diagrama vacío → 400, con clases → 200/`application/pdf`, colaborador → 403, usuario sin relación → 403.

## Trabajo actual — Ciclo 1

Casos de uso, todos con **autenticación JWT**:

- **CU01** — Login — *backend + frontend hechos*
- **CU02** — Logout — *solo cliente (descartar token)* — hecho
- **CU03** — Perfil de usuario — *backend + frontend hechos* (`GET`/`PUT /usuarios/me`)
- **CU04** — Gestión de proyectos (CRUD) — *backend + frontend hechos*.
- **CU06** — Búsqueda de usuarios registrados — *backend + frontend hechos*. `GET /usuarios/buscar`.
- **CU05** — Gestión de integrantes/colaboradores (`<<include>>` CU06) — *backend + frontend hechos*. `app/routers/colaboradores.py` + `ColaboradoresModal.tsx` (buscador con debounce en vez de campo de email).
- **CU09** — Editor de diagrama de clases (React Flow) — *backend + frontend hechos*. En `/proyectos/:id`: crear/editar/eliminar clases con atributos, métodos, estereotipo y abstracción (arrastrables desde el grip superior del nodo; posición inicial en grilla, sin superponerse); relaciones tipadas (asociación/herencia/agregación/composición) con etiqueta y multiplicidad (`1`/`0..1`/`0..*`/`1..*`, select en el modal) **visibles en el lienzo** cerca de cada extremo de la línea (`RelacionEdge.tsx`, edge custom — los edges de fábrica de React Flow solo soportan una etiqueta centrada); autoguardado con debounce y reintento visible si falla el guardado. `guardar_diagrama` valida nombres de clase duplicados (409), que las relaciones solo referencien clases del propio payload (400) y que la multiplicidad sea una de las 4 válidas (400). Tests en `backend/tests/test_diagramas.py`.
- **CU08** — Generación de backend Spring Boot — *backend + frontend hechos*. Botón "Generar backend" en la toolbar del editor descarga el `.zip` (ver la sección de arriba para el detalle y las limitaciones conocidas).
- **CU07** — Gestión de reportes (PDF/Imagen) — *backend + frontend hechos*. Ver la sección "Reportes (CU07)" arriba.

### Colaboración en tiempo real (CU10) — backend implementado, frontend pendiente

- Librería elegida: **pycrdt + pycrdt-websocket** (paquete `pycrdt-websocket` en PyPI, pero desde la 0.16 el código vive bajo `pycrdt.websocket`, no `pycrdt_websocket`). Es el sucesor directo, activamente mantenido, de `y-py`/`ypy-websocket`: mismo mantenedor y org de GitHub (`y-crdt`, antes `jupyter-server`), `ypy-websocket` está formalmente abandonado y su propio README remite a `pycrdt-websocket`. Verificado al momento de implementar (sep. 2026): `pycrdt` 0.14.5 (ago. 2026) y `pycrdt-websocket` 0.16.4 (jul. 2026), ambos con releases recientes. `pycrdt` es un binding mixto Python/Rust (usa `yrs`, el puerto en Rust de Yjs) — más simple de mantener que el `y-py` 100%-Rust al que reemplaza.
- `app/routers/ws_diagramas.py`: endpoint `WS /ws/proyectos/{proyecto_id}/diagrama?token=<jwt>`. El JWT va por query param (los WebSockets del navegador no permiten headers `Authorization` custom). Se decodifica el token y se corre `obtener_proyecto_con_acceso` (mismo gate que CU09: dueño o colaborador activo) **antes** de `websocket.accept()` — si falla, se cierra con `websocket.close(code=...)` sin aceptar nunca la conexión (códigos privados RFC6455 4xxx: `4401` sin token/token inválido, `4403` sin acceso, `4404` proyecto inexistente). `FastAPIChannel` adapta el `WebSocket` de Starlette al protocolo `pycrdt.Channel` (`path`/`send`/`recv`/`__aiter__`) que espera `YRoom.serve()` — calcado del `HttpxWebsocket` que trae la librería de fábrica.
- `app/services/yjs_rooms.py`: un `GestorSalas` (singleton `gestor_salas`, referenciado por módulo — no por `from...import` — para que los tests puedan reemplazarlo) mantiene un `DiagramaRoom` por `proyecto_id` mientras haya al menos un cliente conectado. Cada room envuelve un `pycrdt.Doc` + un `pycrdt.websocket.YRoom` (que trae su propio `Awareness` de fábrica — no hace falta cablearlo a mano). Estructura del documento: `doc["clases"]` y `doc["relaciones"]` son `Y.Map` reales (no blobs JSON opacos) con `Y.Map` anidados por clase/atributo/método/relación, así cada campo (p. ej. `pos_x` al arrastrar una clase) es una entrada de CRDT independiente.
- Al conectar el primer cliente a un proyecto, el room se hidrata leyendo la BD (reutiliza `cargar_diagrama`). Cada cambio al documento (`doc.observe`) programa un guardado con debounce de `DEBOUNCE_SEGUNDOS = 4.0`s que vuelca el estado actual a las tablas normalizadas reutilizando `guardar_diagrama` (la misma función que usa el autoguardado HTTP de CU09 — la lógica de persistencia se extrajo a `app/services/diagrama.py`, no se duplicó). Al quedar el room sin clientes, se fuerza un guardado inmediato (cancela el debounce pendiente) antes de destruir el `Doc` en memoria; ese guardado corre bajo `asyncio.shield` porque algunos servidores/clientes (y el propio `TestClient` de Starlette en los tests) cancelan la tarea del handler apenas se detecta la desconexión, y sin el `shield` el guardado final se puede abortar a mitad de camino.
- Awareness (cursores; el cableado visual queda para el siguiente paso del frontend): se limpia solo — por el mensaje de desconexión que manda el cliente Yjs al cerrar la pestaña (protocolo estándar), o si no llegó, por el `outdated_timeout` de 30s de `pycrdt.Awareness`. No se agregó lógica propia de limpieza en el servidor porque `YRoom` ya la trae.
- Probado en `backend/tests/test_ws_diagramas.py` (7 tests) simulando clientes Yjs reales con las primitivas de bajo nivel de `pycrdt` (`create_sync_message`/`handle_sync_message`/`create_update_message`) contra el WebSocket real del backend, sin frontend:
  - **Dos conexiones simultáneas sincronizan en tiempo real**: cliente A edita → el servidor reenvía el update a B (y viceversa) — incluye drenar el "eco" que el servidor manda de vuelta al propio emisor (así mantiene viva la conexión, es comportamiento normal de Yjs, no un bug).
  - **Reconexión**: tras desconectar B, un tercer cliente que se conecta ve el estado *actual* del room (con los cambios de A y B), no una copia vieja recién leída de la BD.
  - **Persistencia tras debounce**: con `DEBOUNCE_SEGUNDOS` bajado a 0.3s vía `monkeypatch`, se edita sin desconectar y se confirma el guardado en BD pasado ese tiempo.
  - **Guardado final al desconectar**: se edita y se cierra la conexión sin esperar el debounce; se confirma que igual queda guardado (con reintentos cortos, porque corre en background protegido por `asyncio.shield`).
  - **Hidratación desde BD**: una clase ya existente en la tabla `clases_uml` aparece en el documento Yjs al conectarse.
  - **Rechazo antes de aceptar**: sin token (4401), usuario sin acceso al proyecto (4403), proyecto inexistente (4404) — las tres via `pytest.raises(WebSocketDisconnect)`.
  - Suite propia con su propio engine SQLite en memoria (no la fixture `db_session` de `conftest.py`) porque el guardado con debounce corre en un hilo aparte con su propia `Session`, vía `yjs_rooms.set_session_factory(...)` — necesita apuntar al mismo engine que el `get_db` sobreescrito para los endpoints HTTP/WS del test.
- Limitaciones/decisiones conocidas:
  - El campo `orphanRemoval`... no aplica acá; lo relevante para CU10: dos usuarios editando el **mismo campo de la misma clase** al mismo tiempo se resuelven por last-write-wins a nivel de esa entrada de `Y.Map` (no hay merge de texto tipo Y.Text en los campos, son valores atómicos) — aceptable para este caso de uso, ya lo advertía la auditoría de CU09 sobre el autoguardado HTTP.
  - Si el proceso del backend se reinicia o se mata (no un simple disconnect de un cliente), cualquier cambio dentro de la ventana de debounce (4s) que no haya llegado a guardarse se pierde — no hay un WAL/store persistente de los updates de Yjs entre reinicios (se decidió no usar `BaseYStore` para eso; el volcado a las tablas normalizadas ya es la fuente de verdad).
  - Frontend (cliente Yjs real, cursores de colaboración) queda para el siguiente paso — no se tocó nada de `frontend/` en esta tanda, tal como se pidió.

## Cierre Ciclo 2 (CU05, CU06, CU07) — auditoría

Revisión de cierre antes de empezar CU10. Estado confirmado:

- **CU05** (gestión de colaboradores), **CU06** (búsqueda de usuarios, `<<include>>` de CU05) y **CU07** (reportes PDF/Imagen) están **completos**, backend + frontend, con tests automatizados y un flujo manual end-to-end verificado con dos usuarios reales (administrador + colaborador) que encadenó los tres casos de uso: crear proyecto → buscar y agregar colaborador (nombre parcial) → el colaborador edita el diagrama (CU09 sigue funcionando) → el colaborador intenta generar un reporte y recibe 403 sin ver el control en su Toolbar → el administrador lo quita (soft-delete) → el colaborador pierde acceso (403 en `/diagrama`, el proyecto desaparece de su lista) → el administrador lo vuelve a agregar (reactivación) → el colaborador recupera acceso normalmente. Los 12 chequeos del flujo pasaron.
- Suite de tests backend: **69/69 passed** (`pytest -v` desde `backend/`, SQLite en memoria).

### Decisiones de diseño confirmadas en esta auditoría

- **Soft-delete con reactivación** (`ProyectoColaborador.activo`): quitar a un colaborador no borra la fila, solo la marca `activo=false`; volver a agregar al mismo usuario reactiva esa fila (`activo=true` + `fecha_asignacion` actualizada) en vez de violar la constraint única `(id_proyecto, id_usuario)` con una fila duplicada. Conserva historial y evita que la validación de "colaboradores activos" al eliminar un proyecto (CU04) se rompa con filas fantasma.
- **CU07 es el único caso de uso de esta tanda con acceso exclusivo al dueño** (ni siquiera lectura para colaboradores) — decisión explícita de la ficha, distinta de CU08/CU09 donde cualquiera con acceso (dueño o colaborador activo) puede operar. El frontend refleja esto ocultando el control por completo, no solo deshabilitándolo.
- **Agregar/quitar colaborador es por `usuario_id`** (resuelto vía la búsqueda de CU06), no por email ni por el id de la fila `ProyectoColaborador` — cambio de contrato respecto al CU04 original, ver sección de CU05/CU06 arriba.
- **PDF vía reportlab** (puro Python, sin dependencias de sistema) e **imagen vía html-to-image en el navegador** (sin pasar por el backend) — ver el razonamiento completo en la sección "Reportes (CU07)".

### Auditoría de control de acceso — endpoints de proyecto

Se revisó (por código, no solo por los tests) qué helper de `app/services/acceso.py` usa cada endpoint bajo `/proyectos`. Los dos helpers:
- `obtener_proyecto_con_acceso` → administrador dueño **o** colaborador activo.
- `obtener_proyecto_propio` → **solo** el administrador dueño.

| Endpoint | Método | Gate usado | CU | ¿Coincide con la ficha? |
|---|---|---|---|---|
| `/proyectos` | GET | (sin gate de un proyecto puntual — filtra por `usuario_actual.id`) | CU04 | Sí — lista proyectos propios + colaborados, no aplica a un solo proyecto |
| `/proyectos` | POST | (sin gate — crea como propio) | CU04 | Sí |
| `/proyectos/{id}` | PUT | `obtener_proyecto_propio` | CU04 | Sí — solo el dueño edita |
| `/proyectos/{id}` | DELETE | `obtener_proyecto_propio` | CU04 | Sí — solo el dueño elimina |
| `/usuarios/buscar?proyecto_id=` | GET | `obtener_proyecto_con_acceso` | CU06 | Sí — dueño o colaborador puede buscar (coherente con que también puede listar colaboradores) |
| `/proyectos/{id}/colaboradores` | GET | `obtener_proyecto_con_acceso` | CU05 | Sí — dueño o colaborador activo ve la lista |
| `/proyectos/{id}/colaboradores` | POST | `obtener_proyecto_propio` | CU05 | Sí — solo el dueño agrega |
| `/proyectos/{id}/colaboradores/{usuario_id}` | DELETE | `obtener_proyecto_propio` | CU05 | Sí — solo el dueño quita |
| `/proyectos/{id}/diagrama` | GET / PUT | `obtener_proyecto_con_acceso` | CU09 | Sí — dueño o colaborador activo |
| `/proyectos/{id}/generar-backend` | POST | `obtener_proyecto_con_acceso` | CU08 | Sí (decisión de diseño explícita: cualquiera con acceso genera, no solo el dueño) |
| `/proyectos/{id}/reporte` | GET | `obtener_proyecto_propio` | CU07 | Sí — solo el dueño, a diferencia de CU08 |

**Resultado: no se encontró ningún endpoint con el criterio de acceso equivocado.** La división coincide en los 12 endpoints con lo que pide cada ficha de caso de uso.

### Limitaciones conocidas que siguen vigentes (no perder de vista)

- **CU08** (generación Spring Boot): `HERENCIA` se mapea como asociación simple (sin `@Inheritance`); `es_abstracta` se ignora; pluralización heurística (no perfecta para irregulares en español); `orphanRemoval` va en el lado `@OneToMany` real en vez del dueño/FK (JPA no lo permite ahí); los métodos UML no se generan; backend generado sin JWT. Detalle completo en la sección "Generación de backend Spring Boot (CU08)" arriba.
- **CU09** (editor de diagrama): el `PUT /diagrama` reemplaza el diagrama completo (sin edición incremental por campo); dos usuarios editando el mismo proyecto en simultáneo pueden pisarse el autoguardado del otro (no hay locking ni merge, algo a tener en cuenta ahora que CU05 habilita colaboración real).
- **CU07** (reportes): el PDF es un reporte de texto estructurado (clases/atributos/métodos + tabla de relaciones), no renderiza el diagrama visual con cajas y flechas — si se pide eso más adelante, es una mejora aparte.

### Pendiente (ciclos posteriores)

- **CU15** — Generación automática de código frontend a partir del diagrama.

## Comandos

### Backend (desde `backend/`)

```bash
venv\Scripts\activate                       # Windows PowerShell
uvicorn app.main:app --reload               # servidor de desarrollo (http://localhost:8000/docs)
python -m app.seed                           # crea el usuario admin de prueba (idempotente)
alembic revision --autogenerate -m "msg"    # nueva migración
alembic upgrade head                        # aplicar migraciones
pytest -v                                   # tests (SQLite en memoria, no toca la BD real)
```

Usuario de prueba creado por el seed: `admin@diagramador.com` / `admin12345` (rol `ADMINISTRADOR`).

### Frontend (desde `frontend/`)

```bash
npm run dev       # servidor Vite (http://localhost:5173)
npm run build     # tsc -b && vite build
npm run lint      # oxlint
```

- URL de la API: `VITE_API_URL` en `frontend/.env` (por defecto `http://localhost:8000`).
- Rutas: `/login`, `/registro`, `/` (lista de proyectos, CU04), `/perfil` (CU03), `/proyectos/:id` (editor, CU09).
- Auth: token JWT en `localStorage`; `src/auth/` (contexto + `useAuth` + `RequireAuth`);
  cliente HTTP y funciones por endpoint en `src/api/`.
- Sistema de diseño: `src/styles/tokens.css` (variables CSS) + `src/components/ui/`
  (`Button`, `TextField`, `Modal`, `Banner`). Estética "mesa de dibujo técnico".
- Editor de diagrama (CU09): `src/components/shell/` (`AppShell`, `CanvasArea`, `ClassNode`,
  `Sidebar`, `Toolbar`, `RelacionEditorModal`, `RelacionEdge.tsx`, `umlFormat.ts`, `UmlMarkers.tsx`) + hook
  `useDiagrama.ts` (estado de React Flow, autoguardado). `src/pages/ColaboradoresModal.tsx`
  gestiona colaboradores (CU05, con buscador de CU06) — ver sección de CU05/CU06 arriba.

## Notas para trabajar en este repo

- Al crear un modelo nuevo, exportarlo en `backend/app/models/__init__.py` para que Alembic lo detecte.
- Mantener las respuestas de la API y los esquemas Pydantic separados de los modelos ORM.
- Priorizar avanzar el Ciclo 1; no adelantar trabajo de CU15 salvo que se pida.
