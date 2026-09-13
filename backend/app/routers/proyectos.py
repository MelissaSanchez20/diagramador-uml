from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.proyecto import Proyecto
from app.models.proyecto_colaborador import ProyectoColaborador
from app.models.usuario import RolUsuario, Usuario
from app.routers.auth import get_current_user
from app.schemas.colaborador import ColaboradorAsignar, ColaboradorOut
from app.schemas.proyecto import ProyectoCreate, ProyectoOut, ProyectoUpdate

router = APIRouter(prefix="/proyectos", tags=["proyectos"])


def _obtener_proyecto_propio(proyecto_id: int, usuario: Usuario, db: Session) -> Proyecto:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado",
        )
    if proyecto.id_administrador != usuario.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No eres el administrador de este proyecto",
        )
    return proyecto


def _nombre_duplicado(
    nombre: str, id_administrador: int, db: Session, excluir_id: int | None = None
) -> bool:
    consulta = select(Proyecto).where(
        Proyecto.id_administrador == id_administrador,
        Proyecto.nombre == nombre,
    )
    if excluir_id is not None:
        consulta = consulta.where(Proyecto.id != excluir_id)
    return db.scalar(consulta) is not None


@router.get("", response_model=list[ProyectoOut])
def listar_proyectos(
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Proyecto]:
    """CU04 - Lista los proyectos propios y aquellos donde el usuario colabora."""
    propios = list(
        db.scalars(select(Proyecto).where(Proyecto.id_administrador == usuario_actual.id))
    )
    for proyecto in propios:
        proyecto.rol_en_proyecto = RolUsuario.ADMINISTRADOR

    colaborados = list(
        db.scalars(
            select(Proyecto)
            .join(ProyectoColaborador, ProyectoColaborador.id_proyecto == Proyecto.id)
            .where(
                ProyectoColaborador.id_usuario == usuario_actual.id,
                ProyectoColaborador.activo.is_(True),
            )
        )
    )
    for proyecto in colaborados:
        proyecto.rol_en_proyecto = RolUsuario.COLABORADOR

    return sorted(propios + colaborados, key=lambda p: p.fecha_creacion, reverse=True)


@router.post("", response_model=ProyectoOut, status_code=status.HTTP_201_CREATED)
def crear_proyecto(
    datos: ProyectoCreate,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Proyecto:
    """CU04 - Crea un proyecto. El nombre debe ser único por administrador."""
    if _nombre_duplicado(datos.nombre, usuario_actual.id, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya tienes un proyecto con ese nombre",
        )
    proyecto = Proyecto(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        id_administrador=usuario_actual.id,
    )
    db.add(proyecto)
    db.commit()
    db.refresh(proyecto)
    proyecto.rol_en_proyecto = RolUsuario.ADMINISTRADOR
    return proyecto


@router.put("/{proyecto_id}", response_model=ProyectoOut)
def actualizar_proyecto(
    proyecto_id: int,
    datos: ProyectoUpdate,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Proyecto:
    """CU04 - Edita un proyecto propio."""
    proyecto = _obtener_proyecto_propio(proyecto_id, usuario_actual, db)

    if datos.nombre is not None and datos.nombre != proyecto.nombre:
        if _nombre_duplicado(datos.nombre, usuario_actual.id, db, excluir_id=proyecto.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya tienes un proyecto con ese nombre",
            )
        proyecto.nombre = datos.nombre

    if datos.descripcion is not None:
        proyecto.descripcion = datos.descripcion

    db.commit()
    db.refresh(proyecto)
    proyecto.rol_en_proyecto = RolUsuario.ADMINISTRADOR
    return proyecto


@router.delete("/{proyecto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_proyecto(
    proyecto_id: int,
    confirmar: bool = False,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """CU04 - Elimina un proyecto propio.

    Si tiene colaboradores activos, exige `?confirmar=true`; si no, responde 409.
    """
    proyecto = _obtener_proyecto_propio(proyecto_id, usuario_actual, db)

    colaboradores_activos = db.scalar(
        select(func.count())
        .select_from(ProyectoColaborador)
        .where(
            ProyectoColaborador.id_proyecto == proyecto.id,
            ProyectoColaborador.activo.is_(True),
        )
    )
    if colaboradores_activos and not confirmar:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"El proyecto tiene {colaboradores_activos} colaborador(es) activo(s). "
                "Repite la petición con ?confirmar=true para eliminarlo de todos modos."
            ),
        )

    db.delete(proyecto)
    db.commit()


@router.post(
    "/{proyecto_id}/colaboradores",
    response_model=ColaboradorOut,
    status_code=status.HTTP_201_CREATED,
)
def agregar_colaborador(
    proyecto_id: int,
    datos: ColaboradorAsignar,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProyectoColaborador:
    """CU04 - Agrega un colaborador al proyecto por email de un usuario existente."""
    proyecto = _obtener_proyecto_propio(proyecto_id, usuario_actual, db)

    usuario_colaborador = db.scalar(select(Usuario).where(Usuario.email == datos.email))
    if usuario_colaborador is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe un usuario registrado con ese email",
        )

    if usuario_colaborador.id == usuario_actual.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes agregarte a ti mismo como colaborador de tu propio proyecto",
        )

    colaborador = db.scalar(
        select(ProyectoColaborador).where(
            ProyectoColaborador.id_proyecto == proyecto.id,
            ProyectoColaborador.id_usuario == usuario_colaborador.id,
        )
    )
    if colaborador is not None:
        if colaborador.activo:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ese usuario ya es colaborador del proyecto",
            )
        colaborador.activo = True
        colaborador.fecha_asignacion = func.now()
    else:
        colaborador = ProyectoColaborador(
            id_proyecto=proyecto.id,
            id_usuario=usuario_colaborador.id,
            activo=True,
        )
        db.add(colaborador)

    db.commit()
    db.refresh(colaborador)
    return colaborador


@router.get("/{proyecto_id}/colaboradores", response_model=list[ColaboradorOut])
def listar_colaboradores(
    proyecto_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProyectoColaborador]:
    """CU04 - Lista los colaboradores activos de un proyecto propio."""
    proyecto = _obtener_proyecto_propio(proyecto_id, usuario_actual, db)
    return list(
        db.scalars(
            select(ProyectoColaborador).where(
                ProyectoColaborador.id_proyecto == proyecto.id,
                ProyectoColaborador.activo.is_(True),
            )
        )
    )


@router.delete(
    "/{proyecto_id}/colaboradores/{colaborador_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def quitar_colaborador(
    proyecto_id: int,
    colaborador_id: int,
    usuario_actual: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """CU04 - Quita (soft delete) un colaborador de un proyecto propio."""
    proyecto = _obtener_proyecto_propio(proyecto_id, usuario_actual, db)

    colaborador = db.scalar(
        select(ProyectoColaborador).where(
            ProyectoColaborador.id == colaborador_id,
            ProyectoColaborador.id_proyecto == proyecto.id,
        )
    )
    if colaborador is None or not colaborador.activo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Colaborador no encontrado en este proyecto",
        )

    colaborador.activo = False
    db.commit()
