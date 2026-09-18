"""CU11 — interpretación de comandos de voz.

Este módulo SOLO interpreta: recibe el texto ya transcrito por el navegador
(Web Speech API), usa la API de OpenAI (function calling / tools) para
determinar cuál de las 5 acciones soportadas corresponde, resuelve los
nombres de clase que citó el modelo contra las clases reales del proyecto
(mismo criterio `casefold()` que ya usa `validar_diagrama`), y devuelve una
`AccionVoz` con los ids ya resueltos. Nunca persiste nada en la base de datos
-- quien aplica la acción es el frontend, llamando a las funciones que ya
existen en `useDiagrama.ts` (`agregarClase`/`actualizarClase`/`eliminarClase`/
`crearRelacion`), que ya disparan el autoguardado HTTP y la sincronización a
Yjs (CU10). Así se evita duplicar validación/persistencia/ids nuevos.

`_llamar_openai` es el único punto que toca la red -- es la función que se
monkeypatchea en los tests (`backend/tests/test_comandos_voz.py`) para no
pegarle nunca a la API real, mismo patrón que ya usa
`test_ws_diagramas.py` (`monkeypatch.setattr(yjs_rooms, "DEBOUNCE_SEGUNDOS", ...)`).
"""

from __future__ import annotations

import json

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.atributo import VisibilidadMiembro
from app.models.relacion import TipoRelacion
from app.schemas.comando_voz import (
    AccionAgregarAtributo,
    AccionCrearClase,
    AccionCrearRelacion,
    AccionEliminarClase,
    AccionRenombrarClase,
    AccionVoz,
    AtributoNuevoIO,
)
from app.schemas.diagrama import ClaseIO, DiagramaIO
from app.services.diagrama import MULTIPLICIDADES_VALIDAS, cargar_diagrama

MENSAJE_NO_SOPORTADO = (
    "No se entendió el comando o la acción no está soportada. Comandos soportados: "
    "crear clase, agregar atributo, eliminar clase, crear relación, renombrar clase."
)


class ComandoVozInvalidoError(Exception):
    """El texto no se pudo mapear a ninguna de las 5 acciones soportadas, los
    argumentos que devolvió el modelo no pasan la validación, o el comando
    referencia/duplica un nombre de clase que no corresponde. El router lo
    traduce a 422 -- nunca se toca el diagrama en este caso."""


class ComandoVozNoDisponibleError(Exception):
    """Timeout, error de red o rate-limit al llamar a OpenAI. El router lo
    traduce a 503 con un mensaje genérico -- nunca se expone el detalle
    crudo del proveedor externo."""


def _construir_tools() -> list[dict]:
    visibilidades = [v.value for v in VisibilidadMiembro]
    tipos_relacion = [t.value for t in TipoRelacion]
    multiplicidades = sorted(MULTIPLICIDADES_VALIDAS)

    propiedades_atributo = {
        "nombre": {"type": "string", "description": "Nombre del atributo."},
        "tipo": {
            "type": ["string", "null"],
            "description": "Tipo de dato del atributo, ej. String, int, boolean. null si no se especificó.",
        },
        "visibilidad": {"type": "string", "enum": visibilidades},
    }

    return [
        {
            "type": "function",
            "function": {
                "name": "crear_clase",
                "description": (
                    "Crea una clase nueva en el diagrama UML, opcionalmente con "
                    "atributos ya especificados en el mismo comando."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nombre_clase": {"type": "string", "description": "Nombre de la clase a crear."},
                        "atributos": {
                            "type": "array",
                            "description": "Atributos mencionados en el mismo comando, si los hay.",
                            "items": {
                                "type": "object",
                                "properties": propiedades_atributo,
                                "required": ["nombre", "tipo", "visibilidad"],
                            },
                        },
                    },
                    "required": ["nombre_clase", "atributos"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "agregar_atributo",
                "description": "Agrega un atributo nuevo a una clase que YA EXISTE en el diagrama.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nombre_clase": {
                            "type": "string",
                            "description": "Nombre de la clase existente a la que se agrega el atributo.",
                        },
                        **propiedades_atributo,
                    },
                    "required": ["nombre_clase", "nombre", "tipo", "visibilidad"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "eliminar_clase",
                "description": "Elimina una clase existente del diagrama (y sus relaciones).",
                "parameters": {
                    "type": "object",
                    "properties": {"nombre_clase": {"type": "string"}},
                    "required": ["nombre_clase"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "crear_relacion",
                "description": "Crea una relación UML entre dos clases existentes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nombre_clase_origen": {"type": "string"},
                        "nombre_clase_destino": {"type": "string"},
                        "tipo_relacion": {"type": "string", "enum": tipos_relacion},
                        "multiplicidad_origen": {"type": ["string", "null"], "enum": [*multiplicidades, None]},
                        "multiplicidad_destino": {"type": ["string", "null"], "enum": [*multiplicidades, None]},
                    },
                    "required": [
                        "nombre_clase_origen",
                        "nombre_clase_destino",
                        "tipo_relacion",
                        "multiplicidad_origen",
                        "multiplicidad_destino",
                    ],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "renombrar_clase",
                "description": "Cambia el nombre de una clase existente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nombre_actual": {"type": "string"},
                        "nombre_nuevo": {"type": "string"},
                    },
                    "required": ["nombre_actual", "nombre_nuevo"],
                },
            },
        },
    ]


def _prompt_sistema(diagrama: DiagramaIO) -> str:
    nombres = ", ".join(f'"{c.nombre}"' for c in diagrama.clases) or "(el diagrama está vacío todavía)"
    visibilidades = ", ".join(v.value for v in VisibilidadMiembro)
    tipos_relacion = ", ".join(t.value for t in TipoRelacion)
    multiplicidades = ", ".join(sorted(MULTIPLICIDADES_VALIDAS))
    return (
        "Sos el intérprete de comandos de voz de un diagramador de clases UML.\n"
        "El usuario habla en español (Bolivia/Latinoamérica) y su comando ya fue "
        "transcrito a texto.\n"
        "Tu única tarea es traducir ese texto a UNA de las funciones disponibles, "
        "con sus parámetros.\n\n"
        f"Clases que existen ACTUALMENTE en este diagrama: {nombres}.\n\n"
        "Reglas estrictas:\n"
        "- Nunca inventes un nombre de clase que el usuario no haya dicho o que no "
        "exista en la lista de arriba cuando la acción lo requiere (agregar atributo, "
        "eliminar clase, crear relación, renombrar).\n"
        f"- Los únicos tipos de relación válidos son: {tipos_relacion}.\n"
        f"- Las únicas multiplicidades válidas son: {multiplicidades}, o ninguna si no "
        "se especificó.\n"
        f"- Las únicas visibilidades válidas son: {visibilidades} (si no se especifica, "
        "usa PRIVADO).\n"
        "- Si el comando no corresponde claramente a ninguna de las acciones "
        "soportadas, o le falta información esencial para ejecutarse (ej. no queda "
        "claro el nombre de la clase), NO llames ninguna función: respondé en una "
        "frase breve en español explicando qué no se entendió.\n"
        "- No pidas confirmación ni hagas preguntas de vuelta: interpretá con la "
        "mejor información disponible o reportá que no se pudo interpretar."
    )


def _llamar_openai(texto: str, prompt_sistema: str) -> tuple[str | None, dict | None]:
    if not settings.OPENAI_API_KEY:
        raise ComandoVozNoDisponibleError("OPENAI_API_KEY no está configurada en el servidor.")

    cliente = OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        respuesta = cliente.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": texto},
            ],
            tools=_construir_tools(),
            tool_choice="auto",
        )
    except (APIConnectionError, APITimeoutError, RateLimitError, APIStatusError) as err:
        raise ComandoVozNoDisponibleError(str(err)) from err

    tool_calls = respuesta.choices[0].message.tool_calls
    if not tool_calls:
        return None, None

    llamada = tool_calls[0]
    try:
        argumentos = json.loads(llamada.function.arguments)
    except json.JSONDecodeError as err:
        raise ComandoVozInvalidoError(
            "El comando no se pudo interpretar completamente. Intenta de nuevo siendo más específico."
        ) from err
    return llamada.function.name, argumentos


def _resolver_clase(nombre: str, clases: list[ClaseIO]) -> ClaseIO:
    objetivo = nombre.strip().casefold()
    for clase in clases:
        if clase.nombre.strip().casefold() == objetivo:
            return clase
    raise ComandoVozInvalidoError(f'No se encontró ninguna clase llamada "{nombre}" en este proyecto.')


def _validar_nombre_disponible(nombre: str, clases: list[ClaseIO]) -> None:
    objetivo = nombre.strip().casefold()
    if any(c.nombre.strip().casefold() == objetivo for c in clases):
        raise ComandoVozInvalidoError(f'Ya existe una clase llamada "{nombre}" en este proyecto.')


def _atributo_desde_argumentos(argumentos: dict) -> AtributoNuevoIO:
    try:
        return AtributoNuevoIO(**argumentos)
    except ValidationError as err:
        raise ComandoVozInvalidoError(
            "El comando no se pudo interpretar completamente. Intenta de nuevo siendo más específico."
        ) from err


def _manejar_crear_clase(argumentos: dict, clases: list[ClaseIO]) -> AccionCrearClase:
    nombre_clase = argumentos.get("nombre_clase")
    if not nombre_clase or not isinstance(nombre_clase, str):
        raise ComandoVozInvalidoError(MENSAJE_NO_SOPORTADO)
    _validar_nombre_disponible(nombre_clase, clases)

    atributos_crudos = argumentos.get("atributos") or []
    try:
        atributos = [AtributoNuevoIO(**a) for a in atributos_crudos]
    except ValidationError as err:
        raise ComandoVozInvalidoError(
            "El comando no se pudo interpretar completamente. Intenta de nuevo siendo más específico."
        ) from err

    resumen = f"Se creó la clase \"{nombre_clase}\""
    resumen += f" con {len(atributos)} atributo{'s' if len(atributos) != 1 else ''}." if atributos else "."
    return AccionCrearClase(nombre_clase=nombre_clase, atributos=atributos, resumen=resumen)


def _manejar_agregar_atributo(argumentos: dict, clases: list[ClaseIO]) -> AccionAgregarAtributo:
    nombre_clase = argumentos.get("nombre_clase")
    if not nombre_clase or not isinstance(nombre_clase, str):
        raise ComandoVozInvalidoError(MENSAJE_NO_SOPORTADO)
    clase = _resolver_clase(nombre_clase, clases)
    atributo = _atributo_desde_argumentos(
        {
            "nombre": argumentos.get("nombre"),
            "tipo": argumentos.get("tipo"),
            "visibilidad": argumentos.get("visibilidad", VisibilidadMiembro.PRIVADO.value),
        }
    )
    resumen = f'Se agregó el atributo "{atributo.nombre}" a la clase "{clase.nombre}".'
    return AccionAgregarAtributo(id_clase=clase.id, nombre_clase=clase.nombre, atributo=atributo, resumen=resumen)


def _manejar_eliminar_clase(argumentos: dict, clases: list[ClaseIO]) -> AccionEliminarClase:
    nombre_clase = argumentos.get("nombre_clase")
    if not nombre_clase or not isinstance(nombre_clase, str):
        raise ComandoVozInvalidoError(MENSAJE_NO_SOPORTADO)
    clase = _resolver_clase(nombre_clase, clases)
    resumen = f'Se eliminó la clase "{clase.nombre}".'
    return AccionEliminarClase(id_clase=clase.id, nombre_clase=clase.nombre, resumen=resumen)


def _manejar_crear_relacion(argumentos: dict, clases: list[ClaseIO]) -> AccionCrearRelacion:
    nombre_origen = argumentos.get("nombre_clase_origen")
    nombre_destino = argumentos.get("nombre_clase_destino")
    tipo_relacion = argumentos.get("tipo_relacion")
    if not nombre_origen or not nombre_destino or tipo_relacion not in {t.value for t in TipoRelacion}:
        raise ComandoVozInvalidoError(MENSAJE_NO_SOPORTADO)

    origen = _resolver_clase(nombre_origen, clases)
    destino = _resolver_clase(nombre_destino, clases)

    for multiplicidad in (argumentos.get("multiplicidad_origen"), argumentos.get("multiplicidad_destino")):
        if multiplicidad is not None and multiplicidad not in MULTIPLICIDADES_VALIDAS:
            raise ComandoVozInvalidoError(MENSAJE_NO_SOPORTADO)

    resumen = f'Se creó una relación de {tipo_relacion.lower()} entre "{origen.nombre}" y "{destino.nombre}".'
    return AccionCrearRelacion(
        id_clase_origen=origen.id,
        id_clase_destino=destino.id,
        nombre_clase_origen=origen.nombre,
        nombre_clase_destino=destino.nombre,
        tipo=TipoRelacion(tipo_relacion),
        multiplicidad_origen=argumentos.get("multiplicidad_origen"),
        multiplicidad_destino=argumentos.get("multiplicidad_destino"),
        resumen=resumen,
    )


def _manejar_renombrar_clase(argumentos: dict, clases: list[ClaseIO]) -> AccionRenombrarClase:
    nombre_actual = argumentos.get("nombre_actual")
    nombre_nuevo = argumentos.get("nombre_nuevo")
    if not nombre_actual or not nombre_nuevo:
        raise ComandoVozInvalidoError(MENSAJE_NO_SOPORTADO)

    clase = _resolver_clase(nombre_actual, clases)
    otras = [c for c in clases if c.id != clase.id]
    _validar_nombre_disponible(nombre_nuevo, otras)

    resumen = f'Se cambió el nombre de "{clase.nombre}" a "{nombre_nuevo}".'
    return AccionRenombrarClase(id_clase=clase.id, nombre_anterior=clase.nombre, nombre_nuevo=nombre_nuevo, resumen=resumen)


_MANEJADORES = {
    "crear_clase": _manejar_crear_clase,
    "agregar_atributo": _manejar_agregar_atributo,
    "eliminar_clase": _manejar_eliminar_clase,
    "crear_relacion": _manejar_crear_relacion,
    "renombrar_clase": _manejar_renombrar_clase,
}


def interpretar_comando(proyecto_id: int, texto: str, db: Session) -> AccionVoz:
    diagrama = cargar_diagrama(proyecto_id, db)
    prompt = _prompt_sistema(diagrama)
    nombre_tool, argumentos = _llamar_openai(texto, prompt)

    manejador = _MANEJADORES.get(nombre_tool) if nombre_tool else None
    if manejador is None:
        raise ComandoVozInvalidoError(MENSAJE_NO_SOPORTADO)

    return manejador(argumentos, diagrama.clases)
