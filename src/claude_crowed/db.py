import sqlite3
from pathlib import Path

import sqlite_vec

from claude_crowed.config import DB_DIR, DB_PATH, EMBEDDING_DIMENSION

SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    version INTEGER NOT NULL DEFAULT 1,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_accessed_at TEXT NOT NULL,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    parent_id TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    FOREIGN KEY (parent_id) REFERENCES memories(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings USING vec0(
    id TEXT PRIMARY KEY,
    embedding float[{EMBEDDING_DIMENSION}]
);

CREATE TABLE IF NOT EXISTS memory_links (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id),
    FOREIGN KEY (source_id) REFERENCES memories(id),
    FOREIGN KEY (target_id) REFERENCES memories(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at);
CREATE INDEX IF NOT EXISTS idx_memories_deleted ON memories(is_deleted);
CREATE INDEX IF NOT EXISTS idx_memories_parent ON memories(parent_id);
CREATE INDEX IF NOT EXISTS idx_links_source ON memory_links(source_id);
CREATE INDEX IF NOT EXISTS idx_links_target ON memory_links(target_id);
"""


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Create a new SQLite connection with sqlite-vec loaded."""
    if db_path is None:
        db_path = DB_PATH
    db_path = Path(db_path)

    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_schema(db: sqlite3.Connection) -> None:
    """Initialize the database schema. Idempotent."""
    db.executescript(SCHEMA_SQL)
    db.commit()
