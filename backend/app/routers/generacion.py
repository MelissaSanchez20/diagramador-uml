import io

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.clase_uml import ClaseUml
from app.models.relacion import Relacion
from app.models.usuario import Usuario
from app.routers.auth import get_current_user
from app.services.acceso import obtener_proyecto_con_acceso
from app.services.generador_spring import generar_zip_backend, slug_paquete

router = APIRouter(prefix="/proyectos/{proyecto_id}", tags=["generacion"])


@router.post("/generar-backend")
def generar_backend(
    proyecto_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """CU08 - Genera un proyecto Maven de Spring Boot (entidades JPA,
    repositories, services y controllers REST) a partir del diagrama de
    clases guardado del proyecto, y lo devuelve como .zip descargable."""
    proyecto = obtener_proyecto_con_acceso(proyecto_id, usuario_actual, db)
    clases = list(db.scalars(select(ClaseUml).where(ClaseUml.id_proyecto == proyecto_id)))
    if not clases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El proyecto no tiene clases en el diagrama todavía. Agrega al menos una antes de generar el backend.",
        )
    relaciones = list(db.scalars(select(Relacion).where(Relacion.id_proyecto == proyecto_id)))

    contenido_zip = generar_zip_backend(proyecto, clases, relaciones)
    nombre_archivo = f"{slug_paquete(proyecto.nombre)}-backend.zip"

    return StreamingResponse(
        io.BytesIO(contenido_zip),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )
