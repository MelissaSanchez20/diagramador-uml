import pytest

from app.models.usuario import RolUsuario
from app.models.clase_uml import ClaseUml
from app.services import comandos_voz


def _mock_llamada(monkeypatch, nombre_tool, argumentos):
    monkeypatch.setattr(
        comandos_voz, "_llamar_openai", lambda texto, prompt: (nombre_tool, argumentos)
    )


def _crear_clase(db_session, proyecto, nombre="Cliente"):
    import uuid

    clase = ClaseUml(id=str(uuid.uuid4()), id_proyecto=proyecto.id, nombre=nombre)
    db_session.add(clase)
    db_session.commit()
    db_session.refresh(clase)
    return clase


class TestCrearClase:
    def test_sin_atributos(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _mock_llamada(monkeypatch, "crear_clase", {"nombre_clase": "Pedido", "atributos": []})

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "crea una clase Pedido"},
            headers=headers(admin),
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert datos["accion"] == "crear_clase"
        assert datos["nombre_clase"] == "Pedido"
        assert datos["atributos"] == []

    def test_con_atributos(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _mock_llamada(
            monkeypatch,
            "crear_clase",
            {
                "nombre_clase": "Cliente",
                "atributos": [
                    {"nombre": "nombre", "tipo": "String", "visibilidad": "PRIVADO"},
                    {"nombre": "correo", "tipo": "String", "visibilidad": "PRIVADO"},
                ],
            },
        )

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "crea una clase Cliente con atributos nombre y correo"},
            headers=headers(admin),
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert len(datos["atributos"]) == 2
        assert all("id" not in a for a in datos["atributos"])

    def test_nombre_duplicado(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _crear_clase(db_session, proyecto, "Cliente")
        _mock_llamada(monkeypatch, "crear_clase", {"nombre_clase": "cliente", "atributos": []})

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "crea una clase Cliente"},
            headers=headers(admin),
        )
        assert resp.status_code == 422


class TestAgregarAtributo:
    def test_exitoso(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        clase = _crear_clase(db_session, proyecto, "Cliente")
        _mock_llamada(
            monkeypatch,
            "agregar_atributo",
            {"nombre_clase": "Cliente", "nombre": "telefono", "tipo": "String", "visibilidad": "PUBLICO"},
        )

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "agrega el atributo telefono a la clase Cliente"},
            headers=headers(admin),
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert datos["accion"] == "agregar_atributo"
        assert datos["id_clase"] == clase.id
        assert datos["atributo"]["nombre"] == "telefono"

    def test_clase_no_encontrada(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _mock_llamada(
            monkeypatch,
            "agregar_atributo",
            {"nombre_clase": "Factura", "nombre": "monto", "tipo": "float", "visibilidad": "PRIVADO"},
        )

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "agrega el atributo monto a la clase Factura"},
            headers=headers(admin),
        )
        assert resp.status_code == 422
        assert "Factura" in resp.json()["detail"]


class TestEliminarClase:
    def test_exitoso(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        clase = _crear_clase(db_session, proyecto, "Pedido")
        _mock_llamada(monkeypatch, "eliminar_clase", {"nombre_clase": "Pedido"})

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "elimina la clase Pedido"},
            headers=headers(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["id_clase"] == clase.id


class TestCrearRelacion:
    def test_con_multiplicidad(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        origen = _crear_clase(db_session, proyecto, "Usuario")
        destino = _crear_clase(db_session, proyecto, "Pedido")
        _mock_llamada(
            monkeypatch,
            "crear_relacion",
            {
                "nombre_clase_origen": "Usuario",
                "nombre_clase_destino": "Pedido",
                "tipo_relacion": "ASOCIACION",
                "multiplicidad_origen": "1",
                "multiplicidad_destino": "0..*",
            },
        )

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "crea una relacion de asociacion entre Usuario y Pedido"},
            headers=headers(admin),
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert datos["id_clase_origen"] == origen.id
        assert datos["id_clase_destino"] == destino.id
        assert datos["tipo"] == "ASOCIACION"

    def test_sin_multiplicidad(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _crear_clase(db_session, proyecto, "Usuario")
        _crear_clase(db_session, proyecto, "Pedido")
        _mock_llamada(
            monkeypatch,
            "crear_relacion",
            {
                "nombre_clase_origen": "Usuario",
                "nombre_clase_destino": "Pedido",
                "tipo_relacion": "HERENCIA",
                "multiplicidad_origen": None,
                "multiplicidad_destino": None,
            },
        )

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "Pedido hereda de Usuario"},
            headers=headers(admin),
        )
        assert resp.status_code == 200


class TestRenombrarClase:
    def test_exitoso(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        clase = _crear_clase(db_session, proyecto, "Cliente")
        _mock_llamada(monkeypatch, "renombrar_clase", {"nombre_actual": "Cliente", "nombre_nuevo": "Usuario"})

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "cambia el nombre de la clase Cliente a Usuario"},
            headers=headers(admin),
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert datos["id_clase"] == clase.id
        assert datos["nombre_anterior"] == "Cliente"
        assert datos["nombre_nuevo"] == "Usuario"


class TestErroresGenerales:
    def test_comando_no_mapeable(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _mock_llamada(monkeypatch, None, None)

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "cambia el color de fondo"},
            headers=headers(admin),
        )
        assert resp.status_code == 422

    def test_argumentos_invalidos(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _crear_clase(db_session, proyecto, "Usuario")
        _crear_clase(db_session, proyecto, "Pedido")
        _mock_llamada(
            monkeypatch,
            "crear_relacion",
            {
                "nombre_clase_origen": "Usuario",
                "nombre_clase_destino": "Pedido",
                "tipo_relacion": "NO_EXISTE",
                "multiplicidad_origen": None,
                "multiplicidad_destino": None,
            },
        )

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "algo raro"},
            headers=headers(admin),
        )
        assert resp.status_code == 422

    def test_openai_no_disponible(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)

        def _falla(texto, prompt):
            raise comandos_voz.ComandoVozNoDisponibleError("timeout")

        monkeypatch.setattr(comandos_voz, "_llamar_openai", _falla)

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "crea una clase Cliente"},
            headers=headers(admin),
        )
        assert resp.status_code == 503

    def test_sin_acceso(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        otro = crear_usuario()
        proyecto = crear_proyecto(admin)
        _mock_llamada(monkeypatch, "crear_clase", {"nombre_clase": "Pedido", "atributos": []})

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "crea una clase Pedido"},
            headers=headers(otro),
        )
        assert resp.status_code == 403

    def test_proyecto_inexistente(self, client, db_session, crear_usuario, headers, monkeypatch):
        admin = crear_usuario()
        _mock_llamada(monkeypatch, "crear_clase", {"nombre_clase": "Pedido", "atributos": []})

        resp = client.post(
            "/proyectos/999999/comandos-voz",
            json={"texto": "crea una clase Pedido"},
            headers=headers(admin),
        )
        assert resp.status_code == 404

    def test_colaborador_activo_puede_usarlo(
        self, client, db_session, crear_usuario, crear_proyecto, agregar_colaborador, headers, monkeypatch
    ):
        admin = crear_usuario()
        colaborador = crear_usuario(rol=RolUsuario.COLABORADOR)
        proyecto = crear_proyecto(admin)
        agregar_colaborador(proyecto, colaborador)
        _mock_llamada(monkeypatch, "crear_clase", {"nombre_clase": "Pedido", "atributos": []})

        resp = client.post(
            f"/proyectos/{proyecto.id}/comandos-voz",
            json={"texto": "crea una clase Pedido"},
            headers=headers(colaborador),
        )
        assert resp.status_code == 200
