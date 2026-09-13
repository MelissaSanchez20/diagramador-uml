from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hashear_password, verificar_password
from app.db.session import get_db
from app.models.usuario import Usuario
from app.routers.auth import get_current_user
from app.schemas.usuario import UsuarioOut, UsuarioUpdate

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("/me", response_model=UsuarioOut)
def leer_perfil(usuario_actual: Usuario = Depends(get_current_user)) -> Usuario:
    """CU03 - Ver el perfil del usuario autenticado."""
    return usuario_actual


@router.put("/me", response_model=UsuarioOut)
def actualizar_perfil(
    datos: UsuarioUpdate,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Usuario:
    """CU03 - Editar el perfil: nombre, email y (opcionalmente) contraseña."""
    if datos.nombre_completo is not None:
        usuario_actual.nombre_completo = datos.nombre_completo

    if datos.email is not None and datos.email != usuario_actual.email:
        existe = db.scalar(select(Usuario).where(Usuario.email == datos.email))
        if existe is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El email ya está registrado",
            )
        usuario_actual.email = datos.email

    if datos.password_nuevo is not None:
        if not datos.password_actual or not verificar_password(
            datos.password_actual, usuario_actual.password_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña actual es incorrecta",
            )
        usuario_actual.password_hash = hashear_password(datos.password_nuevo)

    db.commit()
    db.refresh(usuario_actual)
    return usuario_actual
