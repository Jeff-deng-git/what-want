"""Focused ch02 contract tests for the four-stage exercise flow."""
import json
import os
import sys
import uuid
from importlib import reload

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")
CONFIG_PATH = r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch02.json"


@pytest.fixture
def ch02_app(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    import app.config
    import app.db
    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, 1, ?, 1, datetime('now'))",
            ("ch02", json.dumps(cfg, ensure_ascii=False)),
        )
        conn.execute(
            "INSERT INTO learner_profiles (user_id, profile_json) VALUES (?, ?)",
            ("local", json.dumps({
                "misconceptions_cleared": ["必须找到唯一答案"],
                "external_voices": {"1": "家里人说稳定体面", "3": "同事都在考证"},
            }, ensure_ascii=False)),
        )
        for role_name in ("psychologist", "career_counselor"):
            conn.execute(
                """INSERT INTO llm_roles
                   (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (str(uuid.uuid4()), role_name, "test", "You are " + role_name,
                 "deepseek", "deepseek-chat", 0.2, 1200),
            )
    import app.runtime.agent as agent_mod
    response = {
        "commentary": "针对加班与画画的驱动力映照。",
        "internal_external_ratio": {"external_pct": 1, "internal_pct": 99, "method": "wrong"},
        "reclaim_item": "我想重新决定把时间给谁。",
    }

    async def mock_call_llm(*args, **kwargs):
        return json.dumps(response, ensure_ascii=False)

    monkeypatch.setattr(agent_mod, "call_llm", mock_call_llm)
    import app.main as main_mod
    reload(main_mod)
    return main_mod.app, app.db, agent_mod


@pytest.fixture
def valid_answers():
    return {
        "drive_items": [
            {"text": "加班做项目", "drive": "external", "note": "领导会看到我的进步"},
            {"text": "周末画画", "drive": "internal", "note": "自己真的喜欢"},
            {"text": "准备资格考试", "drive": "external", "note": "家人觉得更体面"},
        ],
        "notes": "想分清哪些选择是我自己的",
    }


async def run_ch02(client, answers):
    response = await client.post(
        "/api/chapters/ch02/steps/step-1/run",
        json={"user_answers": answers},
    )
    assert response.status_code == 200, response.text
    return response


@pytest.mark.asyncio
async def test_ch02_ratio_is_backend_derived_and_prompt_keeps_context(ch02_app, valid_answers):
    from httpx import ASGITransport, AsyncClient

    app_obj, db, _ = ch02_app
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        response = await run_ch02(client, valid_answers)
    payload = response.json()
    assert payload["parsed_output"]["internal_external_ratio"] == {
        "external_pct": 67,
        "internal_pct": 33,
        "method": "item_count",
    }
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT rendered_prompt FROM step_runs WHERE chapter_id='ch02' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    prompt = row["rendered_prompt"]
    assert "misconceptions_cleared" in prompt
    assert "external_voices" in prompt
    assert "加班做项目" in prompt
    assert "领导会看到我的进步" in prompt


@pytest.mark.asyncio
async def test_ch02_invalid_json_is_failed_and_not_submittable(ch02_app, valid_answers):
    from httpx import ASGITransport, AsyncClient

    app_obj, db, agent_mod = ch02_app

    async def invalid_call(*args, **kwargs):
        return "not json"

    agent_mod.call_llm = invalid_call
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        response = await client.post(
            "/api/chapters/ch02/steps/step-1/run",
            json={"user_answers": valid_answers},
        )
        assert response.status_code == 502
        submit = await client.post("/api/chapters/ch02/steps/step-1/submit")
        assert submit.status_code == 409
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM step_runs WHERE chapter_id='ch02' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    assert row["status"] == "failed"


@pytest.mark.asyncio
async def test_ch02_output_edit_only_changes_reclaim_item(ch02_app, valid_answers):
    from httpx import ASGITransport, AsyncClient

    app_obj, db, _ = ch02_app
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        await run_ch02(client, valid_answers)
        edited = await client.put(
            "/api/chapters/ch02/steps/step-1/output",
            json={"parsed_output": {"reclaim_item": "我决定重新安排自己的周末。"}},
        )
        assert edited.status_code == 200, edited.text
        readonly = await client.put(
            "/api/chapters/ch02/steps/step-1/output",
            json={"parsed_output": {"commentary": "篡改"}},
        )
        assert readonly.status_code == 409
        submitted = await client.post("/api/chapters/ch02/steps/step-1/submit")
        assert submitted.status_code == 200, submitted.text
    with db.get_conn() as conn:
        run = conn.execute(
            "SELECT status, parsed_output FROM step_runs WHERE chapter_id='ch02' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        profile = conn.execute(
            "SELECT profile_json FROM learner_profiles WHERE user_id='local'"
        ).fetchone()
    assert run["status"] == "submitted"
    parsed = json.loads(run["parsed_output"])
    assert parsed["reclaim_item"] == "我决定重新安排自己的周末。"
    assert parsed["internal_external_ratio"]["method"] == "item_count"
    assert json.loads(profile["profile_json"])["reclaim_item"] == "我决定重新安排自己的周末。"


@pytest.mark.asyncio
async def test_ch02_new_run_preserves_submitted_history(ch02_app, valid_answers):
    from httpx import ASGITransport, AsyncClient

    app_obj, db, _ = ch02_app
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        first = await run_ch02(client, valid_answers)
        first_id = first.json()["id"]
        assert (await client.post("/api/chapters/ch02/steps/step-1/submit")).status_code == 200
        draft = await client.post(
            "/api/chapters/ch02/steps/step-1/draft",
            json={"user_answers": {"drive_items": [{}, {}], "notes": ""}, "new_run": True},
        )
        assert draft.status_code == 200, draft.text
        assert draft.json()["id"] != first_id
        current = await client.get("/api/chapters/ch02/steps/step-1")
        assert current.json()["current_run"]["status"] == "draft"
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, status FROM step_runs WHERE chapter_id='ch02' ORDER BY created_at, rowid"
        ).fetchall()
    assert [(row["id"], row["status"]) for row in rows] == [
        (first_id, "submitted"),
        (draft.json()["id"], "draft"),
    ]


@pytest.mark.asyncio
async def test_ch02_requires_two_complete_items(ch02_app):
    from httpx import ASGITransport, AsyncClient

    app_obj, _, _ = ch02_app
    bad_answers = {"drive_items": [{"text": "只有一件", "drive": "external"}], "notes": ""}
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        response = await client.post(
            "/api/chapters/ch02/steps/step-1/run",
            json={"user_answers": bad_answers},
        )
    assert response.status_code == 422
    assert "requires at least 2" in response.json()["detail"]["errors"][0]

@pytest.mark.asyncio
async def test_ch02_provider_timeout_returns_gateway_timeout_and_preserves_latest_answers(ch02_app, valid_answers):
    from httpx import ASGITransport, AsyncClient
    from app.services.llm_client import LLMTimeoutError

    app_obj, db, agent_mod = ch02_app
    updated_answers = {
        **valid_answers,
        "drive_items": [
            {**valid_answers["drive_items"][0], "text": "修改后的事项"},
            *valid_answers["drive_items"][1:],
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        await run_ch02(client, valid_answers)

        async def timeout_call(*args, **kwargs):
            raise LLMTimeoutError("LLM provider timed out after 120s")

        agent_mod.call_llm = timeout_call
        response = await client.post(
            "/api/chapters/ch02/steps/step-1/run",
            json={"user_answers": updated_answers},
        )

    assert response.status_code == 504
    assert "timed out after 120s" in response.json()["detail"]
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT status, user_answers, rendered_prompt FROM step_runs WHERE chapter_id='ch02' ORDER BY created_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
    assert row["status"] == "failed"
    assert json.loads(row["user_answers"]) == updated_answers
    assert row["rendered_prompt"] == ""