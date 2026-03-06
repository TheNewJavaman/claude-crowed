/** Interpolate node color by recency: old=cool blue → recent=warm amber */
export function ageColor(updatedAt: string, oldest: string, newest: string): string {
  const t = oldest === newest
    ? 0.5
    : (new Date(updatedAt).getTime() - new Date(oldest).getTime()) /
      (new Date(newest).getTime() - new Date(oldest).getTime())

  // Blue → Teal → Amber
  const r = Math.round(30 + t * 200)
  const g = Math.round(100 + t * 80)
  const b = Math.round(220 - t * 160)
  return `rgb(${r},${g},${b})`
}

/** Source badge colors */
export const SOURCE_COLORS: Record<string, string> = {
  manual: '#58a6ff',
  conversation: '#3fb950',
  auto: '#d2a8ff',
}

export const BG = '#0d1117'
export const PANEL_BG = '#161b22'
export const BORDER = '#30363d'
export const TEXT = '#c9d1d9'
export const TEXT_DIM = '#8b949e'
export const ACCENT = '#58a6ff'
export const DANGER = '#f85149'
export const SUCCESS = '#3fb950'
