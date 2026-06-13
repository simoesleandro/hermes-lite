import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import services.backup as backup_mod
from services.backup import run_backup


def test_run_backup_creates_db_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_ENABLED", "1")
    monkeypatch.setattr(backup_mod, "BACKUPS_DIR", tmp_path / "backups")
    monkeypatch.setattr(backup_mod, "EXPORTS_DIR", tmp_path / "exports")

    db_src = tmp_path / "hermes.db"
    db_src.write_bytes(b"sqlite-test")
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "note.md").write_text("# test", encoding="utf-8")

    result = run_backup(db_src)
    assert result.get("db_path")
    assert os.path.isfile(result["db_path"])
    assert result.get("exports_zip")
    with zipfile.ZipFile(result["exports_zip"]) as zf:
        names = zf.namelist()
    assert any("note.md" in n for n in names)


def test_run_backup_skipped(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKUP_ENABLED", "0")
    result = run_backup(tmp_path / "missing.db")
    assert result.get("skipped")
