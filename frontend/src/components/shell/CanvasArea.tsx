import { useEffect } from 'react'
import type { MouseEvent } from 'react'
import ReactFlow, {
  Background,
  BackgroundVariant,
  ConnectionMode,
  Controls,
  useReactFlow,
} from 'reactflow'
import type {
  Connection,
  Edge,
  Node,
  OnEdgesChange,
  OnNodesChange,
} from 'reactflow'

import { ClassNode } from './ClassNode'
import type { ClassNodeData } from './ClassNode'
import { RelacionEdge } from './RelacionEdge'
import type { EdgeData } from './useDiagrama'
import { UmlMarkers } from './UmlMarkers'
import './diagram.css'

const nodeTypes = { classNode: ClassNode }
const edgeTypes = { relacion: RelacionEdge }

type Props = {
  nodes: Node<ClassNodeData>[]
  edges: Edge<EdgeData>[]
  onNodesChange: OnNodesChange
  onEdgesChange: OnEdgesChange
  onNodeDragStop: () => void
  onConnect: (connection: Connection) => void
  onEdgeDoubleClick: (event: MouseEvent, edge: Edge<EdgeData>) => void
  cargando: boolean
  error: string | null
}

export function CanvasArea({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onNodeDragStop,
  onConnect,
  onEdgeDoubleClick,
  cargando,
  error,
}: Props) {
  const { fitView } = useReactFlow()

  // Ajusta la vista una vez que el diagrama terminó de cargar (fitView del
  // <ReactFlow> solo actúa en el montaje, y en el montaje aún no hay nodos).
  useEffect(() => {
    if (!cargando && !error && nodes.length > 0) {
      const t = setTimeout(() => fitView({ padding: 0.25 }), 0)
      return () => clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cargando])

  return (
    <main className="app-canvas">
      <UmlMarkers />
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeDragStop={onNodeDragStop}
        onConnect={onConnect}
        onEdgeDoubleClick={onEdgeDoubleClick}
        connectionMode={ConnectionMode.Loose}
        deleteKeyCode={['Backspace', 'Delete']}
        nodesFocusable={false}
      >
        <Background id="minor" variant={BackgroundVariant.Dots} gap={16} size={1} color="#d3d8e0" />
        <Background id="major" variant={BackgroundVariant.Lines} gap={96} lineWidth={1} color="#e7eaf0" />
        <Controls showInteractive={false} />
      </ReactFlow>

      {cargando && <div className="canvas-overlay">Cargando diagrama…</div>}
      {error && <div className="canvas-overlay canvas-overlay--error">{error}</div>}
      {!cargando && !error && nodes.length === 0 && (
        <div className="canvas-overlay canvas-overlay--hint">
          Este diagrama está vacío. Usa "Nueva clase" para empezar.
        </div>
      )}
    </main>
  )
}
