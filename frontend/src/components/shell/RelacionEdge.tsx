import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath } from 'reactflow'
import type { EdgeProps } from 'reactflow'

import type { EdgeData } from './useDiagrama'

/** Punto sobre la recta source→target a `distancia` px del extremo (x1,y1),
 * sin pasar del 40% del camino (para que en aristas muy cortas la etiqueta
 * de multiplicidad no termine encima de la del otro extremo). */
function puntoCercaDe(x1: number, y1: number, x2: number, y2: number, distancia: number) {
  const dx = x2 - x1
  const dy = y2 - y1
  const largo = Math.hypot(dx, dy) || 1
  const t = Math.min(distancia / largo, 0.4)
  return { x: x1 + dx * t, y: y1 + dy * t }
}

/**
 * Arista tipo "smoothstep" con hasta 3 etiquetas: multiplicidad en cada
 * extremo (patrón estándar UML, ej. "1" / "0..*") y la etiqueta libre de la
 * relación en el medio. React Flow no ofrece esto en sus edges de fábrica
 * (como mucho un `label` centrado), así que hace falta una arista custom.
 */
export function RelacionEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerStart,
  markerEnd,
  style,
  data,
  label,
}: EdgeProps<EdgeData>) {
  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  const puntoOrigen = puntoCercaDe(sourceX, sourceY, targetX, targetY, 26)
  const puntoDestino = puntoCercaDe(targetX, targetY, sourceX, sourceY, 26)
  const etiqueta = label ?? data?.etiqueta

  return (
    <>
      <BaseEdge id={id} path={path} markerStart={markerStart} markerEnd={markerEnd} style={style} />
      <EdgeLabelRenderer>
        {data?.multiplicidad_origen && (
          <div
            className="nodrag nopan edge-multiplicidad"
            style={{ transform: `translate(-50%, -50%) translate(${puntoOrigen.x}px, ${puntoOrigen.y}px)` }}
          >
            {data.multiplicidad_origen}
          </div>
        )}
        {data?.multiplicidad_destino && (
          <div
            className="nodrag nopan edge-multiplicidad"
            style={{ transform: `translate(-50%, -50%) translate(${puntoDestino.x}px, ${puntoDestino.y}px)` }}
          >
            {data.multiplicidad_destino}
          </div>
        )}
        {etiqueta && (
          <div
            className="nodrag nopan edge-etiqueta"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          >
            {etiqueta}
          </div>
        )}
      </EdgeLabelRenderer>
    </>
  )
}
