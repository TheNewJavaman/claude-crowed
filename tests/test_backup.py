import tempfile
from pathlib import Path

import pytest

from claude_crowed.backup import create_backup
from claude_crowed.db import get_connection, init_schema


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test.db"
    db = get_connection(db_path)
    init_schema(db)
    db.execute(
        "INSERT INTO memories (id, version, title, content, created_at, updated_at, source) "
        "VALUES ('test-1', 1, 'Test', 'Content', '2025-01-01T00:00:00Z', '2025-01-01T00:00:00Z', 'manual')"
    )
    db.commit()
    db.close()
    return db_path


def test_create_backup(tmp_db, tmp_path):
    backup_dir = tmp_path / "backups"
    backup_path = create_backup(tmp_db, backup_dir)
    assert backup_path.exists()
    assert backup_path.stat().st_size > 0


def test_backup_contains_data(tmp_db, tmp_path):
    backup_dir = tmp_path / "backups"
    backup_path = create_backup(tmp_db, backup_dir)

    db = get_connection(backup_path)
    row = db.execute("SELECT title FROM memories WHERE id = 'test-1'").fetchone()
    assert row["title"] == "Test"
    db.close()


def test_backup_pruning(tmp_db, tmp_path):
    backup_dir = tmp_path / "backups"

    # Create more than max_backups
    paths = []
    for i in range(5):
        p = create_backup(tmp_db, backup_dir, max_backups=3)
        paths.append(p)

    backups = list(backup_dir.glob("memories-backup-*.db"))
    assert len(backups) == 3
