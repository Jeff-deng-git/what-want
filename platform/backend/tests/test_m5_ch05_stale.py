"""Contract tests for ch05 step-1 resubmit cascade (option A)."""

import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")

PROJECT_ROOT = Path(r"D:\AI_Project\What_Want")
CONFIG_PATH = PROJECT_ROOT / "llm_prompt_design" / "config" / "chapters" / "chapter_config_ch05.json"

CH05_PAYLOADS = {
    "step-1": {"commentary": "从回答中看到稳定的才能线索。", "talents": [{"text": "empathy framing", "locked": False}]},
    "step-2": {"talents": [{"text": "empathy framing", "rating": "◎", "locked": False}], "user_manual": "先理解对方，再帮助对方把复杂问题讲清楚。"},
}

CH05_ANSWERS = {
    "step-1": {"q1": "a1", "q2": "a2", "q3": "a3", "q4": "a4", "q5": "a5"},
    "step-2": {"reference_strengths": [{"text": "empathy framing"}]},
}


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


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
        conn.execute(
            """INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at)
               VALUES ('ch05', 1, ?, 1, datetime('now'))""",
            (json.dumps(load_config(), ensure_ascii=False),),
        )
        for role_name in ("psychologist", "career_counselor"):
            conn.execute(
                """INSERT INTO llm_roles
                   (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
                   VALUES (?, ?, 'test', 'role', 'deepseek', 'deepseek-chat', 0.5, 1500, 1)""",
                (str(uuid.uuid4()), role_name),
            )
    import app.runtime.agent as agent_mod
    state = {"payload": CH05_PAYLOADS["step-1"]}

    async def mock_call_llm(*args, **kwargs):
        return json.dumps(state["payload"], ensure_ascii=False)

    agent_mod.call_llm = mock_call_llm
    import app.main as main_mod
    reload(main_mod)
    return main_mod.app, state


async def _run_and_submit(client, state, step_id):
    state["payload"] = CH05_PAYLOADS[step_id]
    run = await client.post(
        f"/api/chapters/ch05/steps/{step_id}/run",
        json={"user_answers": CH05_ANSWERS[step_id]},
    )
    assert run.status_code == 200, (step_id, run.text)
    submitted = await client.post(f"/api/chapters/ch05/steps/{step_id}/submit")
    assert submitted.status_code == 200, (step_id, submitted.text)


def _db_state():
    from app.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT step_id, status, stale FROM step_runs WHERE chapter_id='ch05' AND stale=0 ORDER BY step_id"
        ).fetchall()
        stale_rows = conn.execute(
            "SELECT step_id, status FROM step_runs WHERE chapter_id='ch05' AND stale=1 ORDER BY step_id"
        ).fetchall()
        profile_row = conn.execute("SELECT profile_json FROM learner_profiles WHERE user_id='local'").fetchone()
        profile = json.loads(profile_row["profile_json"] or "{}") if profile_row else {}
    return rows, stale_rows, profile


@pytest.mark.asyncio
async def test_ch05_step1_resubmit_stales_step2_and_clears_talents(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    app_obj, state = _make_app(tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        await _run_and_submit(client, state, "step-1")
        await _run_and_submit(client, state, "step-2")
        rows, stale_rows, profile = _db_state()
        assert {row["step_id"] for row in rows} == {"step-1", "step-2"}
        assert stale_rows == []
        assert profile.get("talents")

        response = await client.post(
            "/api/chapters/ch05/steps/step-1/draft",
            json={"user_answers": CH05_ANSWERS["step-1"], "new_run": True},
        )
        assert response.status_code == 200, response.text
        await _run_and_submit(client, state, "step-1")

        rows, stale_rows, profile = _db_state()
        assert [row["step_id"] for row in stale_rows] == ["step-2"]
        assert "talents" not in profile


@pytest.mark.asyncio
async def test_ch05_rerun_after_stale_rewrites_talents(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    app_obj, state = _make_app(tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        await _run_and_submit(client, state, "step-1")
        await _run_and_submit(client, state, "step-2")
        await client.post("/api/chapters/ch05/steps/step-1/draft", json={"user_answers": CH05_ANSWERS["step-1"], "new_run": True})
        await _run_and_submit(client, state, "step-1")
        _, _, profile = _db_state()
        assert "talents" not in profile

        await _run_and_submit(client, state, "step-2")
        rows, stale_rows, profile = _db_state()
        assert {row["step_id"] for row in rows} == {"step-1", "step-2"}
        assert profile.get("talents")
