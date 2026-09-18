"""Contract tests for the ch08 flowchart navigation page."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")

PROJECT_ROOT = Path(r"D:\AI_Project\What_Want")
CONFIG_DIR = PROJECT_ROOT / "llm_prompt_design" / "config" / "chapters"


def load_config(chapter_id):
    return json.loads((CONFIG_DIR / f"chapter_config_{chapter_id}.json").read_text(encoding="utf-8"))


def _make_app(tmp_path, monkeypatch):
    from importlib import reload
    import app.config
    import app.db
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with app.db.get_conn() as conn:
        for chapter_id in ("ch04", "ch05", "ch06", "ch07", "ch08"):
            conn.execute(
                """INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at)
                   VALUES (?, 1, ?, 1, datetime('now'))""",
                (chapter_id, json.dumps(load_config(chapter_id), ensure_ascii=False)),
            )
        upstream_steps = {
            "ch04": ["step-1", "step-2", "step-3", "step-4", "step-5"],
            "ch05": ["step-1", "step-2"],
            "ch06": ["step-1", "step-2"],
            "ch07": ["step-1", "step-2"],
        }
        for chapter_id, steps in upstream_steps.items():
            for step_id in steps:
                conn.execute(
                    """INSERT INTO step_runs (chapter_id, step_id, status, stale, user_answers, role_id, rendered_prompt, llm_response, created_at)
                       VALUES (?, ?, 'submitted', 0, '{}', 'career_counselor', '', '', datetime('now'))""",
                    (chapter_id, step_id),
                )
        conn.execute(
            """INSERT INTO learner_profiles (user_id, profile_json, updated_at)
               VALUES ('local', ?, datetime('now'))""",
            (json.dumps({
                "work_purpose": "help people find direction",
                "values": ["growth"],
                "talents": [{"text": "empathy"}],
                "likes": [{"field": "psychology"}],
                "ideal_works": [{"title": "coach"}],
            }, ensure_ascii=False),),
        )
    import app.main as main_mod
    reload(main_mod)
    return main_mod.app


def test_flowchart_state_table_and_schema():
    import sqlite3
    import app.db
    with app.db.get_conn() as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(flowchart_state)")]
    assert {"user_id", "chapter_id", "decision_point_id", "selected_branch", "comment_text"} <= set(cols)


@pytest.mark.asyncio
async def test_flowchart_state_roundtrip_and_current_point(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    app_obj = _make_app(tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        initial = await client.get("/api/book/chapters/ch08/flowchart-state")
        assert initial.status_code == 200
        body = initial.json()
        assert body["current_point_id"] == "dp-1"
        assert body["upstream"]["ch04"]["completed"] is True
        assert body["upstream"]["ch07"]["completed"] is True

        saved = await client.put(
            "/api/book/chapters/ch08/flowchart-state",
            json={"decision_point_id": "dp-1", "selected_branch": "是", "comment_text": "价值观已明确"},
        )
        assert saved.status_code == 200, saved.text

        saved2 = await client.put(
            "/api/book/chapters/ch08/flowchart-state",
            json={"decision_point_id": "dp-2", "selected_branch": "是", "comment_text": ""},
        )
        assert saved2.status_code == 200

        reloaded = (await client.get("/api/book/chapters/ch08/flowchart-state")).json()
        assert reloaded["current_point_id"] == "dp-3"
        by_id = {row["decision_point_id"]: row for row in reloaded["states"]}
        assert by_id["dp-1"]["comment_text"] == "价值观已明确"
        assert by_id["dp-1"]["selected_branch"] == "是"

        bad = await client.put(
            "/api/book/chapters/ch08/flowchart-state",
            json={"decision_point_id": "dp-1", "selected_branch": "不存在的分支"},
        )
        assert bad.status_code == 422
        bad_dp = await client.put(
            "/api/book/chapters/ch08/flowchart-state",
            json={"decision_point_id": "dp-99", "selected_branch": "是"},
        )
        assert bad_dp.status_code == 422

        # profile must not be touched by flowchart state writes
        import app.db
        with app.db.get_conn() as conn:
            profile = json.loads(conn.execute(
                "SELECT profile_json FROM learner_profiles WHERE user_id='local'"
            ).fetchone()["profile_json"])
        assert profile.get("ideal_works") == [{"title": "coach"}]
        assert "flowchart" not in profile


@pytest.mark.asyncio
async def test_flowchart_state_current_stops_at_jump_branch(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    app_obj = _make_app(tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        await client.put(
            "/api/book/chapters/ch08/flowchart-state",
            json={"decision_point_id": "dp-1", "selected_branch": "否"},
        )
        reloaded = (await client.get("/api/book/chapters/ch08/flowchart-state")).json()
        assert reloaded["current_point_id"] == "dp-1"


def test_ch08_config_is_flowchart_page():
    cfg = load_config("ch08")
    assert cfg.get("page_type") == "flowchart"
    assert "exercises" not in cfg
    points = []
    for stage in cfg["flowchart"]["stages"]:
        points.extend(decision["id"] for decision in stage["decision_points"])
    assert points == ["dp-1", "dp-2", "dp-3", "dp-4", "dp-refine", "dp-5"]
    assert cfg["flowchart"]["terminal"]["id"] == "end"
