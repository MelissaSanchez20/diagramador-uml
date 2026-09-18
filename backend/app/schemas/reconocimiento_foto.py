"""Schemas de CU12 (reconocimiento de diagrama por fotografía).

`ReconocimientoFotoResultado` es la "vista previa" que devuelve el endpoint
de reconocimiento (POST .../reconocimiento-foto) y también el body que
recibe el endpoint de confirmación (POST .../reconocimiento-foto/confirmar)
-- el usuario puede revisar/editar ese JSON en el frontend antes de
confirmarlo, mismo criterio que ya usa CU13 con `AccionVoz`."""

from pydantic import BaseModel, Field

from app.models.relacion import TipoRelacion
from app.schemas.diagrama import DiagramaIO


class AtributoDetectadoIO(BaseModel):
    nombre: str
    tipo: str | None = None


class MetodoDetectadoIO(BaseModel):
    nombre: str
    tipo_retorno: str | None = None


class ClaseDetectadaIO(BaseModel):
    nombre: str
    atributos: list[AtributoDetectadoIO] = []
    metodos: list[MetodoDetectadoIO] = []


class RelacionDetectadaIO(BaseModel):
    clase_origen: str
    clase_destino: str
    tipo: TipoRelacion
    multiplicidad_origen: str | None = None
    multiplicidad_destino: str | None = None


class ReconocimientoFotoResultado(BaseModel):
    reconocido: bool
    mensaje: str
    clases: list[ClaseDetectadaIO] = Field(default_factory=list)
    relaciones: list[RelacionDetectadaIO] = Field(default_factory=list)


class ConfirmarReconocimientoResultado(BaseModel):
    """Mismo shape que `ImportacionXmiResultado` (CU09) a propósito -- el
    frontend reusa el mismo manejo (`diagrama.importarDiagrama`)."""

    diagrama: DiagramaIO
    advertencias: list[str] = []
