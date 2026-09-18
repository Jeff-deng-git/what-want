"""Focused ch03 contract tests for context isolation and four-stage persistence."""
import json
import sys
import uuid
from importlib import reload

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")
ROOT = r"D:\AI_Project\What_Want"
CH01_CONFIG = ROOT + r"\llm_prompt_design\config\chapters\chapter_config_ch01.json"
CH03_CONFIG = ROOT + r"\llm_prompt_design\config\chapters\chapter_config_ch03.json"


@pytest.fixture
def ch03_app(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    import app.config
    import app.db
    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with open(CH01_CONFIG, "r", encoding="utf-8") as handle:
        ch01_cfg = json.load(handle)
    with open(CH03_CONFIG, "r", encoding="utf-8") as handle:
        ch03_cfg = json.load(handle)
    with app.db.get_conn() as conn:
        for chapter_id, cfg in (("ch01", ch01_cfg), ("ch03", ch03_cfg)):
            conn.execute(
                "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, 1, ?, 1, datetime('now'))",
                (chapter_id, json.dumps(cfg, ensure_ascii=False)),
            )
        conn.execute(
            "INSERT INTO learner_profiles (user_id, profile_json) VALUES (?, ?)",
            ("local", json.dumps({
                "external_voices": {"5": "同事都考 CPA，我也得考", "3": "", "2": "要有命中注定的感觉"},
            }, ensure_ascii=False)),
        )
        conn.execute(
            """INSERT INTO llm_roles
               (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (str(uuid.uuid4()), "psychologist", "test", "You are a test psychologist",
             "deepseek", "deepseek-chat", 0.2, 1200),
        )
    import app.runtime.agent as agent_mod
    response = {
        "commentary": "你把写代码当成了才能候选，但这更像技能；你喜欢的活动还可以继续拆解其领域和协作方式。",
        "importance": ["帮助别人", "持续学习", "保留创造空间"],
        "talents": ["理解复杂问题", "把话讲清楚", "组织协作"],
        "likes": ["探索心理学", "做有用的工具", "和人讨论想法"],
        "intersection": "用理解、表达与创造帮助别人解决复杂问题。",
    }

    async def mock_call_llm(*args, **kwargs):
        return json.dumps(response, ensure_ascii=False)

    monkeypatch.setattr(agent_mod, "call_llm", mock_call_llm)
    import app.main as main_mod
    reload(main_mod)
    return main_mod.app, app.db


@pytest.fixture
def valid_answers():
    return {
        "importance": [{"text": "帮助别人"}, {"text": "持续学习"}, {"text": "创造空间"}],
        "talents": [{"text": "写代码"}, {"text": "解释复杂问题"}, {"text": "组织协作"}],
        "likes": [{"text": "心理学"}, {"text": "做工具"}, {"text": "和人讨论"}],
    }


@pytest.mark.asyncio
async def test_ch03_step_detail_returns_sorted_filtered_ui_context(ch03_app):
    from httpx import ASGITransport, AsyncClient

    app_obj, _ = ch03_app
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        response = await client.get("/api/chapters/ch03/steps/step-1")
    assert response.status_code == 200, response.text
    assert response.json()["ui_context"] == {
        "external_voices": [
            {
                "misconception_id": "2",
                "misconception_label": "找到想做的事时会有命中注定的感觉",
                "voice_text": "要有命中注定的感觉",
            },
            {
                "misconception_id": "5",
                "misconception_label": "想做的事不能成为工作",
                "voice_text": "同事都考 CPA，我也得考",
            },
        ]
    }


@pytest.mark.asyncio
async def test_ch03_step_prompt_excludes_ui_and_mentor_profile(ch03_app, valid_answers):
    from httpx import ASGITransport, AsyncClient

    app_obj, db = ch03_app
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        response = await client.post("/api/chapters/ch03/steps/step-1/run", json={"user_answers": valid_answers})
    assert response.status_code == 200, response.text
    with db.get_conn() as conn:
        row = conn.execute("SELECT rendered_prompt FROM step_runs WHERE chapter_id='ch03' ORDER BY created_at DESC LIMIT 1").fetchone()
    prompt = row["rendered_prompt"]
    assert "[CH03 ANALYSIS CONTRACT]" in prompt
    assert "同事都考 CPA" not in prompt
    assert "要有命中注定的感觉" not in prompt
    assert "写代码" in prompt


@pytest.mark.asyncio
async def test_ch03_rerun_preserves_previous_saved_run(ch03_app, valid_answers):
    from httpx import ASGITransport, AsyncClient

    app_obj, db = ch03_app
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        first = await client.post("/api/chapters/ch03/steps/step-1/run", json={"user_answers": valid_answers})
        second = await client.post("/api/chapters/ch03/steps/step-1/run", json={"user_answers": valid_answers})
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] != second.json()["id"]
    with db.get_conn() as conn:
        rows = conn.execute("SELECT id, status FROM step_runs WHERE chapter_id='ch03' AND step_id='step-1' ORDER BY rowid").fetchall()
    assert len(rows) == 2
    assert [row["status"] for row in rows] == ["saved", "saved"]


@pytest.mark.asyncio
async def test_ch03_output_validation_and_profile_are_canonical(ch03_app, valid_answers):
    from httpx import ASGITransport, AsyncClient

    app_obj, db = ch03_app
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
        run = await client.post("/api/chapters/ch03/steps/step-1/run", json={"user_answers": valid_answers})
        assert run.status_code == 200, run.text
        invalid = await client.put(
            "/api/chapters/ch03/steps/step-1/output",
            json={"parsed_output": {"importance": ["a", "b", "c", "d", "e", "f"]}},
        )
        assert invalid.status_code == 422, invalid.text
        submit = await client.post("/api/chapters/ch03/steps/step-1/submit")
        assert submit.status_code == 200, submit.text
    with db.get_conn() as conn:
        profile = json.loads(conn.execute("SELECT profile_json FROM learner_profiles WHERE user_id='local'").fetchone()["profile_json"])
    assert profile["importance"] == ["帮助别人", "持续学习", "保留创造空间"]
    assert all(isinstance(item, str) for item in profile["talents"])
    assert all(isinstance(item, str) for item in profile["likes"])
