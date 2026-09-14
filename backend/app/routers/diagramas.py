from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.usuario import Usuario
from app.routers.auth import get_current_user
from app.schemas.diagrama import DiagramaIO
from app.services.acceso import obtener_proyecto_con_acceso
from app.services.diagrama import cargar_diagrama, guardar_diagrama

router = APIRouter(prefix="/proyectos/{proyecto_id}/diagrama", tags=["diagrama"])


@router.get("", response_model=DiagramaIO)
def obtener_diagrama(
    proyecto_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DiagramaIO:
    """CU09 - Obtiene el diagrama de clases de un proyecto propio o colaborado."""
    obtener_proyecto_con_acceso(proyecto_id, usuario_actual, db)
    return cargar_diagrama(proyecto_id, db)


@router.put("", response_model=DiagramaIO)
def guardar_diagrama_endpoint(
    proyecto_id: int,
    datos: DiagramaIO,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DiagramaIO:
    """CU09 - Reemplaza el diagrama completo del proyecto (autoguardado)."""
    obtener_proyecto_con_acceso(proyecto_id, usuario_actual, db)
    guardar_diagrama(proyecto_id, datos, db)
    return cargar_diagrama(proyecto_id, db)
