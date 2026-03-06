"""Web visualizer backend for claude-crowed memory database."""

import sqlite3
import threading
import webbrowser
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import sqlite_vec

from claude_crowed.config import DB_PATH
from claude_crowed.db import init_schema
from claude_crowed.embedding import embed_document, embed_query, start_loading
from claude_crowed.memory_store import MemoryStore

app = FastAPI(title="crowed-visualizer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_store: MemoryStore | None = None


def _get_connection() -> sqlite3.Connection:
    """Create a thread-safe SQLite connection for use with FastAPI's threadpool."""
    db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def _get_store() -> MemoryStore:
    global _store
    if _store is None:
        db = _get_connection()
        init_schema(db)
        _store = MemoryStore(db, embed_document, embed_query)
    return _store


@app.get("/api/graph")
def get_graph(similarity_k: int = 3, min_similarity: float = 0.25):
    store = _get_store()
    db = store.db

    # All active memories (latest versions, not deleted)
    memories = db.execute(
        """
        SELECT m.id, m.title, m.created_at, m.updated_at, m.source
        FROM memories m
        WHERE m.is_deleted = 0
          AND m.id NOT IN (SELECT parent_id FROM memories WHERE parent_id IS NOT NULL)
        """
    ).fetchall()

    nodes = [
        {
            "id": m["id"],
            "title": m["title"],
            "created_at": m["created_at"],
            "updated_at": m["updated_at"],
            "source": m["source"],
        }
        for m in memories
    ]

    active_ids = {m["id"] for m in memories}

    # Dynamic similarity edges via nearest-neighbor lookup
    links = []
    seen: set[tuple[str, str]] = set()
    for mid in active_ids:
        emb_row = db.execute(
            "SELECT embedding FROM memory_embeddings WHERE id = ?", (mid,)
        ).fetchone()
        if emb_row is None:
            continue
        neighbors = db.execute(
            "SELECT id, distance FROM memory_embeddings WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (emb_row[0], similarity_k + 1),
        ).fetchall()
        for row in neighbors:
            nid = row[0]
            if nid == mid or nid not in active_ids:
                continue
            similarity = 1.0 - row[1]
            if similarity < min_similarity:
                continue
            pair = (min(mid, nid), max(mid, nid))
            if pair not in seen:
                seen.add(pair)
                links.append({"source": mid, "target": nid, "similarity": similarity})

    return {"nodes": nodes, "links": links}


@app.get("/api/memories/{memory_id}")
def get_memory(memory_id: str):
    store = _get_store()
    result = store.read(memory_id)
    if isinstance(result, dict):
        return result
    return result.model_dump()


@app.get("/api/search")
def search_memories(q: str = Query(...), k: int = 20):
    store = _get_store()
    results = store.search(q, k=k)
    return [r.model_dump() for r in results]


@app.post("/api/memories/{memory_id}/delete")
def delete_memory(memory_id: str):
    store = _get_store()
    return store.delete(memory_id)


@app.post("/api/memories/{memory_id}/undelete")
def undelete_memory(memory_id: str):
    store = _get_store()
    return store.undelete(memory_id)


@app.get("/api/stats")
def get_stats():
    store = _get_store()
    stats = store.stats()
    if DB_PATH.exists():
        stats.db_size_bytes = DB_PATH.stat().st_size
    return stats.model_dump()


# Serve built frontend
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "visualizer" / "dist"


@app.on_event("startup")
def _mount_frontend():
    if FRONTEND_DIR.exists():
        app.mount(
            "/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend"
        )


def _build_frontend():
    """Install npm deps and build the frontend if dist/ is missing or stale."""
    import shutil
    import subprocess

    visualizer_dir = Path(__file__).resolve().parent.parent.parent / "visualizer"
    if not visualizer_dir.exists():
        return

    dist = visualizer_dir / "dist"
    src = visualizer_dir / "src"

    # Skip if dist/ exists and is newer than src/
    if dist.exists() and (dist / "index.html").exists():
        dist_mtime = (dist / "index.html").stat().st_mtime
        src_files = list(src.rglob("*")) if src.exists() else []
        if src_files and all(f.stat().st_mtime <= dist_mtime for f in src_files):
            return

    npm = shutil.which("npm")
    if npm is None:
        print("Warning: npm not found, skipping frontend build. Pre-build with: cd visualizer && npm install && npm run build")
        return

    print("Building visualizer frontend...")
    node_modules = visualizer_dir / "node_modules"
    if not node_modules.exists():
        subprocess.run([npm, "install"], cwd=visualizer_dir, check=True)
    # Use vite directly to skip tsc type-checking
    npx = shutil.which("npx")
    subprocess.run([npx or "npx", "vite", "build"], cwd=visualizer_dir, check=True)


def run_visualizer(port: int = 4242, no_browser: bool = False):
    """Start the visualizer web server."""
    import uvicorn

    _build_frontend()
    start_loading()

    if not no_browser:
        threading.Timer(
            1.5, lambda: webbrowser.open(f"http://localhost:{port}")
        ).start()

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
