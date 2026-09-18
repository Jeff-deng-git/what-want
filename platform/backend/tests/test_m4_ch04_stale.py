"""Contract tests for ch04 cascade stale isolation (design doc ch04_stale isolation §6)."""

import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")

PROJECT_ROOT = Path(r"D:\AI_Project\What_Want")
CONFIG_PATH = PROJECT_ROOT / "llm_prompt_design" / "config" / "chapters" / "chapter_config_ch04.json"

CH04_STEP_PAYLOADS = {
    "step-1": {"top_values": ["按自己的标准活", "不依附他人评价"], "commentary": "two key values"},
    "step-2": {"groups": [{"umbrella": "self-expression", "keywords": ["按自己的标准活", "不依附他人评价", "成长"], "locked": True}]},
    "step-3": {"phase": "screening", "conversions": [
        {"value": "按自己的标准活", "type": "self", "assessment": "keep", "decision": "keep"},
        {"value": "不依附他人评价", "type": "self", "assessment": "keep", "decision": "keep"},
        {"value": "成长", "type": "self", "assessment": "keep", "decision": "keep"},
    ]},
    "step-4": {
        "ranked": [{"value": "self-expression", "locked": True}],
        "support_links": [],
        "final_purpose": {
            "value": "self-expression",
            "life_state": "live by one's own standards",
            "reason": "the confirmed members all serve authentic self-expression",
        },
        "gap_note": "",
    },
    "step-5": {"work_purpose": "help people find direction", "reasoning": "repeatedly helping others clarify direction", "experience_map": [{"experience": "friend asked for advice", "values": ["growth"]}]},
}

CH04_ANSWERS = {
    "step-1": {"q1": "a1", "q2": "a2", "q3": "a3", "q4": "a4", "q5": "a5"},
    "step-2": {"supplemental_keywords": [{"text": "成长"}]},
    "step-3": {},
    "step-4": {},
    "step-5": {"experiences": [{"experience": f"experience {i}"} for i in range(10)]},
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
               VALUES ('ch04', 1, ?, 1, datetime('now'))""",
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
    state = {"payload": CH04_STEP_PAYLOADS["step-1"]}

    async def mock_call_llm(*args, **kwargs):
        return json.dumps(state["payload"], ensure_ascii=False)

    agent_mod.call_llm = mock_call_llm
    import app.main as main_mod
    reload(main_mod)
    return main_mod.app, state


async def _run_and_submit(client, state, step_id, answers=None, payload=None):
    state["payload"] = payload or CH04_STEP_PAYLOADS[step_id]
    run = await client.post(
        f"/api/chapters/ch04/steps/{step_id}/run",
        json={"user_answers": answers if answers is not None else CH04_ANSWERS[step_id]},
    )
    assert run.status_code == 200, (step_id, run.text)
    submitted = await client.post(f"/api/chapters/ch04/steps/{step_id}/submit")
    assert submitted.status_code == 200, (step_id, submitted.text)


async def _complete_all_five(client, state):
    for step_id in ("step-1", "step-2", "step-3", "step-4", "step-5"):
        await _run_and_submit(client, state, step_id)


def _db_state():
    from app.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT step_id, status, stale FROM step_runs WHERE chapter_id='ch04' AND stale=0 ORDER BY step_id"
        ).fetchall()
        stale_rows = conn.execute(
            "SELECT step_id, status FROM step_runs WHERE chapter_id='ch04' AND stale=1 ORDER BY step_id"
        ).fetchall()
        profile_row = conn.execute(
            "SELECT profile_json FROM learner_profiles WHERE user_id='local'"
        ).fetchone()
        profile = json.loads(profile_row["profile_json"] or "{}") if profile_row else {}
    return rows, stale_rows, profile


@pytest.mark.asyncio
async def test_ch04_resubmit_step1_stales_all_downstream_and_clears_profile(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    app_obj, state = _make_app(tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        await _complete_all_five(client, state)
        rows, stale_rows, profile = _db_state()
        assert [row["step_id"] for row in rows] == ["step-1", "step-2", "step-3", "step-4", "step-5"]
        assert stale_rows == []
        assert profile.get("values") and profile.get("ranked") and profile.get("work_purpose")

        response = await client.post(
            "/api/chapters/ch04/steps/step-1/draft",
            json={"user_answers": CH04_ANSWERS["step-1"], "new_run": True},
        )
        assert response.status_code == 200, response.text
        await _run_and_submit(client, state, "step-1")

        rows, stale_rows, profile = _db_state()
        assert [row["step_id"] for row in stale_rows] == ["step-2", "step-3", "step-4", "step-5"]
        assert "values" not in profile and "ranked" not in profile and "work_purpose" not in profile
        assert {row["step_id"] for row in rows} == {"step-1"}


@pytest.mark.asyncio
async def test_ch04_resubmit_step4_stales_only_step5(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    app_obj, state = _make_app(tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        await _complete_all_five(client, state)
        response = await client.post(
            "/api/chapters/ch04/steps/step-4/draft",
            json={"user_answers": {}, "new_run": True},
        )
        assert response.status_code == 200, response.text
        await _run_and_submit(client, state, "step-4")
        rows, stale_rows, profile = _db_state()
        assert [row["step_id"] for row in stale_rows] == ["step-5"]
        assert "values" not in profile and "ranked" not in profile and "work_purpose" not in profile


@pytest.mark.asyncio
async def test_ch04_step5_resubmit_rewrites_profile_without_clearing(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    app_obj, state = _make_app(tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        await _complete_all_five(client, state)
        response = await client.post(
            "/api/chapters/ch04/steps/step-5/draft",
            json={"user_answers": CH04_ANSWERS["step-5"], "new_run": True},
        )
        assert response.status_code == 200, response.text
        await _run_and_submit(client, state, "step-5")
        rows, stale_rows, profile = _db_state()
        assert stale_rows == []
        assert profile.get("values") and profile.get("ranked") and profile.get("work_purpose")


@pytest.mark.asyncio
async def test_ch04_rerun_after_stale_rewrites_profile(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient
    app_obj, state = _make_app(tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        await _complete_all_five(client, state)
        await client.post("/api/chapters/ch04/steps/step-1/draft", json={"user_answers": CH04_ANSWERS["step-1"], "new_run": True})
        await _run_and_submit(client, state, "step-1")
        _, _, profile = _db_state()
        assert "work_purpose" not in profile

        await _complete_all_five(client, state)
        rows, stale_rows, profile = _db_state()
        assert {row["step_id"] for row in rows} == {"step-1", "step-2", "step-3", "step-4", "step-5"}
        assert profile.get("values") and profile.get("ranked") and profile.get("work_purpose")


@pytest.mark.asyncio
async def test_ch04_downstream_closure_covers_diamond_dependency(tmp_path, monkeypatch):
    from app.routers.steps import _downstream_step_ids
    _make_app(tmp_path, monkeypatch)
    assert _downstream_step_ids("ch04", "step-1") == ["step-2", "step-3", "step-4", "step-5"]
    assert _downstream_step_ids("ch04", "step-2") == ["step-3", "step-4", "step-5"]
    assert _downstream_step_ids("ch04", "step-3") == ["step-4", "step-5"]
    assert _downstream_step_ids("ch04", "step-4") == ["step-5"]
    assert _downstream_step_ids("ch04", "step-5") == []
