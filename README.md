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

## Install

```bash
uv sync
```

## Setup

Add to your Claude Code MCP config (`~/.claude.json`):

```json
{
  "mcpServers": {
    "claude-crowed": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/claude-crowed", "claude-crowed"]
    }
  }
}
```

Then add the memory directive to your `~/.claude/CLAUDE.md` so Claude knows to use it:

```markdown
## Memory System (claude-crowed)

You have access to a persistent memory system via MCP tools (server: claude-crowed).
This is your primary knowledge store.

### Always Do
- At the START of any task, call `memory_search` with relevant keywords.
- After completing a task that produced a novel insight, decision, or finding, call `memory_store`.
- When you learn something worth remembering across sessions, store it immediately.
```

## Usage

### MCP Tools (used by Claude)

| Tool | Purpose |
|---|---|
| `memory_search` | Semantic search, returns titles only |
| `memory_read` | Fetch full content of a memory |
| `memory_store` | Store a new memory (with dedup check) |
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
```

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
