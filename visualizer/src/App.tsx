import { useCallback, useEffect, useState } from 'react'
import { fetchGraph, fetchStats } from './api'
import { BG, BORDER, TEXT, TEXT_DIM } from './colors'
import DetailPanel from './DetailPanel'
import GraphView from './GraphView'
import SearchBar from './SearchBar'
import StatsBar from './StatsBar'
import type { GraphLink, GraphNode, Stats } from './types'

export default function App() {
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [links, setLinks] = useState<GraphLink[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [focusId, setFocusId] = useState<string | null>(null)
  const [highlightIds] = useState<Set<string>>(new Set())
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      setLoading(true)
      const [graphData, statsData] = await Promise.all([
        fetchGraph(),
        fetchStats(),
      ])
      setNodes(graphData.nodes)
      setLinks(graphData.links)
      setStats(statsData)
      setError(null)
    } catch (e) {
      setError(`Failed to load: ${e}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleNodeClick = useCallback((id: string) => {
    setSelectedId(id)
  }, [])

  const handleSearchSelect = useCallback((id: string) => {
    setSelectedId(id)
    setFocusId(id)
    setTimeout(() => setFocusId(null), 500)
  }, [])

  const handleNavigate = useCallback((id: string) => {
    setSelectedId(id)
    setFocusId(id)
    setTimeout(() => setFocusId(null), 500)
  }, [])

  const handleDataChanged = useCallback(() => {
    loadData()
  }, [loadData])

  if (error) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          background: BG,
          color: '#f85149',
          fontFamily: 'system-ui',
          fontSize: 16,
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <div>{error}</div>
        <div style={{ color: TEXT_DIM, fontSize: 13 }}>
          Make sure the backend is running: <code>claude-crowed visualize</code>
        </div>
      </div>
    )
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        background: BG,
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
      }}
    >
      {/* Top bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          padding: '8px 16px',
          borderBottom: `1px solid ${BORDER}`,
          background: '#161b22',
          flexShrink: 0,
          zIndex: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: TEXT }}>
            crowed
          </span>
          <span style={{ fontSize: 12, color: TEXT_DIM }}>
            memory visualizer
          </span>
        </div>
        <SearchBar onSelect={handleSearchSelect} />
        <div style={{ flex: 1 }} />
        {loading && (
          <span style={{ color: TEXT_DIM, fontSize: 12 }}>Loading...</span>
        )}
        <button
          onClick={loadData}
          style={{
            padding: '5px 12px',
            borderRadius: 6,
            border: `1px solid ${BORDER}`,
            background: 'none',
            color: TEXT_DIM,
            fontSize: 12,
            cursor: 'pointer',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = TEXT)}
          onMouseLeave={(e) => (e.currentTarget.style.color = TEXT_DIM)}
          title="Reload graph data"
        >
          Refresh
        </button>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {nodes.length === 0 && !loading ? (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: TEXT_DIM,
              fontSize: 14,
            }}
          >
            No memories yet. Store some using Claude Code.
          </div>
        ) : (
          <GraphView
            nodes={nodes}
            links={links}
            selectedId={selectedId}
            highlightIds={highlightIds}
            onNodeClick={handleNodeClick}
            focusNodeId={focusId}
          />
        )}

        {selectedId && (
          <div style={{ position: 'absolute', top: 0, right: 0, bottom: 0, zIndex: 5 }}>
            <DetailPanel
              memoryId={selectedId}
              onClose={() => setSelectedId(null)}
              onNavigate={handleNavigate}
              onDataChanged={handleDataChanged}
            />
          </div>
        )}
      </div>

      <StatsBar
        stats={stats}
        nodeCount={nodes.length}
        edgeCount={links.length}
      />
    </div>
  )
}
