"""Tests for agent_configs seed script (ADR-001).

Ref doc: llm_prompt_design/docs/重构开放问题_设计侧确认.md 附2:
  agent_configs 表 seed 与迁移 (llm_roles 只存 provider/model + 核心 prompt,
  agent_configs 存全局 mentor/summary 脚手架).
"""
import importlib.util
import json
import os
import sys

import pytest


PROJECT_ROOT = r"D:\AI_Project\What_Want"
BACKEND_ROOT = os.path.join(PROJECT_ROOT, "platform", "backend")
SCRIPT_PATH = os.path.join(BACKEND_ROOT, "scripts", "seed_agent_configs.py")
LLM_CONFIG_ROOT = os.path.join(PROJECT_ROOT, "llm_prompt_design", "config")

EXPECTED_CONFIGS = {
    "mentor": os.path.join(LLM_CONFIG_ROOT, "mentor", "mentor_config.json"),
    "summary": os.path.join(LLM_CONFIG_ROOT, "agents", "summary_config.json"),
}


def _load_seed_module():
    if BACKEND_ROOT not in sys.path:
        sys.path.insert(0, BACKEND_ROOT)
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    spec = importlib.util.spec_from_file_location("seed_agent_configs", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def seed_mod():
    return _load_seed_module()


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "ww.db"
    monkeypatch.setenv("WW_DB_PATH", str(db_path))
    import app.config  # noqa: E402
    import app.db  # noqa: E402
    import importlib
    importlib.reload(app.config)
    importlib.reload(app.db)
    app.db.init_db()
    yield db_path


def _agent_configs_columns(db_path):
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("PRAGMA table_info(agent_configs)").fetchall()
    conn.close()
    return [r[1] for r in rows]


def test_agent_configs_table_present(tmp_db):
    cols = _agent_configs_columns(tmp_db)
    assert cols, "agent_configs table missing - init_db did not run or schema regressed"
    for required in ("name", "config_json", "updated_at"):
        assert required in cols, "agent_configs missing column: " + required


def test_seed_agent_configs_creates_rows(tmp_db, seed_mod, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_db))
    seed_mod.main()
    import sqlite3
    conn = sqlite3.connect(str(tmp_db))
    rows = conn.execute("SELECT name FROM agent_configs ORDER BY name").fetchall()
    names = [r[0] for r in rows]
    assert "mentor" in names and "summary" in names, names


def test_seed_is_idempotent(tmp_db, seed_mod, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_db))
    for _ in range(2):
        seed_mod.main()
    import sqlite3
    conn = sqlite3.connect(str(tmp_db))
    count = conn.execute("SELECT COUNT(*) FROM agent_configs").fetchone()[0]
    assert count == 2, "expected 2 rows after 2 seed runs, got " + str(count)


@pytest.mark.parametrize("name", list(EXPECTED_CONFIGS.keys()))
def test_seeded_config_round_trips(name, tmp_db, seed_mod, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_db))
    seed_mod.main()
    import sqlite3
    conn = sqlite3.connect(str(tmp_db))
    row = conn.execute(
        "SELECT config_json FROM agent_configs WHERE name = ?", (name,)
    ).fetchone()
    assert row is not None, "agent_configs row missing: " + name
    seeded = json.loads(row[0])
    with open(EXPECTED_CONFIGS[name], "r", encoding="utf-8") as f:
        source = json.load(f)
    assert seeded == source, name + ": DB config_json != source file"
