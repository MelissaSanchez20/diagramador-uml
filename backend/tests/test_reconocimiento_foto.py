import io
import uuid

import pytest
from PIL import Image

from app.models.usuario import RolUsuario
from app.models.clase_uml import ClaseUml
from app.schemas.reconocimiento_foto import (
    AtributoDetectadoIO,
    ClaseDetectadaIO,
    ReconocimientoFotoResultado,
    RelacionDetectadaIO,
)
from app.services import reconocimiento_foto


def _png_bytes(ancho=20, alto=20) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (ancho, alto), "white").save(buf, format="PNG")
    return buf.getvalue()


def _mock_llamada(monkeypatch, resultado: ReconocimientoFotoResultado):
    monkeypatch.setattr(reconocimiento_foto, "_llamar_openai_reconocimiento", lambda *_: resultado)


def _mock_llamada_no_debe_llamarse(monkeypatch):
    def _falla(*_):
        raise AssertionError("no debería haberse llamado a OpenAI -- la validación de archivo tendría que cortar antes")

    monkeypatch.setattr(reconocimiento_foto, "_llamar_openai_reconocimiento", _falla)


def _crear_clase(db_session, proyecto, nombre="ClaseExistente"):
    clase = ClaseUml(id=str(uuid.uuid4()), id_proyecto=proyecto.id, nombre=nombre)
    db_session.add(clase)
    db_session.commit()
    db_session.refresh(clase)
    return clase


_RESULTADO_DOS_CLASES = ReconocimientoFotoResultado(
    reconocido=True,
    mensaje="Se detectaron 2 clases y 1 relación.",
    clases=[
        ClaseDetectadaIO(nombre="Cliente", atributos=[AtributoDetectadoIO(nombre="nombre", tipo="String")]),
        ClaseDetectadaIO(nombre="Pedido", atributos=[AtributoDetectadoIO(nombre="total", tipo="float")]),
    ],
    relaciones=[
        RelacionDetectadaIO(
            clase_origen="Cliente", clase_destino="Pedido", tipo="ASOCIACION",
            multiplicidad_origen="1", multiplicidad_destino="0..*",
        )
    ],
)


class TestReconocer:
    def test_imagen_valida_con_clases(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _mock_llamada(monkeypatch, _RESULTADO_DOS_CLASES)

        resp = client.post(
            f"/proyectos/{proyecto.id}/reconocimiento-foto",
            files={"archivo": ("diagrama.png", _png_bytes(), "image/png")},
            headers=headers(admin),
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert datos["reconocido"] is True
        assert len(datos["clases"]) == 2
        assert len(datos["relaciones"]) == 1

    def test_imagen_sin_contenido_reconocible(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _mock_llamada(
            monkeypatch,
            ReconocimientoFotoResultado(reconocido=False, mensaje="La imagen no parece contener un diagrama UML.", clases=[], relaciones=[]),
        )

        resp = client.post(
            f"/proyectos/{proyecto.id}/reconocimiento-foto",
            files={"archivo": ("foto.png", _png_bytes(), "image/png")},
            headers=headers(admin),
        )
        assert resp.status_code == 400
        assert "no parece" in resp.json()["detail"]

    def test_tipo_de_archivo_invalido_no_llama_a_openai(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _mock_llamada_no_debe_llamarse(monkeypatch)

        resp = client.post(
            f"/proyectos/{proyecto.id}/reconocimiento-foto",
            files={"archivo": ("documento.pdf", b"%PDF-1.4 no es una imagen", "application/pdf")},
            headers=headers(admin),
        )
        assert resp.status_code == 400
        assert "Formato de imagen no soportado" in resp.json()["detail"]

    def test_archivo_demasiado_grande_no_llama_a_openai(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _mock_llamada_no_debe_llamarse(monkeypatch)

        contenido_grande = b"\x00" * (10 * 1024 * 1024 + 1)
        resp = client.post(
            f"/proyectos/{proyecto.id}/reconocimiento-foto",
            files={"archivo": ("grande.png", contenido_grande, "image/png")},
            headers=headers(admin),
        )
        assert resp.status_code == 400
        assert "grande" in resp.json()["detail"]

    def test_sin_acceso(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        admin = crear_usuario()
        otro = crear_usuario()
        proyecto = crear_proyecto(admin)
        _mock_llamada(monkeypatch, _RESULTADO_DOS_CLASES)

        resp = client.post(
            f"/proyectos/{proyecto.id}/reconocimiento-foto",
            files={"archivo": ("diagrama.png", _png_bytes(), "image/png")},
            headers=headers(otro),
        )
        assert resp.status_code == 403

    def test_clase_duplicada_exacta_se_colapsa(self, client, db_session, crear_usuario, crear_proyecto, headers, monkeypatch):
        # El modelo de visión ocasionalmente repite una clase idéntica dos
        # veces en el mismo resultado (verificado contra la API real) --
        # `_sin_clases_duplicadas` la colapsa antes de mostrar la vista previa.
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        resultado_con_duplicado = ReconocimientoFotoResultado(
            reconocido=True,
            mensaje="Se detectaron 2 clases y 1 relación.",
            clases=[
                ClaseDetectadaIO(nombre="Cliente", atributos=[AtributoDetectadoIO(nombre="nombre", tipo="String")]),
                ClaseDetectadaIO(nombre="Pedido", atributos=[AtributoDetectadoIO(nombre="total", tipo="float")]),
                ClaseDetectadaIO(nombre="Cliente", atributos=[AtributoDetectadoIO(nombre="nombre", tipo="String")]),
            ],
            relaciones=[],
        )
        _mock_llamada(monkeypatch, resultado_con_duplicado)

        resp = client.post(
            f"/proyectos/{proyecto.id}/reconocimiento-foto",
            files={"archivo": ("diagrama.png", _png_bytes(), "image/png")},
            headers=headers(admin),
        )
        assert resp.status_code == 200
        nombres = [c["nombre"] for c in resp.json()["clases"]]
        assert nombres == ["Cliente", "Pedido"]

    def test_colaborador_activo_puede_usarlo(
        self, client, db_session, crear_usuario, crear_proyecto, agregar_colaborador, headers, monkeypatch
    ):
        admin = crear_usuario()
        colaborador = crear_usuario(rol=RolUsuario.COLABORADOR)
        proyecto = crear_proyecto(admin)
        agregar_colaborador(proyecto, colaborador)
        _mock_llamada(monkeypatch, _RESULTADO_DOS_CLASES)

        resp = client.post(
            f"/proyectos/{proyecto.id}/reconocimiento-foto",
            files={"archivo": ("diagrama.png", _png_bytes(), "image/png")},
            headers=headers(colaborador),
        )
        assert resp.status_code == 200


class TestConfirmar:
    def test_agrega_sobre_proyecto_con_clases_existentes(self, client, db_session, crear_usuario, crear_proyecto, headers):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _crear_clase(db_session, proyecto, "Existente")

        resp = client.post(
            f"/proyectos/{proyecto.id}/reconocimiento-foto/confirmar",
            json=_RESULTADO_DOS_CLASES.model_dump(),
            headers=headers(admin),
        )
        assert resp.status_code == 200
        datos = resp.json()
        nombres = {c["nombre"] for c in datos["diagrama"]["clases"]}
        assert nombres == {"Existente", "Cliente", "Pedido"}
        assert datos["advertencias"] == []

    def test_colision_de_nombre_renombra_con_sufijo(self, client, db_session, crear_usuario, crear_proyecto, headers):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        _crear_clase(db_session, proyecto, "Cliente")

        resp = client.post(
            f"/proyectos/{proyecto.id}/reconocimiento-foto/confirmar",
            json=_RESULTADO_DOS_CLASES.model_dump(),
            headers=headers(admin),
        )
        assert resp.status_code == 200
        datos = resp.json()
        nombres = {c["nombre"] for c in datos["diagrama"]["clases"]}
        assert "Cliente 2" in nombres
        assert "Cliente" in nombres
        assert any("renombró" in a for a in datos["advertencias"])
        # La relación detectada seguía apuntando a "Cliente" (nombre original
        # detectado) -> tiene que resolver contra la clase recién creada
        # ("Cliente 2"), no contra la preexistente.
        relacion = datos["diagrama"]["relaciones"][0]
        clase_cliente_2 = next(c for c in datos["diagrama"]["clases"] if c["nombre"] == "Cliente 2")
        assert relacion["id_clase_origen"] == clase_cliente_2["id"]

    def test_relacion_a_clase_no_detectada_se_descarta(self, client, db_session, crear_usuario, crear_proyecto, headers):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        resultado = ReconocimientoFotoResultado(
            reconocido=True,
            mensaje="1 clase",
            clases=[ClaseDetectadaIO(nombre="Solitaria", atributos=[])],
            relaciones=[
                RelacionDetectadaIO(clase_origen="Solitaria", clase_destino="Fantasma", tipo="ASOCIACION")
            ],
        )

        resp = client.post(
            f"/proyectos/{proyecto.id}/reconocimiento-foto/confirmar",
            json=resultado.model_dump(),
            headers=headers(admin),
        )
        assert resp.status_code == 200
        datos = resp.json()
        assert datos["diagrama"]["relaciones"] == []
        assert any("descartó una relación" in a for a in datos["advertencias"])

    def test_sin_clases_es_400(self, client, db_session, crear_usuario, crear_proyecto, headers):
        admin = crear_usuario()
        proyecto = crear_proyecto(admin)
        resultado = ReconocimientoFotoResultado(reconocido=False, mensaje="nada", clases=[], relaciones=[])

        resp = client.post(
            f"/proyectos/{proyecto.id}/reconocimiento-foto/confirmar",
            json=resultado.model_dump(),
            headers=headers(admin),
        )
        assert resp.status_code == 400

    def test_sin_acceso(self, client, db_session, crear_usuario, crear_proyecto, headers):
        admin = crear_usuario()
        otro = crear_usuario()
        proyecto = crear_proyecto(admin)

        resp = client.post(
            f"/proyectos/{proyecto.id}/reconocimiento-foto/confirmar",
            json=_RESULTADO_DOS_CLASES.model_dump(),
            headers=headers(otro),
        )
        assert resp.status_code == 403

    def test_proyecto_inexistente(self, client, db_session, crear_usuario, headers):
        admin = crear_usuario()

        resp = client.post(
            "/proyectos/999999/reconocimiento-foto/confirmar",
            json=_RESULTADO_DOS_CLASES.model_dump(),
            headers=headers(admin),
        )
        assert resp.status_code == 404
