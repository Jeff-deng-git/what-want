"""Tests for check_config_consistency.py (DB vs JSON drift detector).

Ref doc: llm_prompt_design/docs/重构开放问题_设计侧确认.md 附2:
  "DB vs JSON 一致性脚本: 报警漂移（防 ch04 类问题复发）".
"""
import importlib.util
import json
import os
import sys

import pytest


PROJECT_ROOT = r"D:\AI_Project\What_Want"
BACKEND_ROOT = os.path.join(PROJECT_ROOT, "platform", "backend")
SCRIPT_PATH = os.path.join(BACKEND_ROOT, "scripts", "check_config_consistency.py")
JSON_DIR = os.path.join(PROJECT_ROOT, "llm_prompt_design", "config", "chapters")
CHAPTERS = ["ch01", "ch02", "ch03", "ch04", "ch05", "ch06", "ch07", "ch08"]


def _load_module():
    spec = importlib.util.spec_from_file_location("check_config_consistency", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_main(mod, argv):
    saved = sys.argv
    sys.argv = argv
    try:
        return mod.main()
    finally:
        sys.argv = saved


def _init_db(db_path):
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE chapter_configs ("
        "  chapter_id TEXT NOT NULL,"
        "  version INTEGER NOT NULL,"
        "  config_json TEXT NOT NULL,"
        "  active INTEGER DEFAULT 1,"
        "  created_at TIMESTAMP DEFAULT (datetime('now')),"
        "  PRIMARY KEY (chapter_id, version)"
        ")"
    )
    conn.commit()
    conn.close()


def _seed_chapters(db_path, chapters_to_seed, overrides=None):
    """Load each chapter JSON, optionally apply overrides[name]=mutator, then insert v1 active."""
    import sqlite3
    overrides = overrides or {}
    conn = sqlite3.connect(str(db_path))
    for ch in chapters_to_seed:
        path = os.path.join(JSON_DIR, "chapter_config_" + ch + ".json")
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if ch in overrides:
            cfg = overrides[ch](cfg)
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active) VALUES (?, ?, ?, 1)",
            (ch, 1, json.dumps(cfg, ensure_ascii=False)),
        )
    conn.commit()
    conn.close()


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    db_path = tmp_path / "ww.db"
    _init_db(db_path)
    _seed_chapters(db_path, CHAPTERS)
    monkeypatch.setenv("WW_DB_PATH", str(db_path))
    yield db_path


def test_clean_state_exits_zero(seeded_db, capsys):
    mod = _load_module()
    rc = _run_main(mod, ["check_config_consistency"])
    out = capsys.readouterr().out
    assert rc == 0, "expected clean state rc=0, got " + str(rc) + "\n" + out
    assert "CLEAN" in out
    assert "[DRIFT]" not in out


def test_drifts_when_exercises_count_differs(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "ww.db"
    _init_db(db_path)
    # Simulate ch04 migration bug: only 1 exercise in DB instead of 5 in file.
    _seed_chapters(
        db_path,
        CHAPTERS,
        overrides={"ch04": lambda c: {**c, "exercises": c["exercises"][:1]}},
    )
    monkeypatch.setenv("WW_DB_PATH", str(db_path))
    mod = _load_module()
    rc = _run_main(mod, ["check_config_consistency"])
    out = capsys.readouterr().out
    assert rc == 1, "expected drift rc=1, got " + str(rc) + "\n" + out
    assert "[DRIFT] ch04" in out


def test_detects_missing_db_row(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "ww.db"
    _init_db(db_path)
    _seed_chapters(db_path, [c for c in CHAPTERS if c != "ch04"])
    monkeypatch.setenv("WW_DB_PATH", str(db_path))
    mod = _load_module()
    rc = _run_main(mod, ["check_config_consistency"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[DB-MISS] ch04" in out


def test_single_chapter_mode(seeded_db, capsys):
    mod = _load_module()
    rc = _run_main(mod, ["check_config_consistency", "--chapter", "ch04"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[OK] ch04" in out
    assert "[OK] ch01" not in out
    assert "[OK] ch08" not in out
