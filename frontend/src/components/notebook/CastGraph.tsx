import { useMemo, useState } from 'react'
import { Background, Handle, Position, ReactFlow, getBezierPath, type Edge, type EdgeProps, type Node, type NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { cn } from '@/lib/cn'
import { circlePositions, linkStroke, type GraphLink, type GraphPerson } from './board'

type CastNodeData = { label: string }
type CastFlowNode = Node<CastNodeData, 'cast'>
type CastEdgeData = { text: string }
type CastFlowEdge = Edge<CastEdgeData, 'hover'>

function CastNode({ data }: NodeProps<CastFlowNode>) {
  return (
    <div className="cast-node">
      <Handle type="target" position={Position.Left} />
      <span>{data.label}</span>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

function HoverEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style, markerEnd, data }: EdgeProps<CastFlowEdge>) {
  const [path] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition })
  return (
    <path id={id} className="react-flow__edge-path" d={path} style={style} markerEnd={markerEnd}>
      {data?.text ? <title>{data.text}</title> : null}
    </path>
  )
}

const nodeTypes = { cast: CastNode }
const edgeTypes = { hover: HoverEdge }

export function CastGraph({
  people,
  links,
  label,
  emptyNote,
  tone = 'paper',
  height = 260,
}: {
  people: GraphPerson[]
  links: GraphLink[]
  label: string
  emptyNote: string
  tone?: 'paper' | 'lacquer'
  height?: number
}) {
  const [selected, setSelected] = useState<string | null>(null)
  const names = useMemo(() => new Map(people.map((person) => [person.id, person.name])), [people])
  const nodes = useMemo<CastFlowNode[]>(() => {
    const positions = circlePositions(people.map((person) => person.id))
    return people.map((person) => ({
      id: person.id,
      type: 'cast' as const,
      position: positions[person.id] ?? { x: 0, y: 0 },
      data: { label: person.name },
      draggable: true,
    }))
  }, [people])
  const edges = useMemo<CastFlowEdge[]>(
    () =>
      links.map((link) => ({
        id: link.id,
        source: link.source,
        target: link.target,
        type: 'hover' as const,
        data: { text: link.text },
        animated: link.channel === 'private',
        markerEnd: {
          type: 'arrowclosed',
          color: linkStroke(link.channel),
          width: 16,
          height: 16,
        },
        style: {
          stroke: linkStroke(link.channel),
          strokeWidth: selected === link.id ? 3.5 : 1.75,
        },
      })),
    [links, selected],
  )
  const castKey = people.map((person) => person.id).join('|')

  return (
    <div className={cn('cast-graph', tone === 'lacquer' && 'cast-graph--lacquer')}>
      <div style={{ height }} aria-label={label}>
        {people.length > 0 ? (
          <ReactFlow
            key={castKey}
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.4}
            maxZoom={1.6}
            colorMode="light"
            zoomOnScroll={false}
            panOnScroll={false}
            nodesConnectable={false}
            elementsSelectable
            onEdgeClick={(_, edge) => setSelected(edge.id)}
            onPaneClick={() => setSelected(null)}
            style={{ width: '100%', height: '100%', background: 'transparent' }}
          >
            <Background color={tone === 'lacquer' ? '#c9a24b' : '#5a331c'} gap={16} size={1} />
          </ReactFlow>
        ) : (
          <p className="ink-soft" style={{ margin: 8, fontSize: 13 }}>
            No one is in this case.
          </p>
        )}
      </div>
      {links.length === 0 ? (
        <p className={cn(tone === 'lacquer' ? 'muted' : 'ink-soft')} style={{ fontSize: 13, margin: '8px 8px 4px' }}>
          {emptyNote}
        </p>
      ) : (
        <ul className="cast-graph__lines">
          {links.map((link) => (
            <li key={link.id}>
              <button
                type="button"
                className={cn('cast-graph__line', selected === link.id && 'cast-graph__line--selected')}
                aria-pressed={selected === link.id}
                onClick={() => setSelected(link.id)}
              >
                <span className="cast-graph__who">
                  {names.get(link.source) ?? link.source} to {names.get(link.target) ?? link.target}
                  <span className="subtle-caps"> {link.channel}</span>
                </span>
                {link.text ? <span className="cast-graph__text">{link.text}</span> : null}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
