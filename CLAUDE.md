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
  routers/           # auth, usuarios, proyectos, diagramas, generacion
  services/          # acceso.py (control de acceso a proyecto compartido), generador_spring.py (CU08)
backend/alembic/     # migraciones
```

### Autenticación (Ciclo 1) — ya implementada

- JWT con `python-jose`; hashing con `passlib` + `bcrypt` (fijado en `4.0.1`, no subir sin quitar passlib).
- `app/core/security.py`: hash/verificación de contraseñas y creación/decodificación de tokens.
- `app/routers/auth.py`: `POST /auth/login` (form OAuth2, el campo `username` es el email) + dependencia reutilizable `get_current_user` para proteger endpoints.
- `app/routers/usuarios.py`: `GET`/`PUT /usuarios/me` (CU03).
- `app/routers/proyectos.py`: CRUD de proyectos (CU04); solo el administrador dueño modifica/elimina; `DELETE` con colaboradores activos exige `?confirmar=true` (si no, 409).
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
- `app/services/acceso.py`: `obtener_proyecto_con_acceso` (dueño o colaborador activo) — compartida con CU08.

### Generación de backend Spring Boot (CU08) — backend + frontend implementados

- `app/routers/generacion.py`: `POST /proyectos/{id}/generar-backend`, mismo control de acceso que CU09; 400 si el proyecto no tiene clases todavía. Devuelve un `.zip` (proyecto Maven completo) como `StreamingResponse`.
- `app/services/generador_spring.py`: arma el `.zip` a partir de `clases_uml`/`atributos`/`relaciones` — entidades JPA (`@Entity`/`@Table`/`@Column`, Lombok `@Getter/@Setter`), `Repository`/`Service`/`Controller` (CRUD, rutas `/api/{plural}`), `pom.xml` (Spring Boot 3.2.5, Java 17) y `application.properties` de plantilla (sin JWT todavía). Mapeo de tipos UML→Java y de multiplicidad→anotación JPA documentados en el encabezado del módulo.
- Limitaciones conocidas: `HERENCIA` se mapea como asociación simple (sin `@Inheritance`); `es_abstracta` se ignora; pluralización heurística (no perfecta para irregulares); `orphanRemoval` se coloca en el lado `@OneToMany` real (no en el dueño/FK como decía la consigna original, porque JPA no permite ese atributo en `@ManyToOne`/`@ManyToMany` — confirmado correcto); los métodos UML no se generan. Tests en `backend/tests/test_generador_spring.py`.
- CORS: `expose_headers=["Content-Disposition"]` en `main.py` — sin esto el navegador oculta ese header a JS y el frontend no puede leer el nombre real del `.zip` a descargar.
- Frontend: botón "Generar backend" en `Toolbar.tsx` (visible a cualquiera con acceso al proyecto, no solo al admin), con estado de carga ("Generando…", botón deshabilitado) y banner de error dismisseable (`app/api/generacion.ts` extrae el `detail` del error aunque la respuesta venga como `Blob` por el `responseType: 'blob'`).

## Trabajo actual — Ciclo 1

Casos de uso, todos con **autenticación JWT**:

- **CU01** — Login — *backend + frontend hechos*
- **CU02** — Logout — *solo cliente (descartar token)* — hecho
- **CU03** — Perfil de usuario — *backend + frontend hechos* (`GET`/`PUT /usuarios/me`)
- **CU04** — Gestión de proyectos (CRUD) — *backend + frontend hechos*, incluida la asignación de colaboradores (`POST`/`GET`/`DELETE /proyectos/{id}/colaboradores`, `ColaboradoresModal.tsx`).
- **CU09** — Editor de diagrama de clases (React Flow) — *backend + frontend hechos*. En `/proyectos/:id`: crear/editar/eliminar clases con atributos, métodos, estereotipo y abstracción (arrastrables desde el grip superior del nodo; posición inicial en grilla, sin superponerse); relaciones tipadas (asociación/herencia/agregación/composición) con etiqueta y multiplicidad (`1`/`0..1`/`0..*`/`1..*`, select en el modal); autoguardado con debounce y reintento visible si falla el guardado. `guardar_diagrama` valida nombres de clase duplicados (409), que las relaciones solo referencien clases del propio payload (400) y que la multiplicidad sea una de las 4 válidas (400). Tests en `backend/tests/test_diagramas.py`.
- **CU08** — Generación de backend Spring Boot — *backend + frontend hechos*. Botón "Generar backend" en la toolbar del editor descarga el `.zip` (ver la sección de arriba para el detalle y las limitaciones conocidas).

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
  `Sidebar`, `Toolbar`, `RelacionEditorModal`, `umlFormat.ts`, `UmlMarkers.tsx`) + hook
  `useDiagrama.ts` (estado de React Flow, autoguardado). `src/pages/ColaboradoresModal.tsx`
  gestiona colaboradores de CU04.

## Notas para trabajar en este repo

- Al crear un modelo nuevo, exportarlo en `backend/app/models/__init__.py` para que Alembic lo detecte.
- Mantener las respuestas de la API y los esquemas Pydantic separados de los modelos ORM.
- Priorizar avanzar el Ciclo 1; no adelantar trabajo de CU15 salvo que se pida.
