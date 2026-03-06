import argparse
import json
import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from claude_crowed.backup import create_backup, restore_backup
from claude_crowed.config import (
    BACKUP_DIR,
    DB_PATH,
    DEFAULT_SEARCH_K,
    DEFAULT_TIMELINE_K,
    EXPORT_DIR,
)
from claude_crowed.db import get_connection, init_schema
from claude_crowed.embedding import default_embed_fn, embed_document, embed_query, start_loading
from claude_crowed.memory_store import MemoryStore, now_utc, rebuild_embeddings
from claude_crowed.models import ExportData

logger = logging.getLogger("claude-crowed")

mcp = FastMCP("claude-crowed")

_store: MemoryStore | None = None


def _get_store() -> MemoryStore:
    global _store
    if _store is None:
        db = get_connection()
        init_schema(db)
        _store = MemoryStore(db, embed_document, embed_query)
    return _store


def _init_server() -> None:
    """Initialize DB, create backup, set up store."""
    start_loading()  # Begin model loading in background immediately
    db = get_connection()
    init_schema(db)

    # Create startup backup if DB exists
    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        try:
            create_backup(DB_PATH)
            logger.info("Startup backup created")
        except Exception:
            logger.warning("Failed to create startup backup", exc_info=True)

    global _store
    _store = MemoryStore(db, embed_document, embed_query)


# --- MCP Tools ---


@mcp.tool()
def memory_search(
    query: str,
    k: int = DEFAULT_SEARCH_K,
    include_deleted: bool = False,
) -> list[dict] | dict:
    """Search your persistent memory. Call this at the START of every task with relevant
    keywords. Returns titles and metadata only -- use memory_read to fetch full content
    of the few results that look relevant (usually 1-5). Do not skip this step."""
    try:
        store = _get_store()
        results = store.search(query, k=k, include_deleted=include_deleted)
        return [r.model_dump() for r in results]
    except Exception as e:
        logger.error("memory_search failed", exc_info=True)
        return {"error": f"Search failed: {e}"}


@mcp.tool()
def memory_read(id: str) -> dict:
    """Fetch the full content of a specific memory. This is the only tool that returns
    content and the only tool that bumps last_accessed_at."""
    try:
        store = _get_store()
        result = store.read(id)
        if isinstance(result, dict):
            return result
        return result.model_dump()
    except Exception as e:
        logger.error("memory_read failed", exc_info=True)
        return {"error": f"Read failed: {e}"}


@mcp.tool()
def memory_store(
    title: str,
    content: str,
    source: str = "manual",
    force: bool = False,
) -> dict:
    """Store a new memory. Call this whenever you learn something worth remembering across
    sessions -- novel insights, decisions, findings, patterns, or debugging solutions.
    Title (max 150 chars) must be a complete, descriptive thought, not a label. Another
    instance of you should judge relevance from the title alone. Content max 1500 chars;
    split larger ideas into multiple linked memories. Source: manual, conversation, or auto.

    Rejects near-duplicates by default (use memory_threshold to view/adjust sensitivity).
    Set force=True to skip the duplicate check entirely."""
    try:
        store = _get_store()
        result = store.store(title=title, content=content, source=source, force=force)
        if isinstance(result, dict):
            return result
        return {"id": result}
    except Exception as e:
        logger.error("memory_store failed", exc_info=True)
        return {"error": f"Store failed: {e}"}


@mcp.tool()
def memory_update(
    id: str,
    title: str | None = None,
    content: str | None = None,
) -> dict:
    """Update an existing memory, creating a new version. The old version is preserved
    but removed from the search index. Returns the new version's ID."""
    try:
        store = _get_store()
        result = store.update(id, title=title, content=content)
        if isinstance(result, dict):
            return result
        return {"id": result}
    except Exception as e:
        logger.error("memory_update failed", exc_info=True)
        return {"error": f"Update failed: {e}"}


@mcp.tool()
def memory_delete(id: str) -> dict:
    """Soft-delete a memory. Always confirm with the user before deleting.
    Deletions are reversible with memory_undelete, but limited to 5 per session
    as a safety measure."""
    try:
        store = _get_store()
        return store.delete(id)
    except Exception as e:
        logger.error("memory_delete failed", exc_info=True)
        return {"error": f"Delete failed: {e}"}


@mcp.tool()
def memory_undelete(id: str) -> dict:
    """Restore a soft-deleted memory."""
    try:
        store = _get_store()
        return store.undelete(id)
    except Exception as e:
        logger.error("memory_undelete failed", exc_info=True)
        return {"error": f"Undelete failed: {e}"}


@mcp.tool()
def memory_history(id: str) -> list[dict] | dict:
    """Retrieve all versions of a logical memory. Pass any version ID in the chain."""
    try:
        store = _get_store()
        result = store.history(id)
        if isinstance(result, dict):
            return result
        return [v.model_dump() for v in result]
    except Exception as e:
        logger.error("memory_history failed", exc_info=True)
        return {"error": f"History failed: {e}"}


@mcp.tool()
def memory_timeline(
    k: int = DEFAULT_TIMELINE_K,
    cursor: str | None = None,
    before: str | None = None,
    after: str | None = None,
    include_deleted: bool = False,
) -> dict:
    """Browse memories chronologically with cursor-based pagination.
    Returns titles and metadata only."""
    try:
        store = _get_store()
        result = store.timeline(
            k=k, cursor=cursor, before=before, after=after, include_deleted=include_deleted
        )
        return result.model_dump()
    except Exception as e:
        logger.error("memory_timeline failed", exc_info=True)
        return {"error": f"Timeline failed: {e}"}


@mcp.tool()
def memory_link(id_a: str, id_b: str) -> dict:
    """Create a bidirectional 'see also' link between two memories."""
    try:
        store = _get_store()
        return store.link(id_a, id_b)
    except Exception as e:
        logger.error("memory_link failed", exc_info=True)
        return {"error": f"Link failed: {e}"}


@mcp.tool()
def memory_unlink(id_a: str, id_b: str) -> dict:
    """Remove a bidirectional link between two memories."""
    try:
        store = _get_store()
        return store.unlink(id_a, id_b)
    except Exception as e:
        logger.error("memory_unlink failed", exc_info=True)
        return {"error": f"Unlink failed: {e}"}


@mcp.tool()
def memory_related(id: str) -> list[dict] | dict:
    """List all memories linked to a given memory. Returns titles only."""
    try:
        store = _get_store()
        result = store.related(id)
        if isinstance(result, dict):
            return result
        return [r.model_dump() for r in result]
    except Exception as e:
        logger.error("memory_related failed", exc_info=True)
        return {"error": f"Related failed: {e}"}


@mcp.tool()
def memory_export(path: str | None = None) -> dict:
    """Export all memories (including deleted, all versions) to a JSON file."""
    try:
        store = _get_store()
        data = store.export_all()

        if path is None:
            EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = now_utc().replace(":", "").replace("-", "")
            export_path = EXPORT_DIR / f"crowed-export-{timestamp}.json"
        else:
            export_path = Path(path)
            export_path.parent.mkdir(parents=True, exist_ok=True)

        export_path.write_text(data.model_dump_json(indent=2))

        return {
            "path": str(export_path),
            "memory_count": len(data.memories),
            "link_count": len(data.links),
        }
    except Exception as e:
        logger.error("memory_export failed", exc_info=True)
        return {"error": f"Export failed: {e}"}


@mcp.tool()
def memory_import(path: str, overwrite: bool = False) -> dict:
    """Import memories from a JSON export file. Set overwrite=True to clear the database
    first (a backup will be created automatically)."""
    try:
        store = _get_store()
        file_path = Path(path)
        if not file_path.exists():
            return {"error": f"File not found: {path}"}

        raw = json.loads(file_path.read_text())
        data = ExportData(**raw)

        if overwrite and DB_PATH.exists():
            create_backup(DB_PATH)

        return store.import_data(data, overwrite=overwrite)
    except Exception as e:
        logger.error("memory_import failed", exc_info=True)
        return {"error": f"Import failed: {e}"}


@mcp.tool()
def memory_migrate(path: str | None = None) -> dict:
    """Discover and read memory files (CLAUDE.md, auto-memory) for migration into crowed.

    Returns file sections split by markdown headers. Review each section and decide
    whether it contains KNOWLEDGE (store with memory_store) or INSTRUCTIONS (skip).

    - With no path: discovers all migratable files (~/.claude/CLAUDE.md and auto-memory)
      and returns their sections.
    - With a path: reads and splits that specific file.

    This tool does NOT store anything. You review the sections and call memory_store
    for each piece of knowledge you want to keep. Skip pure instructions."""
    try:
        from claude_crowed.migrate import discover_memory_files, read_and_split_file

        if path is not None:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return {"error": f"File not found: {path}"}
            return read_and_split_file(file_path)

        files = discover_memory_files()
        if not files:
            return {"files": [], "message": "No memory files found to migrate."}

        results = []
        for f in files:
            results.append(read_and_split_file(f))
        return {"files": results}
    except Exception as e:
        logger.error("memory_migrate failed", exc_info=True)
        return {"error": f"Migration scan failed: {e}"}


@mcp.tool()
def memory_threshold(value: float | None = None) -> dict:
    """Get or adjust the duplicate similarity threshold used by memory_store.

    Call with no arguments to see the current threshold. Pass a value (0.0-1.0)
    to update it. Higher values are more permissive (only very similar content
    is blocked); lower values are stricter.

    Adjust this when you notice false positives (distinct memories being blocked)
    or false negatives (duplicates getting through). Small increments (0.02-0.05)
    are recommended."""
    try:
        store = _get_store()
        if value is not None:
            return store.set_similarity_threshold(value)
        return {"similarity_threshold": store.get_similarity_threshold()}
    except Exception as e:
        logger.error("memory_threshold failed", exc_info=True)
        return {"error": f"Threshold failed: {e}"}


@mcp.tool()
def memory_stats() -> dict:
    """Return summary statistics about the memory store."""
    try:
        store = _get_store()
        stats = store.stats()
        if DB_PATH.exists():
            stats.db_size_bytes = DB_PATH.stat().st_size
        return stats.model_dump()
    except Exception as e:
        logger.error("memory_stats failed", exc_info=True)
        return {"error": f"Stats failed: {e}"}


# --- CLI ---


def cli_serve(transport: str = "stdio"):
    """Start the MCP server."""
    _init_server()
    mcp.run(transport=transport)


def cli_export(args):
    output = args.output
    store = _get_store()
    data = store.export_all()

    if output is None:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = now_utc().replace(":", "").replace("-", "")
        output = str(EXPORT_DIR / f"crowed-export-{timestamp}.json")

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(data.model_dump_json(indent=2))
    print(f"Exported {len(data.memories)} memories, {len(data.links)} links to {output}")


def cli_import(args):
    store = _get_store()
    file_path = Path(args.path)
    if not file_path.exists():
        print(f"File not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(file_path.read_text())
    data = ExportData(**raw)

    if args.overwrite and DB_PATH.exists():
        create_backup(DB_PATH)

    result = store.import_data(data, overwrite=args.overwrite)
    print(
        f"Imported {result['imported_memories']} memories, "
        f"{result['imported_links']} links, "
        f"skipped {result['skipped']}"
    )


def cli_restore(args):
    backup_path = Path(args.path)
    if not backup_path.exists():
        print(f"Backup not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    safety = restore_backup(backup_path, DB_PATH)
    print(f"Restored from {backup_path}")
    print(f"Safety backup of previous DB: {safety}")

    # Rebuild embeddings
    db = get_connection()
    init_schema(db)
    count = rebuild_embeddings(db, default_embed_fn)
    print(f"Rebuilt embeddings for {count} memories")


def cli_rebuild_embeddings():
    db = get_connection()
    init_schema(db)
    count = rebuild_embeddings(db, default_embed_fn)
    print(f"Rebuilt embeddings for {count} memories")


def cli_stats():
    store = _get_store()
    stats = store.stats()
    if DB_PATH.exists():
        stats.db_size_bytes = DB_PATH.stat().st_size

    print(f"Active memories:  {stats.total_memories}")
    print(f"Deleted memories: {stats.total_deleted}")
    print(f"Total versions:   {stats.total_versions}")
    print(f"Total links:      {stats.total_links}")
    print(f"Oldest memory:    {stats.oldest_memory or '(none)'}")
    print(f"Newest memory:    {stats.newest_memory or '(none)'}")
    print(f"Database size:    {stats.db_size_bytes:,} bytes")


def main():
    parser = argparse.ArgumentParser(
        prog="claude-crowed",
        description="Persistent semantic memory system for Claude Code",
    )
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Start the MCP server")
    serve_parser.add_argument(
        "--transport", choices=["stdio", "sse"], default="stdio",
        help="Transport protocol (default: stdio, use sse for development with hot-reload)"
    )

    # export
    export_parser = subparsers.add_parser("export", help="Export memories")
    export_parser.add_argument("--output", default=None)

    # import
    import_parser = subparsers.add_parser("import", help="Import memories")
    import_parser.add_argument("path")
    import_parser.add_argument("--overwrite", action="store_true")

    # restore
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument("path")

    # dev
    subparsers.add_parser("dev", help="Start MCP server via reload proxy (auto-restarts on git commits)")

    # rebuild-embeddings
    subparsers.add_parser("rebuild-embeddings", help="Rebuild embedding index")

    # stats
    subparsers.add_parser("stats", help="Show memory statistics")

    args = parser.parse_args()

    if args.command is None:
        cli_serve()
    elif args.command == "serve":
        cli_serve(transport=args.transport)
    elif args.command == "dev":
        from claude_crowed.proxy import run_dev
        run_dev()
    elif args.command == "export":
        cli_export(args)
    elif args.command == "import":
        cli_import(args)
    elif args.command == "restore":
        cli_restore(args)
    elif args.command == "rebuild-embeddings":
        cli_rebuild_embeddings()
    elif args.command == "stats":
        cli_stats()


if __name__ == "__main__":
    main()
