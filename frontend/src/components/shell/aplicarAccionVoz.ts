import type { AccionVoz, AtributoUml } from '../../api/types'
import type { useDiagrama } from './useDiagrama'
import { nuevaClaseVacia } from './useDiagrama'

type Diagrama = ReturnType<typeof useDiagrama>

/**
 * Traduce una `AccionVoz` (ids ya resueltos por el backend, ver CU11) a
 * llamadas concretas sobre `useDiagrama` -- extraído del switch que antes
 * vivía inline en `useComandoVoz.ts` (CU11) para que CU13 (agente
 * conversacional) lo reutilice tal cual, sin duplicar los 5 casos.
 */
export function aplicarAccionVoz(accion: AccionVoz, diagrama: Diagrama): void {
  switch (accion.accion) {
    case 'crear_clase': {
      const clase = nuevaClaseVacia(diagrama.nodes.length)
      clase.nombre = accion.nombre_clase
      clase.atributos = accion.atributos.map((a) => ({
        id: crypto.randomUUID(),
        nombre: a.nombre,
        tipo: a.tipo,
        visibilidad: a.visibilidad,
        orden: 0,
      }))
      diagrama.agregarClase(clase)
      break
    }
    case 'agregar_atributo': {
      const nodo = diagrama.nodes.find((n) => n.id === accion.id_clase)
      if (nodo) {
        const nuevoAtributo: AtributoUml = {
          id: crypto.randomUUID(),
          nombre: accion.atributo.nombre,
          tipo: accion.atributo.tipo,
          visibilidad: accion.atributo.visibilidad,
          orden: nodo.data.clase.atributos.length,
        }
        diagrama.actualizarClase({ ...nodo.data.clase, atributos: [...nodo.data.clase.atributos, nuevoAtributo] })
      }
      break
    }
    case 'eliminar_clase': {
      diagrama.eliminarClase(accion.id_clase)
      break
    }
    case 'crear_relacion': {
      diagrama.crearRelacion(
        {
          source: accion.id_clase_origen,
          target: accion.id_clase_destino,
          sourceHandle: null,
          targetHandle: null,
        },
        {
          tipo: accion.tipo,
          etiqueta: null,
          multiplicidad_origen: accion.multiplicidad_origen,
          multiplicidad_destino: accion.multiplicidad_destino,
          forma: null,
        },
      )
      break
    }
    case 'renombrar_clase': {
      const nodo = diagrama.nodes.find((n) => n.id === accion.id_clase)
      if (nodo) diagrama.actualizarClase({ ...nodo.data.clase, nombre: accion.nombre_nuevo })
      break
    }
  }
}
