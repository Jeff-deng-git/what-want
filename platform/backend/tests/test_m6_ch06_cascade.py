"""Contract tests for the ch06 two-stage likes cascade."""
import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")

PROJECT_ROOT = Path(r"D:\AI_Project\What_Want")
CONFIG_PATH = PROJECT_ROOT / "llm_prompt_design" / "config" / "chapters" / "chapter_config_ch06.json"


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def step1_answers(prefix="a"):
    return {f"q{index}": f"{prefix}-{index}" for index in range(1, 6)}


def test_ch06_config_has_two_stage_likes_contract():
    cfg = load_config()
    assert [item["step_id"] for item in cfg["exercises"]] == ["step-1", "step-2"]
    step1_fields = cfg["exercises"][0]["output_fields"][0]["item_schema"]["fields"]
    assert {field["name"] for field in step1_fields} == {"text", "locked", "source"}
    step2_fields = cfg["exercises"][1]["output_fields"][0]["item_schema"]["fields"]
    assert {field["name"] for field in step2_fields} == {
        "field", "aspects", "linked_strengths", "sources", "locked"
    }
    assert len(cfg["ui_context"]["passion_examples"]) == 100


def test_ch06_step2_prompt_merges_domains_seeds_and_talents():
    from app.runtime.assembler import build_step_prompt

    cfg = load_config()
    exercise = cfg["exercises"][1]
    prior = {"step-1": {"output": {"likes": [
        {"text": "心理学", "locked": False, "source": "q1"},
        {"text": "设计", "locked": False, "source": "q2"},
    ]}}}
    _, user = build_step_prompt(
        "role",
        cfg,
        exercise,
        prior,
        {
            "reference_talents": [{"text": "倾听"}],
            "passion_seeds": [{"text": "心理学", "source": "passion_examples"}, {"text": "摄影"}],
        },
    )
    candidates = user.rsplit("[CH06 DISCOVERY CANDIDATES]", 1)[1]
    assert candidates.count("心理学") == 1
    assert candidates.count("设计") == 1
    assert candidates.count("倾听") == 1
    assert candidates.count("摄影") == 1


def test_ch06_output_normalization_and_validation():
    from app.routers import steps

    step1 = steps._normalize_ch06_run_output({
        "commentary": "evidence",
        "likes": [{"text": "心理学", "locked": 1, "source": "q1", "aspects": ["bad"]}],
    }, "step-1")
    assert step1["likes"] == [{"text": "心理学", "locked": False, "source": "q1"}]
    assert not steps._validate_ch06_output(step1, "step-1")

    step2 = steps._normalize_ch06_run_output({
        "commentary": "拆解",
        "likes": [{
            "field": "心理学",
            "aspects": ["理解动机"],
            "linked_strengths": ["倾听"],
            "sources": ["q1"],
            "locked": False,
        }],
    }, "step-2")
    assert step2["likes"][0]["aspects"] == [{"text": "理解动机"}]
    assert step2["likes"][0]["linked_strengths"] == [{"text": "倾听"}]
    assert not steps._validate_ch06_output(step2, "step-2")


def test_ch06_source_normalization_accepts_free_form_tokens():
    from app.routers import steps

    step1 = steps._normalize_ch06_run_output({
        "commentary": "evidence",
        "likes": [
            {"text": "心理学", "locked": False, "source": "Q1 / Q3"},
            {"text": "摄影", "locked": False, "source": "来自 q2 和 q61"},
            {"text": "写作", "locked": False, "source": "no valid token"},
        ],
    }, "step-1")
    assert step1["likes"][0]["source"] == "q1,q3"
    assert step1["likes"][1]["source"] == "q2,q61"
    assert step1["likes"][2]["source"] is None
    assert not steps._validate_ch06_output(step1, "step-1")

    step2 = steps._normalize_ch06_run_output({
        "commentary": "拆解",
        "likes": [{
            "field": "心理学",
            "aspects": ["理解动机"],
            "linked_strengths": ["倾听"],
            "sources": ["q1,q3", "Q61", "无效", "q1"],
            "locked": False,
        }],
    }, "step-2")
    assert step2["likes"][0]["sources"] == ["q1", "q3", "q61"]
    assert not steps._validate_ch06_output(step2, "step-2")


@pytest.mark.asyncio
async def test_ch06_profile_only_accepts_step2_and_invalidates_stale_step2(tmp_path, monkeypatch):
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
        conn.execute(
            """INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at)
               VALUES ('ch06', 1, ?, 1, datetime('now'))""",
            (json.dumps(cfg, ensure_ascii=False),),
        )
        for role_name in ("psychologist", "career_counselor"):
            conn.execute(
                """INSERT INTO llm_roles
                   (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
                   VALUES (?, ?, 'test', 'role', 'deepseek', 'deepseek-chat', 0.5, 1500, 1)""",
                (str(uuid.uuid4()), role_name),
            )

    outputs = [
        {"commentary": "第一轮映照", "likes": [{"text": "心理学", "locked": False, "source": "q1"}]},
        {"commentary": "第一轮拆解", "likes": [{
            "field": "心理学", "aspects": [{"text": "理解动机"}],
            "linked_strengths": [{"text": "倾听"}], "sources": ["q1"], "locked": False,
        }]},
        {"commentary": "第二轮映照", "likes": [{"text": "摄影", "locked": False, "source": "q2"}]},
        {"commentary": "第二轮拆解", "likes": [{
            "field": "摄影", "aspects": [{"text": "观察光线"}],
            "linked_strengths": [], "sources": ["q2"], "locked": False,
        }]},
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
        response = await client.post(
            "/api/chapters/ch06/steps/step-1/run",
            json={"user_answers": step1_answers("first")},
        )
        assert response.status_code == 200, response.text
        assert (await client.post("/api/chapters/ch06/steps/step-1/submit")).status_code == 200
        with app.db.get_conn() as conn:
            profile = json.loads(conn.execute(
                "SELECT profile_json FROM learner_profiles WHERE user_id='local'"
            ).fetchone()["profile_json"])
            assert profile["likes"] == []

        response = await client.post(
            "/api/chapters/ch06/steps/step-2/run",
            json={"user_answers": {"reference_talents": [{"text": "倾听"}]}},
        )
        assert response.status_code == 200, response.text
        assert (await client.post("/api/chapters/ch06/steps/step-2/submit")).status_code == 200
        with app.db.get_conn() as conn:
            profile = json.loads(conn.execute(
                "SELECT profile_json FROM learner_profiles WHERE user_id='local'"
            ).fetchone()["profile_json"])
            assert profile["likes"][0]["field"] == "心理学"

        response = await client.post(
            "/api/chapters/ch06/steps/step-1/draft",
            json={"user_answers": step1_answers("second"), "new_run": True},
        )
        assert response.status_code == 200, response.text
        assert (await client.post(
            "/api/chapters/ch06/steps/step-1/run",
            json={"user_answers": step1_answers("second")},
        )).status_code == 200
        assert (await client.post("/api/chapters/ch06/steps/step-1/submit")).status_code == 200
        with app.db.get_conn() as conn:
            stale = conn.execute(
                """SELECT COUNT(*) AS n FROM step_runs
                   WHERE chapter_id='ch06' AND step_id='step-2' AND stale=1"""
            ).fetchone()["n"]
            profile = json.loads(conn.execute(
                "SELECT profile_json FROM learner_profiles WHERE user_id='local'"
            ).fetchone()["profile_json"])
            assert stale == 1
            assert profile["likes"] == []

        response = await client.post(
            "/api/chapters/ch06/steps/step-2/run",
            json={"user_answers": {"passion_seeds": [{"text": "摄影"}]}},
        )
        assert response.status_code == 200, response.text
        assert (await client.post("/api/chapters/ch06/steps/step-2/submit")).status_code == 200
        with app.db.get_conn() as conn:
            profile = json.loads(conn.execute(
                "SELECT profile_json FROM learner_profiles WHERE user_id='local'"
            ).fetchone()["profile_json"])
            assert profile["likes"][0]["field"] == "摄影"
