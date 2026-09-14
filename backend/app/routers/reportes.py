import io
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.clase_uml import ClaseUml
from app.models.relacion import Relacion
from app.models.usuario import Usuario
from app.routers.auth import get_current_user
from app.services.acceso import obtener_proyecto_propio
from app.services.generador_reporte import generar_pdf_reporte
from app.services.generador_spring import slug_paquete

router = APIRouter(prefix="/proyectos/{proyecto_id}", tags=["reportes"])


@router.get("/reporte")
def obtener_reporte(
    proyecto_id: int,
    formato: Literal["pdf"] = Query("pdf"),
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """CU07 - Genera un reporte del diagrama de clases del proyecto para
    descargar. A diferencia de CU08/CU09, solo el administrador dueño puede
    generarlo (los colaboradores no tienen acceso), por eso se usa
    `obtener_proyecto_propio` en vez del `obtener_proyecto_con_acceso`
    genérico."""
    proyecto = obtener_proyecto_propio(proyecto_id, usuario_actual, db)
    clases = list(db.scalars(select(ClaseUml).where(ClaseUml.id_proyecto == proyecto_id)))
    if not clases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El proyecto no tiene contenido disponible para exportar. Agrega al menos una clase al diagrama.",
        )
    relaciones = list(db.scalars(select(Relacion).where(Relacion.id_proyecto == proyecto_id)))

    contenido_pdf = generar_pdf_reporte(proyecto, clases, relaciones)
    nombre_archivo = f"{slug_paquete(proyecto.nombre)}-reporte.pdf"

    return StreamingResponse(
        io.BytesIO(contenido_pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )
