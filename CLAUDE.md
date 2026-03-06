# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run all tests (uses in-memory SQLite, no GPU/model needed)
uv run pytest

# Run a single test
uv run pytest tests/test_memory_store.py::TestSearch::test_search_returns_results

# Start MCP server (stdio transport)
uv run claude-crowed serve

# Dev mode with hot-reload on git commits
uv run claude-crowed dev

# CLI utilities
uv run claude-crowed stats
uv run claude-crowed export [--output path]
uv run claude-crowed import <path> [--overwrite]
uv run claude-crowed restore <backup-path>
uv run claude-crowed rebuild-embeddings

# Web visualizer (requires: uv sync --extra visualizer)
uv run claude-crowed visualize [--port 4242] [--no-browser]

# Frontend dev (from visualizer/)
cd visualizer && npm run dev  # Vite dev server, proxies /api to :4242
```

## Architecture

MCP server exposing 14 tools for persistent semantic memory. Claude stores/retrieves knowledge across sessions via these tools.

### Data Flow

1. **Store**: Text → `embed_document("search_document: {title}\n{content}")` → 768-dim vector → SQLite + sqlite-vec. Returns `{id}`.
2. **Search**: Query → `embed_query("search_query: {query}")` → vec0 `MATCH` → ranked results (titles only)
3. **Read**: Fetch full content by ID (only tool that bumps `last_accessed_at`)
4. **Recall**: Combines search + read in one call. Returns full content for top-k results + titles for the rest. Preferred over search+read for fewer round trips.
5. **Related**: Finds semantically similar memories via embedding nearest-neighbor lookup (dynamic, no stored links).

The `search_document:`/`search_query:` prefixes are required by the nomic-embed-text-v1.5 model.

### Key Modules

- **`server.py`** — FastMCP tool definitions + CLI entry point. Tools are thin wrappers around `MemoryStore` methods. `_init_server()` starts background model loading, creates DB, takes startup backup.
- **`memory_store.py`** — Core CRUD, search, recall, versioning, import/export. All business logic lives here. `store()` returns a dict (`{id}` on success, `{error}` on failure). Other methods return Pydantic models or `dict` with `"error"` key on failure.
- **`embedding.py`** — Lazy model loading in a background thread (`start_loading()` + `threading.Event`). Model loads during MCP handshake so first tool call doesn't block. CPU-only by default.
- **`db.py`** — Schema definition, `get_connection()` loads sqlite-vec extension. WAL mode, foreign keys enabled.
- **`models.py`** — Pydantic response models.
- **`proxy.py`** — `McpReloadProxy`: stdio proxy that watches `.git/refs/heads/` for commits and restarts the child MCP server, replaying the MCP init handshake. Used by `claude-crowed dev`.
- **`visualizer.py`** — FastAPI backend for the web visualizer. Serves graph data (nodes + dynamic similarity edges from nearest-neighbor queries), memory detail, search, delete/undelete. Auto-builds frontend if `dist/` is missing or stale. Serves the built frontend from `visualizer/dist/`.
- **`visualizer/`** (project root) — React + Vite + TypeScript frontend. Uses `react-force-graph-2d` for force-directed graph rendering. Dark theme. Search bar, detail panel on click, delete/restore actions.

### sqlite-vec Quirks

- vec0 virtual table query results use **positional indexing** (`row[0]`, `row[1]`), not named columns — SQLite's `Row` factory doesn't work for vec0 result columns.
- Embeddings stored as raw bytes via `struct.pack(f"{dim}f", *values)`.
- Cannot use `INSERT OR REPLACE` on vec0 tables — must `DELETE` then `INSERT`.

### Versioning Model

Updates create a new row with `parent_id` pointing to the old version. The old version's embedding is removed from the index. History is reconstructed via recursive CTE walking `parent_id` chains in both directions.

### Deduplication

`store()` checks the top-1 nearest neighbor against a configurable similarity threshold (default 0.85, persisted in `settings` table). `force=True` bypasses the check.

### Testing

Tests use mock embeddings (seeded `random.gauss` from SHA256 of text) — no model loading needed. The `store` and `db` fixtures in `conftest.py` use `:memory:` SQLite. Mock embeddings produce deterministic vectors but don't capture semantic similarity, so dedup tests use exact text matches.

### Data Location

All persistent data in `~/.local/share/claude-crowed/`: `memories.db`, `backups/` (rolling 30), `exports/`.
