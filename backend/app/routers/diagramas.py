from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.atributo import Atributo
from app.models.clase_uml import ClaseUml
from app.models.metodo import Metodo
from app.models.proyecto import Proyecto
from app.models.proyecto_colaborador import ProyectoColaborador
from app.models.relacion import Relacion
from app.models.usuario import Usuario
from app.routers.auth import get_current_user
from app.schemas.diagrama import DiagramaIO

router = APIRouter(prefix="/proyectos/{proyecto_id}/diagrama", tags=["diagrama"])

# Deben coincidir con OPCIONES_MULTIPLICIDAD en el frontend (umlFormat.ts).
MULTIPLICIDADES_VALIDAS = {"1", "0..1", "0..*", "1..*"}


def _obtener_proyecto_con_acceso(proyecto_id: int, usuario: Usuario, db: Session) -> Proyecto:
    """Como _obtener_proyecto_propio (proyectos.py) pero admite también colaborador activo."""
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado",
        )
    if proyecto.id_administrador == usuario.id:
        return proyecto

    es_colaborador = db.scalar(
        select(ProyectoColaborador).where(
            ProyectoColaborador.id_proyecto == proyecto_id,
            ProyectoColaborador.id_usuario == usuario.id,
            ProyectoColaborador.activo.is_(True),
        )
    )
    if es_colaborador is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a este proyecto",
        )
    return proyecto


@router.get("", response_model=DiagramaIO)
def obtener_diagrama(
    proyecto_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DiagramaIO:
    """CU09 - Obtiene el diagrama de clases de un proyecto propio o colaborado."""
    _obtener_proyecto_con_acceso(proyecto_id, usuario_actual, db)
    clases = list(db.scalars(select(ClaseUml).where(ClaseUml.id_proyecto == proyecto_id)))
    relaciones = list(db.scalars(select(Relacion).where(Relacion.id_proyecto == proyecto_id)))
    return DiagramaIO(clases=clases, relaciones=relaciones)


def _validar_diagrama(datos: DiagramaIO) -> None:
    """Nombres de clase únicos (sin distinguir mayúsculas) y relaciones que
    solo referencien clases del propio payload — evita que una relación
    quede apuntando a una clase de otro proyecto."""
    nombres = [c.nombre.strip().casefold() for c in datos.clases]
    if len(nombres) != len(set(nombres)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hay clases con el mismo nombre en el diagrama",
        )

    ids_clases = {c.id for c in datos.clases}
    for r in datos.relaciones:
        if r.id_clase_origen not in ids_clases or r.id_clase_destino not in ids_clases:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Una relación referencia una clase que no está en el diagrama",
            )
        for multiplicidad in (r.multiplicidad_origen, r.multiplicidad_destino):
            if multiplicidad is not None and multiplicidad not in MULTIPLICIDADES_VALIDAS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Multiplicidad inválida: '{multiplicidad}'. "
                        f"Debe ser una de {sorted(MULTIPLICIDADES_VALIDAS)} o no especificarse."
                    ),
                )


@router.put("", response_model=DiagramaIO)
def guardar_diagrama(
    proyecto_id: int,
    datos: DiagramaIO,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DiagramaIO:
    """CU09 - Reemplaza el diagrama completo del proyecto (autoguardado)."""
    _obtener_proyecto_con_acceso(proyecto_id, usuario_actual, db)
    _validar_diagrama(datos)

    # Reemplazo completo: se borra todo lo existente y se reinserta lo recibido.
    # Los borrados son en bloque (no session.delete uno a uno), por lo que no
    # disparan el cascade de SQLAlchemy: los ondelete="CASCADE" a nivel de BD
    # son los que limpian atributos/métodos/relaciones huérfanos.
    db.execute(delete(Relacion).where(Relacion.id_proyecto == proyecto_id))
    db.execute(delete(ClaseUml).where(ClaseUml.id_proyecto == proyecto_id))

    for c in datos.clases:
        clase = ClaseUml(
            id=c.id,
            id_proyecto=proyecto_id,
            nombre=c.nombre,
            estereotipo=c.estereotipo,
            es_abstracta=c.es_abstracta,
            pos_x=c.pos_x,
            pos_y=c.pos_y,
        )
        clase.atributos = [Atributo(**a.model_dump()) for a in c.atributos]
        clase.metodos = [Metodo(**m.model_dump()) for m in c.metodos]
        db.add(clase)
    db.flush()  # las clases deben existir antes de insertar relaciones que las referencian

    for r in datos.relaciones:
        db.add(Relacion(id_proyecto=proyecto_id, **r.model_dump()))

    db.commit()
    return obtener_diagrama(proyecto_id, usuario_actual, db)
