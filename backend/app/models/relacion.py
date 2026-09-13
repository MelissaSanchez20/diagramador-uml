import enum

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class TipoRelacion(str, enum.Enum):
    ASOCIACION = "ASOCIACION"
    HERENCIA = "HERENCIA"
    AGREGACION = "AGREGACION"
    COMPOSICION = "COMPOSICION"


class Relacion(Base):
    __tablename__ = "relaciones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_proyecto: Mapped[int] = mapped_column(
        ForeignKey("proyectos.id", ondelete="CASCADE"), nullable=False
    )
    id_clase_origen: Mapped[str] = mapped_column(
        ForeignKey("clases_uml.id", ondelete="CASCADE"), nullable=False
    )
    id_clase_destino: Mapped[str] = mapped_column(
        ForeignKey("clases_uml.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[TipoRelacion] = mapped_column(Enum(TipoRelacion), nullable=False)
    etiqueta: Mapped[str | None] = mapped_column(String(100), nullable=True)
    multiplicidad_origen: Mapped[str | None] = mapped_column(String(20), nullable=True)
    multiplicidad_destino: Mapped[str | None] = mapped_column(String(20), nullable=True)
    handle_origen: Mapped[str | None] = mapped_column(String(10), nullable=True)
    handle_destino: Mapped[str | None] = mapped_column(String(10), nullable=True)

    origen = relationship("ClaseUml", foreign_keys=[id_clase_origen])
    destino = relationship("ClaseUml", foreign_keys=[id_clase_destino])
