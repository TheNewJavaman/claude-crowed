import type { GraphData, MemoryFull, SearchResult, Stats } from './types'

const BASE = ''

export async function fetchGraph(): Promise<GraphData> {
  const res = await fetch(`${BASE}/api/graph`)
  return res.json()
}

export async function fetchMemory(id: string): Promise<MemoryFull> {
  const res = await fetch(`${BASE}/api/memories/${id}`)
  return res.json()
}

export async function searchMemories(
  query: string,
  k = 20
): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q: query, k: String(k) })
  const res = await fetch(`${BASE}/api/search?${params}`)
  return res.json()
}

export async function deleteMemory(
  id: string
): Promise<{ status?: string; error?: string }> {
  const res = await fetch(`${BASE}/api/memories/${id}/delete`, {
    method: 'POST',
  })
  return res.json()
}

export async function undeleteMemory(
  id: string
): Promise<{ status?: string; error?: string }> {
  const res = await fetch(`${BASE}/api/memories/${id}/undelete`, {
    method: 'POST',
  })
  return res.json()
}

export async function linkMemories(
  idA: string,
  idB: string
): Promise<{ status?: string; error?: string }> {
  const params = new URLSearchParams({ id_a: idA, id_b: idB })
  const res = await fetch(`${BASE}/api/link?${params}`, { method: 'POST' })
  return res.json()
}

export async function unlinkMemories(
  idA: string,
  idB: string
): Promise<{ status?: string; error?: string }> {
  const params = new URLSearchParams({ id_a: idA, id_b: idB })
  const res = await fetch(`${BASE}/api/unlink?${params}`, { method: 'POST' })
  return res.json()
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${BASE}/api/stats`)
  return res.json()
}
