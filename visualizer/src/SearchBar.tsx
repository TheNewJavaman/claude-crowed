import { useCallback, useEffect, useRef, useState } from 'react'
import { searchMemories } from './api'
import { BORDER, PANEL_BG, TEXT, TEXT_DIM } from './colors'
import type { SearchResult } from './types'

interface Props {
  onSelect: (id: string) => void
}

export default function SearchBar({ onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  // Global "/" shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
        const tag = (e.target as HTMLElement)?.tagName
        if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
          e.preventDefault()
          inputRef.current?.focus()
        }
      }
      if (e.key === 'Escape') {
        setOpen(false)
        inputRef.current?.blur()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const doSearch = useCallback(
    async (q: string) => {
      if (q.trim().length < 2) {
        setResults([])
        setOpen(false)
        return
      }
      setLoading(true)
      try {
        const res = await searchMemories(q, 10)
        setResults(Array.isArray(res) ? res : [])
        setOpen(true)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    },
    []
  )

  const onChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setQuery(val)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => doSearch(val), 300)
  }

  const handleSelect = (id: string) => {
    setOpen(false)
    setQuery('')
    onSelect(id)
  }

  return (
    <div style={{ position: 'relative', width: 360 }}>
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={onChange}
        onFocus={() => results.length > 0 && setOpen(true)}
        placeholder='Search memories (press "/")'
        style={{
          width: '100%',
          padding: '8px 12px',
          background: PANEL_BG,
          border: `1px solid ${BORDER}`,
          borderRadius: 8,
          color: TEXT,
          fontSize: 14,
          outline: 'none',
          boxSizing: 'border-box',
        }}
      />
      {loading && (
        <span
          style={{
            position: 'absolute',
            right: 12,
            top: 10,
            color: TEXT_DIM,
            fontSize: 12,
          }}
        >
          ...
        </span>
      )}
      {open && results.length > 0 && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: 4,
            background: PANEL_BG,
            border: `1px solid ${BORDER}`,
            borderRadius: 8,
            maxHeight: 320,
            overflowY: 'auto',
            zIndex: 100,
          }}
        >
          {results.map((r) => (
            <button
              key={r.id}
              onClick={() => handleSelect(r.id)}
              style={{
                display: 'block',
                width: '100%',
                padding: '8px 12px',
                background: 'none',
                border: 'none',
                borderBottom: `1px solid ${BORDER}`,
                color: TEXT,
                fontSize: 13,
                textAlign: 'left',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = '#1c2128')
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = 'none')
              }
            >
              <div style={{ fontWeight: 500 }}>{r.title}</div>
              <div style={{ color: TEXT_DIM, fontSize: 11, marginTop: 2 }}>
                similarity: {(r.similarity * 100).toFixed(1)}%
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
