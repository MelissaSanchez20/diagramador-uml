import io
import zipfile

from app.models.atributo import Atributo, VisibilidadMiembro
from app.models.clase_uml import ClaseUml
from app.models.relacion import Relacion, TipoRelacion


def _crear_diagrama_persona_direccion(db_session, proyecto):
    """2 clases con una relación singular-plural (Persona 1 --- 0..* Direccion)."""
    persona = ClaseUml(id="persona-id", id_proyecto=proyecto.id, nombre="Persona", es_abstracta=False, pos_x=0, pos_y=0)
    persona.atributos = [
        Atributo(id="attr-nombre", nombre="nombre", tipo="string", visibilidad=VisibilidadMiembro.PRIVADO, orden=0)
    ]
    direccion = ClaseUml(id="direccion-id", id_proyecto=proyecto.id, nombre="Direccion", es_abstracta=False, pos_x=0, pos_y=0)
    direccion.atributos = [
        Atributo(id="attr-ciudad", nombre="ciudad", tipo="string", visibilidad=VisibilidadMiembro.PRIVADO, orden=0)
    ]
    db_session.add(persona)
    db_session.add(direccion)
    db_session.commit()

    relacion = Relacion(
        id="rel-1",
        id_proyecto=proyecto.id,
        id_clase_origen=persona.id,
        id_clase_destino=direccion.id,
        tipo=TipoRelacion.ASOCIACION,
        multiplicidad_origen="1",
        multiplicidad_destino="0..*",
    )
    db_session.add(relacion)
    db_session.commit()


def test_generar_backend_con_relacion_singular_plural(client, crear_usuario, crear_proyecto, headers, db_session):
    admin = crear_usuario()
    proyecto = crear_proyecto(admin)
    _crear_diagrama_persona_direccion(db_session, proyecto)

    resp = client.post(f"/proyectos/{proyecto.id}/generar-backend", headers=headers(admin))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    nombres = zf.namelist()

    # Estructura Maven esperada.
    assert any(n.endswith("pom.xml") for n in nombres)
    assert any(n.endswith("src/main/resources/application.properties") for n in nombres)
    assert any(n.endswith("BackendApplication.java") for n in nombres)
    assert any(n.endswith("model/Persona.java") for n in nombres)
    assert any(n.endswith("model/Direccion.java") for n in nombres)
    assert any(n.endswith("repository/PersonaRepository.java") for n in nombres)
    assert any(n.endswith("repository/DireccionRepository.java") for n in nombres)
    assert any(n.endswith("service/PersonaService.java") for n in nombres)
    assert any(n.endswith("service/DireccionService.java") for n in nombres)
    assert any(n.endswith("controller/PersonaController.java") for n in nombres)
    assert any(n.endswith("controller/DireccionController.java") for n in nombres)

    # Direccion es el lado "muchos" -> dueño de la FK -> @ManyToOne hacia Persona.
    direccion_java = next(n for n in nombres if n.endswith("model/Direccion.java"))
    contenido_direccion = zf.read(direccion_java).decode("utf-8")
    assert "@ManyToOne" in contenido_direccion
    assert '@JoinColumn(name = "persona_id")' in contenido_direccion
    assert "private Persona persona;" in contenido_direccion

    # Persona es el lado "uno" -> inverso, @OneToMany(mappedBy = "persona").
    persona_java = next(n for n in nombres if n.endswith("model/Persona.java"))
    contenido_persona = zf.read(persona_java).decode("utf-8")
    assert '@OneToMany(mappedBy = "persona")' in contenido_persona
    assert "private List<Direccion> direccionList;" in contenido_persona

    # El endpoint del controller REST sigue /api/{plural minúscula}.
    controller_direccion = next(n for n in nombres if n.endswith("controller/DireccionController.java"))
    contenido_controller = zf.read(controller_direccion).decode("utf-8")
    assert '@RequestMapping("/api/direcciones")' in contenido_controller


def test_etiqueta_de_relacion_no_se_usa_como_nombre_de_campo(client, crear_usuario, crear_proyecto, headers, db_session):
    """Regresión: con `etiqueta` seteada, el campo/columna de la relación
    debía seguir nombrándose según la clase destino real (ej. "persona" /
    "persona_id" en Direccion), no según la etiqueta (ej. "direcciones")."""
    admin = crear_usuario()
    proyecto = crear_proyecto(admin)

    persona = ClaseUml(id="persona-id", id_proyecto=proyecto.id, nombre="Persona", es_abstracta=False, pos_x=0, pos_y=0)
    direccion = ClaseUml(id="direccion-id", id_proyecto=proyecto.id, nombre="Direccion", es_abstracta=False, pos_x=0, pos_y=0)
    db_session.add(persona)
    db_session.add(direccion)
    db_session.commit()

    relacion = Relacion(
        id="rel-1",
        id_proyecto=proyecto.id,
        id_clase_origen=persona.id,
        id_clase_destino=direccion.id,
        tipo=TipoRelacion.ASOCIACION,
        etiqueta="direcciones",  # etiqueta distinta al nombre de cualquiera de las dos clases
        multiplicidad_origen="1",
        multiplicidad_destino="0..*",
    )
    db_session.add(relacion)
    db_session.commit()

    resp = client.post(f"/proyectos/{proyecto.id}/generar-backend", headers=headers(admin))
    assert resp.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    direccion_java = next(n for n in zf.namelist() if n.endswith("model/Direccion.java"))
    contenido = zf.read(direccion_java).decode("utf-8")

    # El campo y la FK deben nombrarse según la clase destino (Persona), no
    # según la etiqueta ("direcciones") — @Table(name = "direcciones") sí es
    # correcto (nombre de tabla pluralizado de la propia clase Direccion).
    assert "private Persona persona;" in contenido
    assert '@JoinColumn(name = "persona_id")' in contenido
    assert '@JoinColumn(name = "direcciones_id")' not in contenido
    assert "private Persona direcciones;" not in contenido


def test_generar_backend_sin_clases_devuelve_400(client, crear_usuario, crear_proyecto, headers):
    admin = crear_usuario()
    proyecto = crear_proyecto(admin)  # sin clases en el diagrama

    resp = client.post(f"/proyectos/{proyecto.id}/generar-backend", headers=headers(admin))
    assert resp.status_code == 400
    assert "no tiene clases" in resp.json()["detail"]


def test_generar_backend_requiere_acceso(client, crear_usuario, crear_proyecto, headers, db_session):
    admin = crear_usuario()
    otro = crear_usuario()
    proyecto = crear_proyecto(admin)
    _crear_diagrama_persona_direccion(db_session, proyecto)

    resp = client.post(f"/proyectos/{proyecto.id}/generar-backend", headers=headers(otro))
    assert resp.status_code == 403


def test_generar_backend_composicion_agrega_cascade_y_orphan_removal_en_el_padre(
    client, crear_usuario, crear_proyecto, headers, db_session
):
    admin = crear_usuario()
    proyecto = crear_proyecto(admin)

    pedido = ClaseUml(id="pedido-id", id_proyecto=proyecto.id, nombre="Pedido", es_abstracta=False, pos_x=0, pos_y=0)
    item = ClaseUml(id="item-id", id_proyecto=proyecto.id, nombre="Item", es_abstracta=False, pos_x=0, pos_y=0)
    db_session.add(pedido)
    db_session.add(item)
    db_session.commit()

    relacion = Relacion(
        id="rel-comp",
        id_proyecto=proyecto.id,
        id_clase_origen=pedido.id,
        id_clase_destino=item.id,
        tipo=TipoRelacion.COMPOSICION,
        multiplicidad_origen="1",
        multiplicidad_destino="0..*",
    )
    db_session.add(relacion)
    db_session.commit()

    resp = client.post(f"/proyectos/{proyecto.id}/generar-backend", headers=headers(admin))
    assert resp.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    pedido_java = next(n for n in zf.namelist() if n.endswith("model/Pedido.java"))
    contenido_pedido = zf.read(pedido_java).decode("utf-8")
    # cascade + orphanRemoval van en el lado @OneToMany (el "padre" real),
    # no en el @ManyToOne — ver limitación documentada en generador_spring.py.
    assert "cascade = CascadeType.ALL, orphanRemoval = true" in contenido_pedido

    item_java = next(n for n in zf.namelist() if n.endswith("model/Item.java"))
    contenido_item = zf.read(item_java).decode("utf-8")
    assert "orphanRemoval" not in contenido_item
