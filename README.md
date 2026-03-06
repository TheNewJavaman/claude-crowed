# claude-crowed

A persistent semantic memory system for Claude Code, built as an MCP server. Replaces Claude Code's built-in flat-file memories with a structured, searchable, versioned document store.

## Features

- **Semantic search** via sentence-transformers (nomic-embed-text-v1.5) + sqlite-vec
- **Versioned memories** with full history (update creates a new version, old versions preserved)
- **Soft-delete** with rate limiting (5 per session) and undo
- **Bidirectional links** between related memories
- **Duplicate detection** with adjustable similarity threshold
- **Timeline browsing** with cursor-based pagination
- **Export/import** for backup and portability
- **Migration tool** to import existing CLAUDE.md and auto-memory files
- **Hot-reload dev mode** via stdio proxy that watches for git commits
- **Web visualizer** — force-directed graph of memories with search, detail browsing, and CRUD

## Install

```bash
uv sync
```

## Setup

```bash
claude mcp add --scope user claude-crowed -- uv run --directory /path/to/claude-crowed claude-crowed
```

Then add the memory directive to your `~/.claude/CLAUDE.md` so Claude knows to use it:

```markdown
## Memory System (claude-crowed)

You have access to a persistent memory system via MCP tools (server: claude-crowed).
This is your primary knowledge store.

### Search Discipline
- At the START of every task, call `memory_recall` (or `memory_search`) with relevant keywords.
- Mid-task: whenever you encounter unfamiliar code, patterns, or errors, search again.

### When to Store
- After diagnosing a root cause ("the problem was X because Y").
- When you discover a gotcha or workaround.
- After every git commit, for novel decisions or patterns.
- Store as you go, not at the end — mid-task insights are most valuable.

### Linking
- After storing or reading a memory, review the `link_suggestions` in the response.
  Call `memory_link` for any that are related.
```

## Usage

### MCP Tools (used by Claude)

| Tool | Purpose |
|---|---|
| `memory_search` | Semantic search, returns titles only |
| `memory_read` | Fetch full content of a memory (with link suggestions) |
| `memory_recall` | Search + read top results in one call (fewer round trips) |
| `memory_store` | Store a new memory (with dedup check, returns link suggestions) |
| `memory_update` | Create a new version of a memory |
| `memory_delete` | Soft-delete (rate-limited, reversible) |
| `memory_undelete` | Restore a deleted memory |
| `memory_history` | View all versions of a memory |
| `memory_timeline` | Browse chronologically with pagination |
| `memory_link` | Create bidirectional link between memories |
| `memory_unlink` | Remove a link |
| `memory_related` | List linked memories |
| `memory_export` | Export all data to JSON |
| `memory_import` | Import from JSON export |
| `memory_migrate` | Discover and split existing memory files for migration |
| `memory_threshold` | View/adjust duplicate similarity threshold |
| `memory_stats` | Summary statistics |

### CLI

```bash
# Start MCP server (default, stdio transport)
claude-crowed serve

# Development mode with hot-reload on git commits
claude-crowed dev

# Export/import
claude-crowed export [--output path]
claude-crowed import <path> [--overwrite]

# Restore from backup
claude-crowed restore <backup-path>

# Rebuild embedding index
claude-crowed rebuild-embeddings

# Show stats
claude-crowed stats

# Launch web visualizer (opens browser)
claude-crowed visualize [--port 4242] [--no-browser]
```

### Visualizer

The web visualizer shows all memories as a force-directed graph. Nodes are colored
by age (blue = recent, gold = older) and sized by link count. Explicit links between
memories are shown as edges.

```bash
uv sync --extra visualizer
uv run claude-crowed visualize
```

The frontend is built automatically on launch if `visualizer/dist/` is missing or
stale (requires npm). It skips the build if the dist is already up to date.

Features:
- Force-directed graph with age coloring and link-based clustering
- Labels appear progressively as you zoom in (high-link nodes first)
- Semantic search (press `/` to focus)
- Click any node to browse its content, metadata, and links
- Delete/restore memories from the detail panel
- Navigate between linked memories

## Architecture

- **SQLite** with WAL mode for the memory store
- **sqlite-vec** for vector similarity search (vec0 virtual tables)
- **sentence-transformers** with nomic-embed-text-v1.5 (768-dim, CPU by default)
- **Background model loading** — embedding model loads in a thread during MCP handshake (~1s startup)
- **Two-phase retrieval** — search returns titles/metadata, read fetches full content
- **Embedding prefixes** — `search_document:` for storage, `search_query:` for retrieval

## Data

All data is stored in `~/.local/share/claude-crowed/`:
- `crowed.db` — SQLite database
- `backups/` — rolling backups (max 30, created on each server start)
- `exports/` — JSON exports

## Tests

```bash
uv run pytest
```
