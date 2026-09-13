import { useCallback, useEffect, useRef, useState } from 'react'
import { useEdgesState, useNodesState } from 'reactflow'
import type { Connection, Edge, EdgeChange, Node, NodeChange } from 'reactflow'

import { getDiagrama, guardarDiagrama } from '../../api/diagrama'
import { getApiErrorMessage } from '../../api/errors'
import type { ClaseUml, DiagramaData, RelacionUml, TipoRelacion } from '../../api/types'
import type { ClassNodeData } from './ClassNode'
import { markerDeRelacion } from './umlFormat'

export type EdgeData = {
  tipo: TipoRelacion
  etiqueta: string | null
  multiplicidad_origen: string | null
  multiplicidad_destino: string | null
}

export type DetallesRelacion = {
  tipo: TipoRelacion
  etiqueta: string | null
  multiplicidad_origen: string | null
  multiplicidad_destino: string | null
}

const EDGE_STYLE = { stroke: 'var(--border-strong)' }
const DEBOUNCE_MS = 800

function nuevoId(): string {
  return crypto.randomUUID()
}

// Grilla (no diagonal): con el viejo offset de 60px, una clase de ~176px de
// ancho quedaba tapando casi por completo a la siguiente — imposible de
// distinguir o arrastrar por separado. 240x180 deja aire incluso entre
// clases con varios atributos/métodos.
const GRID_COLUMNAS = 4
const GRID_PASO_X = 240
const GRID_PASO_Y = 180

/** Clase en blanco para "Nueva clase" — posición en grilla según cuántas ya hay. */
export function nuevaClaseVacia(cantidadActual: number): ClaseUml {
  const columna = cantidadActual % GRID_COLUMNAS
  const fila = Math.floor(cantidadActual / GRID_COLUMNAS)
  return {
    id: nuevoId(),
    nombre: '',
    estereotipo: null,
    es_abstracta: false,
    pos_x: 80 + columna * GRID_PASO_X,
    pos_y: 80 + fila * GRID_PASO_Y,
    atributos: [],
    metodos: [],
  }
}

function construirNodos(
  clases: ClaseUml[],
  onCambiar: (clase: ClaseUml) => void,
): Node<ClassNodeData>[] {
  return clases.map((clase) => ({
    id: clase.id,
    type: 'classNode',
    position: { x: clase.pos_x, y: clase.pos_y },
    data: { clase, onCambiar },
  }))
}

function construirAristas(relaciones: RelacionUml[]): Edge<EdgeData>[] {
  return relaciones.map((r) => ({
    id: r.id,
    source: r.id_clase_origen,
    target: r.id_clase_destino,
    sourceHandle: r.handle_origen ?? undefined,
    targetHandle: r.handle_destino ?? undefined,
    type: 'relacion',
    label: r.etiqueta ?? undefined,
    style: EDGE_STYLE,
    data: {
      tipo: r.tipo,
      etiqueta: r.etiqueta,
      multiplicidad_origen: r.multiplicidad_origen,
      multiplicidad_destino: r.multiplicidad_destino,
    },
    ...markerDeRelacion(r.tipo),
  }))
}

function serializar(nodes: Node<ClassNodeData>[], edges: Edge<EdgeData>[]): DiagramaData {
  // Las clases sin nombre (recién creadas, el usuario todavía está
  // escribiéndolo) y las filas de atributo/método sin nombre son solo
  // renglones "en blanco" — el backend exige nombre no vacío en todos los
  // casos, así que se excluyen del guardado hasta que se confirmen con un
  // nombre real. Las relaciones que quedarían apuntando a una clase excluida
  // también se descartan para no romper la integridad del payload.
  const idsClasesValidas = new Set(
    nodes.filter((n) => n.data.clase.nombre.trim()).map((n) => n.id),
  )
  return {
    clases: nodes
      .filter((n) => idsClasesValidas.has(n.id))
      .map((n) => ({
        ...n.data.clase,
        pos_x: n.position.x,
        pos_y: n.position.y,
        atributos: n.data.clase.atributos.filter((a) => a.nombre.trim()),
        metodos: n.data.clase.metodos.filter((m) => m.nombre.trim()),
      })),
    relaciones: edges
      .filter((e) => idsClasesValidas.has(e.source) && idsClasesValidas.has(e.target))
      .map((e) => ({
        id: e.id,
        id_clase_origen: e.source,
        id_clase_destino: e.target,
        tipo: e.data?.tipo ?? 'ASOCIACION',
        etiqueta: e.data?.etiqueta ?? null,
        multiplicidad_origen: e.data?.multiplicidad_origen ?? null,
        multiplicidad_destino: e.data?.multiplicidad_destino ?? null,
        handle_origen: e.sourceHandle ?? null,
        handle_destino: e.targetHandle ?? null,
      })),
  }
}

export function useDiagrama(proyectoId: number) {
  const [nodes, setNodes, onNodesChangeBase] = useNodesState<ClassNodeData>([])
  const [edges, setEdges, onEdgesChangeBase] = useEdgesState<EdgeData>([])
  const [estado, setEstado] = useState<'cargando' | 'listo' | 'error'>('cargando')
  const [error, setError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [errorGuardado, setErrorGuardado] = useState<string | null>(null)
  const cargadoRef = useRef(false)

  // Espejo siempre-actualizado de nodes/edges, para que el guardado diferido
  // (setTimeout) lea el estado más reciente sin importar cuándo se programó.
  const nodesRef = useRef(nodes)
  const edgesRef = useRef(edges)
  useEffect(() => {
    nodesRef.current = nodes
  }, [nodes])
  useEffect(() => {
    edgesRef.current = edges
  }, [edges])

  // Guardado explícito con debounce, disparado solo desde puntos concretos
  // (crear/editar/eliminar clase o relación, soltar un arrastre, borrar con
  // teclado) — NO en cada tick de posición mientras se arrastra una clase.
  const guardarTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hayPendienteRef = useRef(false)

  const ejecutarGuardado = useCallback(() => {
    hayPendienteRef.current = false
    setGuardando(true)
    guardarDiagrama(proyectoId, serializar(nodesRef.current, edgesRef.current))
      .then(() => setErrorGuardado(null))
      .catch((err) => {
        // El usuario sigue editando localmente; el error queda visible en la
        // toolbar con opción de reintentar (no se pierde el cambio, solo no
        // está confirmado en el servidor todavía).
        setErrorGuardado(getApiErrorMessage(err, 'No se pudo guardar el diagrama'))
      })
      .finally(() => setGuardando(false))
  }, [proyectoId])

  const guardarAhora = useCallback(() => {
    if (!cargadoRef.current) return
    hayPendienteRef.current = true
    if (guardarTimeoutRef.current) clearTimeout(guardarTimeoutRef.current)
    guardarTimeoutRef.current = setTimeout(ejecutarGuardado, DEBOUNCE_MS)
  }, [ejecutarGuardado])

  // Reintento manual (botón en la toolbar): salta el debounce y guarda ya.
  const reintentarGuardado = useCallback(() => {
    if (guardarTimeoutRef.current) clearTimeout(guardarTimeoutRef.current)
    ejecutarGuardado()
  }, [ejecutarGuardado])

  // Si el componente se desmonta (ej. el usuario navega a "← Proyectos") con
  // un guardado pendiente dentro de la ventana de debounce, se dispara de
  // inmediato en vez de perderse — cubre el caso de editar y salir rápido.
  useEffect(
    () => () => {
      if (guardarTimeoutRef.current) clearTimeout(guardarTimeoutRef.current)
      if (hayPendienteRef.current) ejecutarGuardado()
    },
    [ejecutarGuardado],
  )

  // Envuelve los change-handlers de React Flow: aplican el cambio como
  // siempre (selección, arrastre en vivo, dimensiones), pero solo disparan
  // guardado cuando el cambio es una eliminación (ej. tecla Delete/Backspace
  // sobre un nodo o arista seleccionada).
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      onNodesChangeBase(changes)
      if (changes.some((c) => c.type === 'remove')) guardarAhora()
    },
    [onNodesChangeBase, guardarAhora],
  )

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      onEdgesChangeBase(changes)
      if (changes.some((c) => c.type === 'remove')) guardarAhora()
    },
    [onEdgesChangeBase, guardarAhora],
  )

  // Se dispara al soltar el arrastre de una clase: una sola vez por
  // movimiento, con la posición final ya aplicada por onNodesChange.
  const onNodeDragStop = useCallback(() => {
    guardarAhora()
  }, [guardarAhora])

  const actualizarClase = useCallback(
    (clase: ClaseUml) => {
      setNodes((nds) => nds.map((n) => (n.id === clase.id ? { ...n, data: { ...n.data, clase } } : n)))
      guardarAhora()
    },
    [setNodes, guardarAhora],
  )

  useEffect(() => {
    let alive = true
    cargadoRef.current = false
    setEstado('cargando')
    getDiagrama(proyectoId)
      .then((datos) => {
        if (!alive) return
        setNodes(construirNodos(datos.clases, actualizarClase))
        setEdges(construirAristas(datos.relaciones))
        setEstado('listo')
        cargadoRef.current = true
      })
      .catch((err) => {
        if (!alive) return
        setError(getApiErrorMessage(err, 'No se pudo cargar el diagrama'))
        setEstado('error')
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [proyectoId])

  const eliminarClase = useCallback(
    (id: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== id))
      setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id))
      guardarAhora()
    },
    [setNodes, setEdges, guardarAhora],
  )

  const agregarClase = useCallback(
    (clase: ClaseUml) => {
      setNodes((nds) => [
        ...nds.map((n) => ({ ...n, selected: false })),
        {
          id: clase.id,
          type: 'classNode',
          selected: true,
          position: { x: clase.pos_x, y: clase.pos_y },
          data: { clase, onCambiar: actualizarClase, autoEditarNombre: true },
        },
      ])
      guardarAhora()
    },
    [setNodes, guardarAhora, actualizarClase],
  )

  const seleccionarClase = useCallback(
    (id: string) => {
      setNodes((nds) => nds.map((n) => ({ ...n, selected: n.id === id })))
    },
    [setNodes],
  )

  const crearRelacion = useCallback(
    (conexion: Connection, detalles: DetallesRelacion) => {
      if (!conexion.source || !conexion.target) return
      const id = nuevoId()
      setEdges((eds) => [
        ...eds,
        {
          id,
          source: conexion.source!,
          target: conexion.target!,
          sourceHandle: conexion.sourceHandle ?? undefined,
          targetHandle: conexion.targetHandle ?? undefined,
          type: 'relacion',
          label: detalles.etiqueta ?? undefined,
          style: EDGE_STYLE,
          data: detalles,
          ...markerDeRelacion(detalles.tipo),
        },
      ])
      guardarAhora()
    },
    [setEdges, guardarAhora],
  )

  const actualizarRelacion = useCallback(
    (id: string, detalles: DetallesRelacion) => {
      setEdges((eds) =>
        eds.map((e) =>
          e.id === id
            ? { ...e, label: detalles.etiqueta ?? undefined, data: detalles, ...markerDeRelacion(detalles.tipo) }
            : e,
        ),
      )
      guardarAhora()
    },
    [setEdges, guardarAhora],
  )

  const eliminarRelacion = useCallback(
    (id: string) => {
      setEdges((eds) => eds.filter((e) => e.id !== id))
      guardarAhora()
    },
    [setEdges, guardarAhora],
  )

  return {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onNodeDragStop,
    estado,
    error,
    guardando,
    errorGuardado,
    reintentarGuardado,
    agregarClase,
    actualizarClase,
    seleccionarClase,
    eliminarClase,
    crearRelacion,
    actualizarRelacion,
    eliminarRelacion,
  }
}
