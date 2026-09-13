from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.usuario import UsuarioOut


class ColaboradorAsignar(BaseModel):
    email: EmailStr


class ColaboradorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_proyecto: int
    id_usuario: int
    fecha_asignacion: datetime
    activo: bool
    usuario: UsuarioOut
