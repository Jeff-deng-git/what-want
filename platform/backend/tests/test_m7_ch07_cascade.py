"""Contract tests for the ch07 two-stage ideal_works cascade."""

import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")

PROJECT_ROOT = Path(r"D:\AI_Project\What_Want")
CONFIG_PATH = PROJECT_ROOT / "llm_prompt_design" / "config" / "chapters" / "chapter_config_ch07.json"


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_upstream(chapter_id):
    path = PROJECT_ROOT / "llm_prompt_design" / "config" / "chapters" / f"chapter_config_{chapter_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_ch07_config_has_two_stage_contract():
    cfg = load_config()
    assert [item["step_id"] for item in cfg["exercises"]] == ["step-1", "step-2"]
    assert cfg["step_context"]["references"] == ["talents", "likes", "work_purpose", "values"]
    step2_refs = cfg["exercises"][1]["references"]
    assert step2_refs[0]["from_exercise"] == "step-1"
    assert step2_refs[0]["fields"] == ["ideal_works"]
    buckets = {item["name"]: item for item in cfg["exercises"][1]["output_fields"][0]["item_schema"]["fields"]}["bucket"]["enum"]
    assert buckets == ["真正想做的事", "作为兴趣的想做的事", "未定"]


def test_ch07_output_normalization_and_validation():
    from app.routers import steps

    step1 = steps._normalize_ch07_run_output({
        "commentary": "组合点评",
        "ideal_works": [
            {"title": "一个帮迷茫的人看清方向的人", "like_source": "理解动机", "strength_source": "倾听", "bucket": "真正想做的事", "locked": 1},
            {"title": "", "bucket": "未定"},
            {"title": "保留", "bucket": "奇怪桶", "locked": False},
        ],
    }, "step-1")
    assert step1["ideal_works"][0]["bucket"] == "真正想做的事"
    assert step1["ideal_works"][0]["locked"] is False
    assert step1["ideal_works"][1]["bucket"] == "未定"
    assert not steps._validate_ch07_output(step1, "step-1")

    step2 = steps._normalize_ch07_run_output({
        "commentary": "筛选点评",
        "ideal_works": [{"title": "一个帮迷茫的人看清方向的人", "bucket": "真正想做的事", "locked": False}],
        "next_action": "先接一次 30 分钟免费梳理对话",
    }, "step-2")
    assert not steps._validate_ch07_output(step2, "step-2")
    assert steps._validate_ch07_output({"commentary": "点评", "ideal_works": []}, "step-2")


def test_ch07_step2_prompt_contains_step1_works_and_profile():
    from app.runtime.assembler import build_step_prompt

    cfg = load_config()
    exercise = cfg["exercises"][1]
    prior = {"step-1": {"output": {"ideal_works": [{"title": "一个帮迷茫的人看清方向的人", "bucket": "未定"}]}}}
    profile = {
        "talents": [{"text": "倾听", "rating": "◎"}],
        "likes": [{"field": "心理学", "aspects": [{"text": "理解动机"}]}],
        "work_purpose": "帮更多人找到自己真正想做的事",
        "values": ["真实"],
    }
    system, user = build_step_prompt("mentor", cfg, exercise, prior, {}, profile=profile)
    assert "一个帮迷茫的人看清方向的人" in user
    assert "work_purpose" in system


@pytest.mark.asyncio
async def test_ch07_cascade_gate_stale_and_canonical_profile(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    from importlib import reload
    import app.config
    import app.db
    reload(app.config)
    reload(app.db)
    app.db.init_db()

    cfg = load_config()
    with app.db.get_conn() as conn:
        for chapter_id in ("ch04", "ch05", "ch06", "ch07"):
            chapter_cfg = load_upstream(chapter_id) if chapter_id != "ch07" else cfg
            conn.execute(
                """INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at)
                   VALUES (?, 1, ?, 1, datetime('now'))""",
                (chapter_id, json.dumps(chapter_cfg, ensure_ascii=False)),
            )
        upstream_steps = {
            "ch04": ["step-1", "step-2", "step-3", "step-4", "step-5"],
            "ch05": ["step-1", "step-2"],
            "ch06": ["step-1", "step-2"],
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
                "work_purpose": "帮更多人找到自己真正想做的事",
                "values": ["真实"],
                "talents": [{"text": "倾听"}],
                "likes": [{"field": "心理学", "aspects": [{"text": "理解动机"}]}],
            }, ensure_ascii=False),),
        )
        for role_name in ("career_counselor", "mentor"):
            conn.execute(
                """INSERT INTO llm_roles
                   (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
                   VALUES (?, ?, 'test', 'role', 'deepseek', 'deepseek-chat', 0.5, 1500, 1)""",
                (str(uuid.uuid4()), role_name),
            )

    outputs = [
        {"commentary": "第一轮组合", "ideal_works": [{"title": "一个帮迷茫的人看清方向的人", "like_source": "理解动机", "strength_source": "倾听", "bucket": "未定", "locked": False}]},
        {"commentary": "第一轮筛选", "ideal_works": [{"title": "一个帮迷茫的人看清方向的人", "like_source": "理解动机", "strength_source": "倾听", "bucket": "真正想做的事", "locked": False}], "next_action": "先接一次梳理对话"},
        {"commentary": "第二轮组合", "ideal_works": [{"title": "一个用镜头记录真实故事的人", "like_source": "光影叙事", "strength_source": "共情", "bucket": "未定", "locked": False}]},
        {"commentary": "第二轮筛选", "ideal_works": [{"title": "一个用镜头记录真实故事的人", "like_source": "光影叙事", "strength_source": "共情", "bucket": "作为兴趣的想做的事", "locked": False}], "next_action": "先拍一部三分钟短片"},
    ]
    calls = []
    import app.runtime.agent as agent_mod

    async def mock_call_llm(*args, **kwargs):
        calls.append(kwargs)
        return json.dumps(outputs[len(calls) - 1], ensure_ascii=False)

    agent_mod.call_llm = mock_call_llm
    import app.main as main_mod
    reload(main_mod)

    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://test") as client:
        response = await client.post("/api/chapters/ch07/steps/step-1/run", json={"user_answers": {}})
        assert response.status_code == 200, response.text
        assert (await client.post("/api/chapters/ch07/steps/step-1/submit")).status_code == 200
        with app.db.get_conn() as conn:
            profile = json.loads(conn.execute(
                "SELECT profile_json FROM learner_profiles WHERE user_id='local'"
            ).fetchone()["profile_json"])
            assert profile.get("ideal_works") == []

        response = await client.post("/api/chapters/ch07/steps/step-2/run", json={"user_answers": {}})
        assert response.status_code == 200, response.text
        assert (await client.post("/api/chapters/ch07/steps/step-2/submit")).status_code == 200
        with app.db.get_conn() as conn:
            profile = json.loads(conn.execute(
                "SELECT profile_json FROM learner_profiles WHERE user_id='local'"
            ).fetchone()["profile_json"])
            assert profile["ideal_works"][0]["title"] == "一个帮迷茫的人看清方向的人"
            assert profile["ideal_works"][0]["bucket"] == "真正想做的事"

        response = await client.post(
            "/api/chapters/ch07/steps/step-1/draft",
            json={"user_answers": {}, "new_run": True},
        )
        assert response.status_code == 200, response.text
        assert (await client.post("/api/chapters/ch07/steps/step-1/run", json={"user_answers": {}})).status_code == 200
        assert (await client.post("/api/chapters/ch07/steps/step-1/submit")).status_code == 200
        with app.db.get_conn() as conn:
            stale = conn.execute(
                """SELECT COUNT(*) AS n FROM step_runs
                   WHERE chapter_id='ch07' AND step_id='step-2' AND stale=1"""
            ).fetchone()["n"]
            profile = json.loads(conn.execute(
                "SELECT profile_json FROM learner_profiles WHERE user_id='local'"
            ).fetchone()["profile_json"])
            assert stale == 1
            assert profile.get("ideal_works") == []

        assert (await client.post("/api/chapters/ch07/steps/step-2/run", json={"user_answers": {}})).status_code == 200
        assert (await client.post("/api/chapters/ch07/steps/step-2/submit")).status_code == 200
        with app.db.get_conn() as conn:
            profile = json.loads(conn.execute(
                "SELECT profile_json FROM learner_profiles WHERE user_id='local'"
            ).fetchone()["profile_json"])
            assert profile["ideal_works"][0]["title"] == "一个用镜头记录真实故事的人"
            assert profile["ideal_works"][0]["bucket"] == "作为兴趣的想做的事"


@pytest.mark.asyncio
async def test_ch07_run_blocked_without_upstream(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    from importlib import reload
    import app.config
    import app.db
    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with app.db.get_conn() as conn:
        for chapter_id in ("ch04", "ch05", "ch06", "ch07"):
            chapter_cfg = load_upstream(chapter_id) if chapter_id != "ch07" else load_config()
            conn.execute(
                """INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at)
                   VALUES (?, 1, ?, 1, datetime('now'))""",
                (chapter_id, json.dumps(chapter_cfg, ensure_ascii=False)),
            )

    import app.main as main_mod
    reload(main_mod)
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://test") as client:
        response = await client.post("/api/chapters/ch07/steps/step-1/run", json={"user_answers": {}})
        assert response.status_code == 409, response.text
