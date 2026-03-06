import sqlite3
from pathlib import Path

from claude_crowed.config import BACKUP_DIR, MAX_BACKUP_COUNT
from claude_crowed.memory_store import now_utc


def create_backup(
    db_path: Path,
    backup_dir: Path = BACKUP_DIR,
    max_backups: int = MAX_BACKUP_COUNT,
) -> Path:
    """Create a backup of the database. Returns the backup path."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now_utc().replace(":", "").replace("-", "").replace(".", "")
    backup_path = backup_dir / f"memories-backup-{timestamp}.db"

    source = sqlite3.connect(str(db_path))
    dest = sqlite3.connect(str(backup_path))
    source.backup(dest)
    dest.close()
    source.close()

    # Prune old backups
    backups = sorted(backup_dir.glob("memories-backup-*.db"))
    while len(backups) > max_backups:
        backups.pop(0).unlink()

    return backup_path


def restore_backup(
    backup_path: Path,
    db_path: Path,
    backup_dir: Path = BACKUP_DIR,
) -> Path:
    """Restore a backup, first backing up the current DB. Returns the safety backup path."""
    # Safety backup of current DB
    safety_backup = create_backup(db_path, backup_dir)

    # Copy backup over current DB
    source = sqlite3.connect(str(backup_path))
    dest = sqlite3.connect(str(db_path))
    source.backup(dest)
    dest.close()
    source.close()

    return safety_backup
