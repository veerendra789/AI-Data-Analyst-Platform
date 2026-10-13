from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.core import supabase as supabase_core
from app.main import app
from app.services import supabase_repository, supabase_storage
from tests.supabase_test_doubles import FakeSupabase


@pytest.fixture(autouse=True)
def supabase_test_services(monkeypatch):
    fake_supabase = FakeSupabase()
    monkeypatch.setattr(supabase_core, "get_supabase_client", lambda: fake_supabase)
    monkeypatch.setattr(supabase_repository, "get_supabase_client", lambda: fake_supabase)
    monkeypatch.setattr(supabase_storage, "get_supabase_client", lambda: fake_supabase)
    app.dependency_overrides.clear()
    yield SimpleNamespace(client=fake_supabase, tables=fake_supabase.tables, objects=fake_supabase.objects)
    app.dependency_overrides.clear()