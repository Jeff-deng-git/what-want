"""Regression tests for synchronising LLM role runtime settings."""
import importlib
import importlib.util
import os
import sqlite3
import sys

import pytest


BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(BACKEND_ROOT, "scripts", "seed_roles.py")


def _load_seed_roles_module():
    module_name = "seed_roles_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "ww.db"
    monkeypatch.setenv("WW_DB_PATH", str(db_path))
    import app.config
    import app.db

    importlib.reload(app.config)
    importlib.reload(app.db)
    app.db.init_db()
    return db_path


def test_seed_roles_refreshes_existing_runtime_token_budget(tmp_db, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_db))
    seed_roles = _load_seed_roles_module()
    seed_roles.main()

    conn = sqlite3.connect(str(tmp_db))
    conn.execute(
        "UPDATE llm_roles SET max_tokens = 1500 WHERE name IN ('psychologist', 'career_counselor')"
    )
    conn.commit()
    conn.close()

    seed_roles.main()

    conn = sqlite3.connect(str(tmp_db))
    rows = conn.execute(
        "SELECT name, max_tokens FROM llm_roles WHERE name IN ('psychologist', 'career_counselor')"
    ).fetchall()
    conn.close()

    assert dict(rows) == {"psychologist": 4000, "career_counselor": 4000}
