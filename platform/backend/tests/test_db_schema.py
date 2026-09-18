"""Schema regression tests — cover Task 1 changes.

Two invariants we must keep:
1. chapter_configs supports multiple versions per chapter (composite PK).
2. step_runs has an `error` column for parse/runtime failures.
"""
import pytest


def test_chapter_configs_supports_multi_version(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    import importlib, app.config, app.db
    importlib.reload(app.config)
    importlib.reload(app.db)
    app.db.init_db()
    cfg = '{"chapter_id":"x","steps":[]}'
    with app.db.get_conn() as c:
        c.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) "
            "VALUES (?,?,?,1,datetime('now'))",
            ("x", 1, cfg),
        )
        c.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) "
            "VALUES (?,?,?,1,datetime('now'))",
            ("x", 2, cfg),
        )
        c.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) "
            "VALUES (?,?,?,0,datetime('now'))",
            ("x", 3, cfg),
        )
        rows = c.execute(
            "SELECT version, active FROM chapter_configs WHERE chapter_id='x' ORDER BY version"
        ).fetchall()
    assert [(r[0], r[1]) for r in rows] == [(1, 1), (2, 1), (3, 0)]


def test_step_runs_has_error_column(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    import importlib, app.config, app.db
    importlib.reload(app.config)
    importlib.reload(app.db)
    app.db.init_db()
    with app.db.get_conn() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(step_runs)").fetchall()]
    assert "error" in cols


def test_new_phase_c_tables_exist(tmp_path, monkeypatch):
    """Phase C: chapter_summaries, chapter_chat, questions tables exist."""
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    import importlib, app.config, app.db
    importlib.reload(app.config)
    importlib.reload(app.db)
    app.db.init_db()
    with app.db.get_conn() as c:
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"chapter_summaries", "chapter_chat", "questions"} <= tables


def test_m1_profile_tables_exist_with_expected_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    import importlib, app.config, app.db
    importlib.reload(app.config)
    importlib.reload(app.db)
    app.db.init_db()
    with app.db.get_conn() as c:
        tables = {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert {"learner_profiles", "conversation_summaries", "agent_configs"} <= tables
        profile_columns = {r[1] for r in c.execute(
            "PRAGMA table_info(learner_profiles)").fetchall()}
        summary_columns = {r[1] for r in c.execute(
            "PRAGMA table_info(conversation_summaries)").fetchall()}
        agent_columns = {r[1] for r in c.execute(
            "PRAGMA table_info(agent_configs)").fetchall()}
    assert {"user_id", "profile_json", "updated_at"} <= profile_columns
    assert {"user_id", "chapter_id", "summary", "updated_at"} <= summary_columns
    assert {"name", "config_json", "updated_at"} <= agent_columns
