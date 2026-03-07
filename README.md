# claude-crowed

A persistent semantic memory system for Claude Code, built as an MCP server. Replaces Claude Code's built-in flat-file memories with a structured, searchable, versioned document store.

## Features

- **Semantic search** via sentence-transformers (nomic-embed-text-v1.5) + sqlite-vec
- **Versioned memories** with full history (update creates a new version, old versions preserved)
- **Soft-delete** with rate limiting (5 per session) and undo
- **Dynamic "see also"** via embedding nearest-neighbor lookup (no manual linking needed)
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

Then add the memory directive to your `~/.claude/CLAUDE.md` so Claude knows to use it.

The core principle is **search before work, store after insight** — this prevents
repeating expensive operations like codebase exploration and web research across sessions.

```markdown
## Memory System (claude-crowed)

You have access to a persistent memory system via MCP tools (server: claude-crowed).
This is your primary knowledge store — use it instead of accumulating knowledge in
this file or auto-memory files.

### Search Discipline
- At the **START** of every task, call `memory_recall` (or `memory_search`) with relevant keywords.
  Do not skip this step — you have no passive context from crowed without it.
- **Mid-task**: whenever you encounter unfamiliar code, patterns, or errors, search again.
  Don't only search at the beginning — search whenever you hit something you might have seen before.
- **Before expensive work**: always search before launching an Explore agent, doing
  multi-file Grep/Glob sweeps, or calling WebSearch/WebFetch. A prior session may have
  already answered the question — skip the work if it has.
- Use `memory_recall` to combine search + read in one call (fewer round trips).
  Use `memory_search` + `memory_read` when you need finer control.

### When to Store
- **After diagnosing a root cause**: any time you explain *why* something doesn't work,
  that explanation is a memory. "The problem was X because Y" is always worth storing.
- **When you discover a gotcha or workaround**: non-obvious behavior, API quirks,
  config footguns — things that would cost a future session time to rediscover.
- **After codebase exploration**: when you map out how a module, feature, or subsystem works,
  store the finding. Frame it as the question a future session would ask
  (e.g., "Auth module: JWT flow through middleware → handler → token_store").
- **After web research**: when a WebSearch/WebFetch answers a question, store the
  *actionable conclusion* — not the URL. URLs rot; the insight doesn't.
- **After a user correction**: if the user says "we don't do X here, use Y", store it
  immediately — it prevents the same wrong suggestion in every future session.
- **After every git commit**: store memories for novel decisions, patterns, or architecture
  introduced in that commit. The commit is a natural breakpoint — don't skip it.
- **Don't batch**: store as you go, not at the end. Mid-task insights are the most valuable
  and the easiest to forget.

### Storage Rules
- Title (max 150 chars): Must be a complete thought, not a label. Another instance of you
  should judge relevance from the title alone.
- Content (max 1500 chars): One insight per memory. Split larger ideas into multiple memories.
- Prefer creating NEW memories over updating existing ones unless refining the same idea.

### Do NOT
- Accumulate knowledge in this file or in auto-memory files.
- Fetch all search results — be selective (usually 1-5).
- Delegate memory_store to a subagent.
```

## Usage

### MCP Tools (used by Claude)

| Tool | Purpose |
|---|---|
| `memory_search` | Semantic search, returns titles only |
| `memory_read` | Fetch full content of a memory |
| `memory_recall` | Search + read top results in one call (fewer round trips) |
| `memory_store` | Store a new memory (with dedup check) |
| `memory_update` | Create a new version of a memory |
| `memory_delete` | Soft-delete (rate-limited, reversible) |
| `memory_undelete` | Restore a deleted memory |
| `memory_history` | View all versions of a memory |
| `memory_timeline` | Browse chronologically with pagination |
| `memory_related` | Find semantically similar memories (dynamic nearest-neighbor) |
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
by age (blue = recent, gold = older). Similarity edges connect semantically related
memories via dynamic nearest-neighbor lookup.

```bash
uv sync --extra visualizer
uv run claude-crowed visualize
```

The frontend is built automatically on launch if `visualizer/dist/` is missing or
stale (requires npm). It skips the build if the dist is already up to date.

Features:
- Force-directed graph with age coloring and similarity-based clustering
- Labels appear progressively as you zoom in
- Semantic search (press `/` to focus)
- Click any node to browse its content and metadata
- Delete/restore memories from the detail panel

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
