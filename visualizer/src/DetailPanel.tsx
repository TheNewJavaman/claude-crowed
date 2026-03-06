import { useEffect, useState } from 'react'
import { deleteMemory, fetchMemory, undeleteMemory } from './api'
import {
  ACCENT,
  BORDER,
  DANGER,
  PANEL_BG,
  SOURCE_COLORS,
  SUCCESS,
  TEXT,
  TEXT_DIM,
} from './colors'
import type { MemoryFull } from './types'

interface Props {
  memoryId: string | null
  onClose: () => void
  onNavigate: (id: string) => void
  onDataChanged: () => void
}

export default function DetailPanel({
  memoryId,
  onClose,
  onNavigate,
  onDataChanged,
}: Props) {
  const [memory, setMemory] = useState<MemoryFull | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [actionMsg, setActionMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!memoryId) {
      setMemory(null)
      return
    }
    setLoading(true)
    setError(null)
    setActionMsg(null)
    fetchMemory(memoryId)
      .then((data) => {
        if ('error' in data && (data as Record<string, unknown>).error) {
          setError((data as Record<string, unknown>).error as string)
          setMemory(null)
        } else {
          setMemory(data as MemoryFull)
        }
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [memoryId])

  const handleDelete = async () => {
    if (!memory) return
    const res = await deleteMemory(memory.id)
    if (res.error) {
      setActionMsg(res.error)
    } else {
      setActionMsg('Deleted')
      onDataChanged()
    }
  }

  const handleUndelete = async () => {
    if (!memory) return
    const res = await undeleteMemory(memory.id)
    if (res.error) {
      setActionMsg(res.error)
    } else {
      setActionMsg('Restored')
      onDataChanged()
    }
  }

  if (!memoryId) return null

  const formatDate = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div
      style={{
        width: 400,
        minWidth: 400,
        height: '100%',
        background: PANEL_BG,
        borderLeft: `1px solid ${BORDER}`,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: `1px solid ${BORDER}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>Memory Detail</span>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: TEXT_DIM,
            fontSize: 18,
            cursor: 'pointer',
            padding: '0 4px',
          }}
        >
          ×
        </button>
      </div>

      {loading && (
        <div style={{ padding: 20, color: TEXT_DIM }}>Loading...</div>
      )}
      {error && (
        <div style={{ padding: 20, color: DANGER }}>{error}</div>
      )}

      {memory && (
        <div style={{ padding: '20px 20px 32px 20px', flex: 1 }}>
          {/* Title */}
          <h2
            style={{
              color: TEXT,
              fontSize: 16,
              fontWeight: 600,
              margin: '0 0 12px 0',
              lineHeight: 1.4,
            }}
          >
            {memory.title}
          </h2>

          {/* Tags */}
          <div
            style={{
              display: 'flex',
              gap: 8,
              marginBottom: 16,
              flexWrap: 'wrap',
            }}
          >
            <Tag
              label={memory.source}
              color={SOURCE_COLORS[memory.source] || TEXT_DIM}
            />
            <Tag label={`v${memory.version}`} color={TEXT_DIM} />
            {memory.is_deleted && <Tag label="deleted" color={DANGER} />}
          </div>

          {/* Content */}
          <div
            style={{
              background: '#0d1117',
              border: `1px solid ${BORDER}`,
              borderRadius: 8,
              padding: 16,
              marginBottom: 16,
              color: TEXT,
              fontSize: 13,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {memory.content}
          </div>

          {/* Metadata */}
          <div style={{ marginBottom: 16 }}>
            <MetaRow label="Created" value={formatDate(memory.created_at)} />
            <MetaRow label="Updated" value={formatDate(memory.updated_at)} />
            <MetaRow
              label="Accessed"
              value={formatDate(memory.last_accessed_at)}
            />
            <MetaRow label="ID" value={memory.id} mono />
          </div>

          {/* Links */}
          {memory.links.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div
                style={{
                  color: TEXT_DIM,
                  fontSize: 11,
                  textTransform: 'uppercase',
                  letterSpacing: 1,
                  marginBottom: 8,
                }}
              >
                Linked Memories ({memory.links.length})
              </div>
              {memory.links.map((link) => (
                <button
                  key={link.id}
                  onClick={() => onNavigate(link.id)}
                  style={{
                    display: 'block',
                    width: '100%',
                    padding: '8px 12px',
                    marginBottom: 4,
                    background: '#1c2128',
                    border: `1px solid ${BORDER}`,
                    borderRadius: 6,
                    color: ACCENT,
                    fontSize: 13,
                    textAlign: 'left',
                    cursor: 'pointer',
                    textDecoration: 'none',
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.borderColor = ACCENT)
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.borderColor = BORDER)
                  }
                >
                  {link.title}
                </button>
              ))}
            </div>
          )}

          {/* Actions */}
          <div
            style={{
              display: 'flex',
              gap: 8,
              paddingTop: 8,
              borderTop: `1px solid ${BORDER}`,
            }}
          >
            {!memory.is_deleted ? (
              <ActionButton
                label="Delete"
                color={DANGER}
                onClick={handleDelete}
              />
            ) : (
              <ActionButton
                label="Restore"
                color={SUCCESS}
                onClick={handleUndelete}
              />
            )}
          </div>

          {actionMsg && (
            <div
              style={{
                marginTop: 8,
                padding: '6px 10px',
                borderRadius: 6,
                background: '#1c2128',
                color: actionMsg.includes('error') ? DANGER : SUCCESS,
                fontSize: 12,
              }}
            >
              {actionMsg}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Tag({ label, color }: { label: string; color: string }) {
  return (
    <span
      style={{
        padding: '2px 8px',
        borderRadius: 12,
        border: `1px solid ${color}40`,
        color,
        fontSize: 11,
        fontWeight: 500,
      }}
    >
      {label}
    </span>
  )
}

function MetaRow({
  label,
  value,
  mono,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '4px 0',
        fontSize: 12,
      }}
    >
      <span style={{ color: TEXT_DIM }}>{label}</span>
      <span
        style={{
          color: TEXT,
          fontFamily: mono ? 'monospace' : 'inherit',
          fontSize: mono ? 10 : 12,
          maxWidth: 220,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {value}
      </span>
    </div>
  )
}

function ActionButton({
  label,
  color,
  onClick,
}: {
  label: string
  color: string
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '6px 16px',
        borderRadius: 6,
        border: `1px solid ${color}`,
        background: `${color}15`,
        color,
        fontSize: 12,
        fontWeight: 500,
        cursor: 'pointer',
      }}
      onMouseEnter={(e) =>
        (e.currentTarget.style.background = `${color}30`)
      }
      onMouseLeave={(e) =>
        (e.currentTarget.style.background = `${color}15`)
      }
    >
      {label}
    </button>
  )
}
