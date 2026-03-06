export interface GraphNode {
  id: string
  title: string
  created_at: string
  updated_at: string
  source: string
  // Set by force graph
  x?: number
  y?: number
}

export interface GraphLink {
  source: string | GraphNode
  target: string | GraphNode
  similarity?: number
}

export interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
}

export interface MemoryFull {
  id: string
  version: number
  title: string
  content: string
  created_at: string
  updated_at: string
  last_accessed_at: string
  source: string
  is_deleted: boolean
}

export interface SearchResult {
  id: string
  title: string
  similarity: number
  created_at: string
  updated_at: string
}

export interface Stats {
  total_memories: number
  total_deleted: number
  total_versions: number
  oldest_memory: string | null
  newest_memory: string | null
  db_size_bytes: number
}
