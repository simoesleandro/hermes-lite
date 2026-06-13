"""Backup local de hermes.db e pasta exports."""

from __future__ import annotations

import logging
import os
import shutil
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("hermes.backup")

_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = _ROOT / "db" / "hermes.db"
BACKUPS_DIR = _ROOT / "backups"
EXPORTS_DIR = _ROOT / "exports"
KEEP_DAYS = int(os.getenv("BACKUP_KEEP_DAYS", "14"))


def _prune_old(backups_dir: Path, keep_days: int) -> int:
    if not backups_dir.is_dir():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    removed = 0
    for path in backups_dir.iterdir():
        if not path.is_file():
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def run_backup(
    db_path: str | Path | None = None,
    *,
    include_exports: bool = True,
) -> dict:
    if os.getenv("BACKUP_ENABLED", "1") != "1":
        return {"skipped": True, "reason": "BACKUP_ENABLED=0"}

    src_db = Path(db_path) if db_path else DEFAULT_DB
    if not src_db.is_file():
        return {"skipped": True, "reason": f"db not found: {src_db}"}

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now().strftime("%Y-%m-%d")
    db_dest = BACKUPS_DIR / f"hermes-{date_tag}.db"
    shutil.copy2(src_db, db_dest)

    exports_zip: str | None = None
    if include_exports and EXPORTS_DIR.is_dir():
        exports_zip = str(BACKUPS_DIR / f"exports-{date_tag}.zip")
        with zipfile.ZipFile(exports_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for fp in EXPORTS_DIR.rglob("*"):
                if fp.is_file():
                    zf.write(fp, fp.relative_to(EXPORTS_DIR.parent))

    removed = _prune_old(BACKUPS_DIR, KEEP_DAYS)
    logger.info("backup → %s (pruned %s old files)", db_dest, removed)

    return {
        "db_path": str(db_dest),
        "exports_zip": exports_zip,
        "pruned": removed,
        "keep_days": KEEP_DAYS,
    }
