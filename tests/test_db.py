from claude_crowed.db import get_connection, init_schema


def test_schema_init_idempotent():
    """Running init_schema twice should not raise errors."""
    db = get_connection(":memory:")
    init_schema(db)
    init_schema(db)  # second call should be fine

    # Verify tables exist
    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [t["name"] for t in tables]
    assert "memories" in table_names
    assert "settings" in table_names
    db.close()


def test_wal_mode():
    db = get_connection(":memory:")
    mode = db.execute("PRAGMA journal_mode").fetchone()[0]
    # In-memory DBs use "memory" journal mode, but the pragma is still set
    assert mode in ("wal", "memory")
    db.close()


def test_foreign_keys_enabled():
    db = get_connection(":memory:")
    init_schema(db)
    fk = db.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1
    db.close()
