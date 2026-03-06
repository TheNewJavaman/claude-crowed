import { useCallback, useEffect, useMemo, useRef } from 'react'
import { forceCollide, forceLink, forceX, forceY } from 'd3-force'
import ForceGraph2D, {
  type ForceGraphMethods,
} from 'react-force-graph-2d'
import { ageColor } from './colors'
import type { GraphLink, GraphNode } from './types'

interface Props {
  nodes: GraphNode[]
  links: GraphLink[]
  selectedId: string | null
  highlightIds: Set<string>
  onNodeClick: (id: string) => void
  focusNodeId: string | null
}

export default function GraphView({
  nodes,
  links,
  selectedId,
  highlightIds,
  onNodeClick,
  focusNodeId,
}: Props) {
  const fgRef = useRef<ForceGraphMethods<GraphNode, GraphLink>>(undefined)

  // Compute edge count per node for sizing
  const edgeCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const link of links) {
      const src = typeof link.source === 'string' ? link.source : link.source.id
      const tgt = typeof link.target === 'string' ? link.target : link.target.id
      counts.set(src, (counts.get(src) ?? 0) + 1)
      counts.set(tgt, (counts.get(tgt) ?? 0) + 1)
    }
    return counts
  }, [links])

  const getRadius = useCallback(
    (node: GraphNode) => 4 + Math.min((edgeCounts.get(node.id) ?? 0) * 3, 24),
    [edgeCounts]
  )

  // Compute date range for age coloring
  const { oldest, newest } = useMemo(() => {
    if (nodes.length === 0) return { oldest: '', newest: '' }
    let lo = nodes[0].updated_at
    let hi = nodes[0].updated_at
    for (const n of nodes) {
      if (n.updated_at < lo) lo = n.updated_at
      if (n.updated_at > hi) hi = n.updated_at
    }
    return { oldest: lo, newest: hi }
  }, [nodes])

  // Focus on a specific node
  useEffect(() => {
    if (!focusNodeId || !fgRef.current) return
    const node = nodes.find((n) => n.id === focusNodeId)
    if (node && node.x != null && node.y != null) {
      fgRef.current.centerAt(node.x, node.y, 400)
      fgRef.current.zoom(3, 400)
    }
  }, [focusNodeId, nodes])

  // Stronger repulsion so nodes spread out; gentle gravity keeps groups nearby
  useEffect(() => {
    if (!fgRef.current) return
    const fg = fgRef.current
    const charge = fg.d3Force('charge')
    if (charge) (charge as { strength: (n: number) => void }).strength(-1400)
    fg.d3Force('gravityX', forceX(0).strength(0.05))
    fg.d3Force('gravityY', forceY(0).strength(0.05))
    fg.d3Force('collide', forceCollide((node: GraphNode) => getRadius(node) + 8).strength(1).iterations(6))

    const link = fg.d3Force('link')
    if (link) {
      const fl = link as ReturnType<typeof forceLink>
      fl.distance(60)
      fl.strength(0.3)
    }
  }, [getRadius])

  // Fit to screen on first load
  useEffect(() => {
    if (nodes.length > 0 && fgRef.current) {
      setTimeout(() => fgRef.current?.zoomToFit(400, 60), 500)
    }
  }, [nodes.length > 0])

  const graphData = useMemo(
    () => ({ nodes: [...nodes], links: [...links] }),
    [nodes, links]
  )

  const nodeColor = useCallback(
    (node: GraphNode) => {
      if (node.id === selectedId) return '#58a6ff'
      if (highlightIds.has(node.id)) return '#3fb950'
      return ageColor(node.updated_at, oldest, newest)
    },
    [selectedId, highlightIds, oldest, newest]
  )

  const nodeVal = useCallback(
    (node: GraphNode) => 1 + Math.min((edgeCounts.get(node.id) ?? 0) * 3, 30),
    [edgeCounts]
  )

  const nodeLabel = useCallback(
    (node: GraphNode) => node.title,
    []
  )

  // Nodes only — circles and glow, no labels
  const nodeCanvasObject = useCallback(
    (node: GraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const x = node.x ?? 0
      const y = node.y ?? 0
      const isSelected = node.id === selectedId
      const isHighlighted = highlightIds.has(node.id)
      const baseRadius = getRadius(node)

      const color = isSelected
        ? '#58a6ff'
        : isHighlighted
          ? '#3fb950'
          : ageColor(node.updated_at, oldest, newest)

      // Glow for selected/highlighted
      if (isSelected || isHighlighted) {
        ctx.beginPath()
        ctx.arc(x, y, baseRadius * 1.8, 0, 2 * Math.PI)
        ctx.fillStyle = isSelected
          ? 'rgba(88,166,255,0.15)'
          : 'rgba(63,185,80,0.12)'
        ctx.fill()
      }

      // Main circle
      ctx.beginPath()
      ctx.arc(x, y, baseRadius, 0, 2 * Math.PI)
      ctx.fillStyle = color
      ctx.fill()

      if (isSelected) {
        ctx.strokeStyle = '#58a6ff'
        ctx.lineWidth = 2 / globalScale
        ctx.stroke()
      }
    },
    [selectedId, highlightIds, oldest, newest, getRadius]
  )

  // Labels drawn in a separate pass after all nodes, with z-ordering
  const renderLabels = useCallback(
    (ctx: CanvasRenderingContext2D, globalScale: number) => {
      type Entry = {
        node: GraphNode
        alpha: number
        priority: number
        isSelected: boolean
        isHighlighted: boolean
      }
      const entries: Entry[] = []

      for (const node of nodes) {
        const isSelected = node.id === selectedId
        const isHighlighted = highlightIds.has(node.id)
        const importance = edgeCounts.get(node.id) ?? 0
        const showThreshold = importance >= 7 ? 0.15 : Math.max(0.5, 1.5 - importance * 0.25)

        if (isSelected || isHighlighted || globalScale > showThreshold) {
          const t = (globalScale - showThreshold) / Math.max(showThreshold, 0.5)
          const alpha = isSelected || isHighlighted
            ? 1.0
            : importance >= 7
              ? 1.0
              : Math.min(1.0, t * t)
          const priority = isSelected ? 1000 : isHighlighted ? 500 : importance
          entries.push({ node, alpha, priority, isSelected, isHighlighted })
        }
      }

      // Low priority drawn first (behind), high priority last (on top)
      entries.sort((a, b) => a.priority - b.priority)

      const fontSize = Math.max(11 / globalScale, 3)
      ctx.font = `${fontSize}px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'

      const maxChars = globalScale > 3 ? 50 : globalScale > 1.8 ? 35 : 22
      const padX = 4 / globalScale
      const padY = 2 / globalScale
      const radius = 3 / globalScale

      for (const { node, alpha, isSelected, isHighlighted } of entries) {
        const x = node.x ?? 0
        const y = node.y ?? 0
        const baseRadius = getRadius(node)

        const label = node.title.length > maxChars
          ? node.title.slice(0, maxChars - 1) + '…'
          : node.title

        const labelY = y + baseRadius + (fontSize / 2) + 3 / globalScale
        const metrics = ctx.measureText(label)
        const w = metrics.width + padX * 2
        const h = fontSize + padY * 2

        // Background pill
        ctx.beginPath()
        ctx.roundRect(x - w / 2, labelY - h / 2, w, h, radius)
        ctx.fillStyle = isSelected
          ? `rgba(30,38,50,${alpha * 0.92})`
          : `rgba(13,17,23,${alpha * 0.82})`
        ctx.fill()

        // Subtle border on selected/highlighted
        if (isSelected || isHighlighted) {
          ctx.strokeStyle = isSelected
            ? `rgba(88,166,255,${alpha * 0.4})`
            : `rgba(63,185,80,${alpha * 0.3})`
          ctx.lineWidth = 1 / globalScale
          ctx.stroke()
        }

        // Text — muted for regular, brighter for selected
        ctx.fillStyle = isSelected
          ? `rgba(230,237,243,${alpha})`
          : isHighlighted
            ? `rgba(201,209,217,${alpha})`
            : `rgba(139,148,158,${alpha})`
        ctx.fillText(label, x, labelY)
      }
    },
    [nodes, selectedId, highlightIds, edgeCounts, getRadius]
  )

  const linkColor = useCallback(
    () => 'rgba(88,166,255,0.3)',
    []
  )

  const linkWidth = useCallback(
    () => 1.5,
    []
  )

  const handleClick = useCallback(
    (node: GraphNode) => {
      onNodeClick(node.id)
    },
    [onNodeClick]
  )

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={graphData}
      nodeId="id"
      nodeVal={nodeVal}
      nodeLabel={nodeLabel}
      nodeColor={nodeColor}
      nodeCanvasObject={nodeCanvasObject}
      nodeCanvasObjectMode={() => 'replace'}
      onNodeClick={handleClick}
      onRenderFramePost={renderLabels}
      linkColor={linkColor}
      linkWidth={linkWidth}
      linkDirectionalParticles={0}
      enablePointerInteraction={true}
      backgroundColor="#0d1117"
      d3AlphaDecay={0.015}
      d3VelocityDecay={0.25}
      cooldownTicks={300}
      warmupTicks={100}
    />
  )
}
