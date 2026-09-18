"""Shared test fixtures: fresh tmp DB + httpx ASGI client."""
import os
import sys
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from importlib import reload

import app.config  # noqa: F401
import app.db
import app.main as _app_main


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    reload(app.config)
    reload(app.db)
    reload(_app_main)
    app.db.init_db()
    transport = ASGITransport(app=_app_main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
