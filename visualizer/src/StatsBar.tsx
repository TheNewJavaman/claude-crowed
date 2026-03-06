import { BORDER, TEXT, TEXT_DIM } from './colors'
import type { Stats } from './types'

interface Props {
  stats: Stats | null
  nodeCount: number
  edgeCount: number
}

export default function StatsBar({ stats, nodeCount, edgeCount }: Props) {
  if (!stats) return null

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div
      style={{
        display: 'flex',
        gap: 20,
        padding: '6px 16px',
        borderTop: `1px solid ${BORDER}`,
        background: '#161b22',
        fontSize: 11,
        color: TEXT_DIM,
        flexShrink: 0,
      }}
    >
      <span>
        <strong style={{ color: TEXT }}>{stats.total_memories}</strong> memories
      </span>
      <span>
        <strong style={{ color: TEXT }}>{nodeCount}</strong> nodes
      </span>
      <span>
        <strong style={{ color: TEXT }}>{edgeCount}</strong> edges
      </span>
      <span>
        <strong style={{ color: TEXT }}>{stats.total_deleted}</strong> deleted
      </span>
      <span>{formatSize(stats.db_size_bytes)}</span>
    </div>
  )
}
