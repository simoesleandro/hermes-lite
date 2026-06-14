import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.syshealth_client import SysHealthClient, check_syshealth_service


def test_rest_url_from_postgres_connection(monkeypatch):
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_REST_URL", raising=False)
    monkeypatch.setenv(
        "SUPABASE_URL",
        "postgresql://postgres.abc123xyz:secret@host:5432/postgres",
    )
    from services import syshealth_client
    assert syshealth_client._rest_url() == "https://abc123xyz.supabase.co"


def test_supabase_offline_without_keys(monkeypatch):
    monkeypatch.setenv("SYSHEALTH_BACKEND", "supabase")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setenv("SUPABASE_URL", "")
    client = SysHealthClient()
    summary = client.get_health_summary()
    assert summary["offline"] is True


def test_check_syshealth_unconfigured(monkeypatch):
    monkeypatch.setenv("SYSHEALTH_BACKEND", "supabase")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    status = check_syshealth_service()
    assert status["status"] == "offline"
    assert status["backend"] == "supabase"
