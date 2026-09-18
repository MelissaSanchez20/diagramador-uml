"""Schemas de CU11 (comandos de voz): la "acción estructurada" que
`app/services/comandos_voz.py` devuelve luego de interpretar un comando con
OpenAI function calling. Los ids ya vienen resueltos (nunca nombres crudos) y
nunca se inventa un `id` nuevo acá -- eso lo sigue generando el cliente con
`crypto.randomUUID()`, igual que hoy para cualquier clase/atributo/relación
creada a mano (ver `useDiagrama.ts`)."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from app.models.atributo import VisibilidadMiembro
from app.models.relacion import TipoRelacion


class ComandoVozInput(BaseModel):
    texto: str = Field(min_length=1, max_length=500)


class AtributoNuevoIO(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    tipo: str | None = Field(default=None, max_length=100)
    visibilidad: VisibilidadMiembro = VisibilidadMiembro.PRIVADO


class AccionCrearClase(BaseModel):
    accion: Literal["crear_clase"] = "crear_clase"
    nombre_clase: str
    atributos: list[AtributoNuevoIO] = []
    resumen: str


class AccionAgregarAtributo(BaseModel):
    accion: Literal["agregar_atributo"] = "agregar_atributo"
    id_clase: str
    nombre_clase: str
    atributo: AtributoNuevoIO
    resumen: str


class AccionEliminarClase(BaseModel):
    accion: Literal["eliminar_clase"] = "eliminar_clase"
    id_clase: str
    nombre_clase: str
    resumen: str


class AccionCrearRelacion(BaseModel):
    accion: Literal["crear_relacion"] = "crear_relacion"
    id_clase_origen: str
    id_clase_destino: str
    nombre_clase_origen: str
    nombre_clase_destino: str
    tipo: TipoRelacion
    multiplicidad_origen: str | None = None
    multiplicidad_destino: str | None = None
    resumen: str


class AccionRenombrarClase(BaseModel):
    accion: Literal["renombrar_clase"] = "renombrar_clase"
    id_clase: str
    nombre_anterior: str
    nombre_nuevo: str
    resumen: str


AccionVoz = Annotated[
    Union[
        AccionCrearClase,
        AccionAgregarAtributo,
        AccionEliminarClase,
        AccionCrearRelacion,
        AccionRenombrarClase,
    ],
    Field(discriminator="accion"),
]
