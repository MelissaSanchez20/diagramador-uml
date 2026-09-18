"""CU12 — reconocimiento de diagrama de clases a partir de una fotografía.

Reutiliza la infraestructura de OpenAI ya construida en CU11/CU13
(`OPENAI_API_KEY`/`OPENAI_MODEL` de `app/core/config.py`, la misma
`ComandoVozNoDisponibleError` de `app/services/comandos_voz.py` para
errores de red/API -- mismo significado, no se crea una excepción hermana
solo por prolijidad cosmética) pero con dos diferencias de fondo respecto a
CU11/CU13:

1. No es function calling sobre acciones del editor -- es una extracción
   estructurada de una sola vez (`response_format` con JSON Schema en modo
   `strict`, para forzar una salida parseable en vez de texto libre a
   interpretar con regex) a partir de una imagen (input de visión de
   `gpt-4o-mini`).
2. El resultado NUNCA se aplica solo -- `reconocer_diagrama` es de solo
   lectura (no persiste nada); recién `aplicar_reconocimiento` escribe en la
   base de datos, y solo cuando el usuario confirmó la vista previa en el
   frontend.

`aplicar_reconocimiento` reutiliza `guardar_diagrama` (mismo patrón que el
importador XMI de CU09) pero, a diferencia de XMI, **agrega** al diagrama
existente en vez de exigir que esté vacío: carga el diagrama actual,
construye las clases/relaciones nuevas con ids frescos (`uuid4`, igual que
el resto del proyecto -- nunca se reusan ids externos) y guarda la unión.

Criterio de colisión de nombres (ver `_nombre_disponible`): si una clase
detectada en la foto tiene el mismo nombre (case-insensitive) que una que ya
existe en el proyecto -- o que otra clase de la misma foto -- se le agrega
un sufijo numérico (" 2", " 3", ...) hasta encontrar uno libre, y se deja
una advertencia. Se eligió renombrar en vez de rechazar la clase para no
perder información ya interpretada de la imagen (atributos/relaciones), y en
vez de fusionar con la clase existente porque decidir qué atributos son
"nuevos" de forma automática es ambiguo y arriesgado (podría pisar datos
reales). Las relaciones detectadas solo pueden conectar clases DETECTADAS EN
LA MISMA FOTO (nunca a una clase preexistente del proyecto) -- si el modelo
devuelve una relación que referencia un nombre que no está entre las clases
de esa misma foto, se descarta con advertencia en vez de intentar adivinar a
qué clase preexistente se refería.
"""

from __future__ import annotations

import base64
import json
from uuid import uuid4

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.relacion import TipoRelacion
from app.schemas.diagrama import AtributoIO, ClaseIO, DiagramaIO, MetodoIO, RelacionIO
from app.schemas.reconocimiento_foto import (
    ClaseDetectadaIO,
    ConfirmarReconocimientoResultado,
    ReconocimientoFotoResultado,
)
from app.services.comandos_voz import ComandoVozNoDisponibleError
from app.services.diagrama import MULTIPLICIDADES_VALIDAS, cargar_diagrama, guardar_diagrama

TIPOS_IMAGEN_PERMITIDOS = {"image/jpeg", "image/png", "image/webp"}
TAMANIO_MAXIMO_BYTES = 10 * 1024 * 1024  # 10MB

# Misma grilla que useDiagrama.ts/importador_xmi.py -- las clases nuevas no
# se amontonan todas en el mismo punto, siguen la grilla desde donde queda
# el diagrama actual (no desde 0, a diferencia de XMI que siempre parte de
# un diagrama vacío).
_GRID_COLUMNAS = 4
_GRID_PASO_X = 240
_GRID_PASO_Y = 180


def _posicion_en_grilla(indice: int) -> tuple[float, float]:
    columna = indice % _GRID_COLUMNAS
    fila = indice // _GRID_COLUMNAS
    return 80 + columna * _GRID_PASO_X, 80 + fila * _GRID_PASO_Y


class ImagenInvalidaError(Exception):
    """Archivo de imagen inválido (tipo/tamaño no permitido, vacío) o la
    imagen no contiene ningún diagrama de clases UML reconocible -- el
    router lo traduce a 400. Nunca se inventa una clase genérica para
    "rellenar" cuando no se reconoce nada."""


_PROMPT_SISTEMA = (
    "Sos un intérprete de diagramas de clases UML a partir de imágenes "
    "(fotos de un pizarrón/papel a mano, o capturas de otra herramienta "
    "UML). Tu tarea es devolver una estructura JSON con las clases, "
    "atributos, métodos (si son claramente visibles) y relaciones que "
    "identifiques.\n\n"
    "Reglas estrictas:\n"
    "- Si la imagen no contiene ningún diagrama de clases UML reconocible "
    "(por ejemplo es una foto sin relación con UML, o está demasiado "
    "borrosa/incompleta para identificar ni una sola clase), poné "
    '"reconocido": false, dejá "clases" y "relaciones" vacíos, y explicá '
    'brevemente por qué en "mensaje". NUNCA inventes clases genéricas '
    "(\"Clase1\", \"Entidad\", etc.) para rellenar cuando no hay nada "
    "reconocible.\n"
    "- Si reconocés al menos una clase, poné \"reconocido\": true y un "
    'resumen breve en "mensaje" (ej. "Se detectaron 2 clases y 1 '
    'relación.").\n'
    "- El tipo de una relación debe ser uno de: ASOCIACION, HERENCIA, "
    "AGREGACION, COMPOSICION -- elegí el que mejor corresponda según cómo "
    "se ve dibujada (flecha/rombo/línea simple); si no podés distinguirlo "
    "con confianza, usá ASOCIACION.\n"
    "- La multiplicidad (ej. \"1\", \"0..1\", \"0..*\", \"1..*\") solo si "
    "es legible junto a la relación; si no, dejala en null. No inventes "
    "una multiplicidad que no esté escrita.\n"
    "- Los nombres de clase/atributo/método deben ser tal como aparecen en "
    "la imagen (sin traducir ni normalizar mayúsculas)."
)

_ESQUEMA_ATRIBUTO = {
    "type": "object",
    "properties": {
        "nombre": {"type": "string"},
        "tipo": {"type": ["string", "null"], "description": "Tipo de dato tal como aparece, o null si no se indica."},
    },
    "required": ["nombre", "tipo"],
    "additionalProperties": False,
}

_ESQUEMA_METODO = {
    "type": "object",
    "properties": {
        "nombre": {"type": "string"},
        "tipo_retorno": {"type": ["string", "null"]},
    },
    "required": ["nombre", "tipo_retorno"],
    "additionalProperties": False,
}

_ESQUEMA_RESPUESTA = {
    "type": "object",
    "properties": {
        "reconocido": {
            "type": "boolean",
            "description": "true si la imagen contiene al menos una clase UML identificable.",
        },
        "mensaje": {"type": "string"},
        "clases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "atributos": {"type": "array", "items": _ESQUEMA_ATRIBUTO},
                    "metodos": {"type": "array", "items": _ESQUEMA_METODO},
                },
                "required": ["nombre", "atributos", "metodos"],
                "additionalProperties": False,
            },
        },
        "relaciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clase_origen": {"type": "string"},
                    "clase_destino": {"type": "string"},
                    "tipo": {"type": "string", "enum": [t.value for t in TipoRelacion]},
                    "multiplicidad_origen": {"type": ["string", "null"], "enum": [*sorted(MULTIPLICIDADES_VALIDAS), None]},
                    "multiplicidad_destino": {"type": ["string", "null"], "enum": [*sorted(MULTIPLICIDADES_VALIDAS), None]},
                },
                "required": ["clase_origen", "clase_destino", "tipo", "multiplicidad_origen", "multiplicidad_destino"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reconocido", "mensaje", "clases", "relaciones"],
    "additionalProperties": False,
}

_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {"name": "reconocimiento_diagrama", "schema": _ESQUEMA_RESPUESTA, "strict": True},
}


def _validar_imagen(contenido: bytes, content_type: str | None) -> None:
    if content_type not in TIPOS_IMAGEN_PERMITIDOS:
        raise ImagenInvalidaError(
            f'Formato de imagen no soportado ("{content_type or "desconocido"}"). Usa JPG, PNG o WEBP.'
        )
    if not contenido:
        raise ImagenInvalidaError("El archivo está vacío.")
    if len(contenido) > TAMANIO_MAXIMO_BYTES:
        raise ImagenInvalidaError("La imagen es demasiado grande (máximo 10MB).")


def _llamar_openai_reconocimiento(contenido: bytes, content_type: str) -> ReconocimientoFotoResultado:
    """Único punto que llama al SDK de OpenAI -- se monkeypatchea en los
    tests para no pegarle nunca a la API real, mismo patrón que
    `comandos_voz._llamar_openai`/`agente._llamar_openai_agente`."""
    if not settings.OPENAI_API_KEY:
        raise ComandoVozNoDisponibleError("OPENAI_API_KEY no está configurada en el servidor.")

    data_url = f"data:{content_type};base64,{base64.b64encode(contenido).decode('ascii')}"
    cliente = OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        respuesta = cliente.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _PROMPT_SISTEMA},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Interpretá el diagrama de clases UML de esta imagen."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            response_format=_RESPONSE_FORMAT,
        )
    except (APIConnectionError, APITimeoutError, RateLimitError, APIStatusError) as err:
        raise ComandoVozNoDisponibleError(str(err)) from err

    contenido_json = respuesta.choices[0].message.content
    try:
        return ReconocimientoFotoResultado(**json.loads(contenido_json))
    except (json.JSONDecodeError, ValidationError, TypeError) as err:
        raise ComandoVozNoDisponibleError(f"Respuesta inesperada del modelo de reconocimiento: {err}") from err


def _sin_clases_duplicadas(clases: list[ClaseDetectadaIO]) -> list[ClaseDetectadaIO]:
    """El modelo de visión ocasionalmente repite una clase idéntica dos
    veces en el mismo resultado (mismo nombre y mismos atributos/métodos --
    verificado empíricamente, ver limitaciones documentadas). Un duplicado
    EXACTO nunca es información real (un diagrama no tiene dos clases con el
    mismo nombre y los mismos atributos), así que se colapsa acá antes de
    mostrar la vista previa. Dos clases con el mismo nombre pero atributos
    distintos NO se tocan -- eso sí podría ser una ambigüedad real de la
    imagen, y el usuario la revisa en la vista previa."""
    vistas: set[tuple] = set()
    resultado = []
    for c in clases:
        clave = (
            c.nombre.strip().casefold(),
            tuple((a.nombre.strip().casefold(), a.tipo) for a in c.atributos),
            tuple((m.nombre.strip().casefold(), m.tipo_retorno) for m in c.metodos),
        )
        if clave in vistas:
            continue
        vistas.add(clave)
        resultado.append(c)
    return resultado


def reconocer_diagrama(contenido: bytes, content_type: str | None) -> ReconocimientoFotoResultado:
    """Solo lectura -- nunca persiste nada. Devuelve la vista previa que el
    frontend muestra antes de confirmar."""
    _validar_imagen(contenido, content_type)
    resultado = _llamar_openai_reconocimiento(contenido, content_type)
    resultado.clases = _sin_clases_duplicadas(resultado.clases)

    if not resultado.reconocido or not resultado.clases:
        raise ImagenInvalidaError(
            resultado.mensaje or "No se reconoció ningún diagrama de clases UML en la imagen."
        )
    return resultado


def _nombre_disponible(nombre: str, tomados: set[str]) -> str:
    base = nombre.strip()
    candidato = base
    sufijo = 2
    while candidato.casefold() in tomados:
        candidato = f"{base} {sufijo}"
        sufijo += 1
    return candidato


def aplicar_reconocimiento(proyecto_id: int, resultado: ReconocimientoFotoResultado, db: Session) -> ConfirmarReconocimientoResultado:
    """Persiste las clases/relaciones de `resultado` AGREGÁNDOLAS al
    diagrama actual del proyecto (nunca lo reemplaza ni exige que esté
    vacío, a diferencia de la importación XMI de CU09) reutilizando
    `guardar_diagrama`. Ver criterio de colisión de nombres en el docstring
    del módulo."""
    clases_validas = [c for c in resultado.clases if c.nombre.strip()]
    if not clases_validas:
        raise ImagenInvalidaError("No hay clases para agregar al diagrama.")

    diagrama_actual = cargar_diagrama(proyecto_id, db)
    nombres_tomados = {c.nombre.strip().casefold() for c in diagrama_actual.clases}
    advertencias: list[str] = []

    # Construcción envuelta en un único try/except: si algún campo detectado
    # excede las validaciones de Pydantic (nombre/tipo demasiado largo), se
    # traduce a un 400 claro en vez de dejar escapar un 500 crudo.
    try:
        nuevas_clases: list[ClaseIO] = []
        mapa_nombre_a_id: dict[str, str] = {}
        indice_base = len(diagrama_actual.clases)

        for i, c in enumerate(clases_validas):
            nombre_final = _nombre_disponible(c.nombre, nombres_tomados)
            if nombre_final.casefold() != c.nombre.strip().casefold():
                advertencias.append(
                    f'Se renombró "{c.nombre}" a "{nombre_final}" porque ya existía una clase con ese nombre.'
                )
            nombres_tomados.add(nombre_final.casefold())

            nueva_id = str(uuid4())
            mapa_nombre_a_id[c.nombre] = nueva_id
            pos_x, pos_y = _posicion_en_grilla(indice_base + i)
            nuevas_clases.append(
                ClaseIO(
                    id=nueva_id,
                    nombre=nombre_final,
                    pos_x=pos_x,
                    pos_y=pos_y,
                    atributos=[
                        AtributoIO(id=str(uuid4()), nombre=a.nombre, tipo=a.tipo, orden=idx)
                        for idx, a in enumerate(c.atributos)
                        if a.nombre.strip()
                    ],
                    metodos=[
                        MetodoIO(id=str(uuid4()), nombre=m.nombre, tipo_retorno=m.tipo_retorno, orden=idx)
                        for idx, m in enumerate(c.metodos)
                        if m.nombre.strip()
                    ],
                )
            )

        nuevas_relaciones: list[RelacionIO] = []
        for r in resultado.relaciones:
            origen_id = mapa_nombre_a_id.get(r.clase_origen)
            destino_id = mapa_nombre_a_id.get(r.clase_destino)
            if origen_id is None or destino_id is None:
                advertencias.append(
                    f'Se descartó una relación porque no se pudo identificar "{r.clase_origen}" o '
                    f'"{r.clase_destino}" entre las clases detectadas en la imagen.'
                )
                continue

            mult_origen = r.multiplicidad_origen if r.multiplicidad_origen in MULTIPLICIDADES_VALIDAS else None
            if r.multiplicidad_origen and mult_origen is None:
                advertencias.append(f'Multiplicidad "{r.multiplicidad_origen}" no reconocida, se omitió.')
            mult_destino = r.multiplicidad_destino if r.multiplicidad_destino in MULTIPLICIDADES_VALIDAS else None
            if r.multiplicidad_destino and mult_destino is None:
                advertencias.append(f'Multiplicidad "{r.multiplicidad_destino}" no reconocida, se omitió.')

            nuevas_relaciones.append(
                RelacionIO(
                    id=str(uuid4()),
                    id_clase_origen=origen_id,
                    id_clase_destino=destino_id,
                    tipo=r.tipo,
                    multiplicidad_origen=mult_origen,
                    multiplicidad_destino=mult_destino,
                )
            )

        diagrama_final = DiagramaIO(
            clases=diagrama_actual.clases + nuevas_clases,
            relaciones=diagrama_actual.relaciones + nuevas_relaciones,
        )
    except ValidationError as err:
        raise ImagenInvalidaError(
            "Algunos datos detectados en la imagen no son válidos para el diagrama (nombre o tipo demasiado largo)."
        ) from err

    guardar_diagrama(proyecto_id, diagrama_final, db)
    return ConfirmarReconocimientoResultado(diagrama=cargar_diagrama(proyecto_id, db), advertencias=advertencias)
