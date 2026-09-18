
"""Contract tests for the ch05 two-step talent cascade."""
import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")

PROJECT_ROOT = Path(r"D:\AI_Project\What_Want")
CONFIG_PATH = PROJECT_ROOT / "llm_prompt_design" / "config" / "chapters" / "chapter_config_ch05.json"
GOOD = chr(0x25CE)
SOME = chr(0x3007)


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def test_ch05_config_contains_canonical_examples_and_two_steps():
    cfg = load_config()
    assert [item["step_id"] for item in cfg["exercises"]] == ["step-1", "step-2"]
    fields = cfg["exercises"][0]["output_fields"][0]["item_schema"]["fields"]
    assert fields[1]["name"] == "locked"
    assert all(field["name"] != "rating" for field in fields)
    examples = cfg["ui_context"]["strength_examples"]
    assert len(examples) == 100
    assert [item["id"] for item in examples] == [f"s{index:02d}" for index in range(1, 101)]
    assert all(item["text"] for item in examples)


def test_ch05_step2_prompt_merges_step1_and_reference_strengths():
    from app.runtime.assembler import build_step_prompt

    cfg = load_config()
    exercise = cfg["exercises"][1]
    prior = {"step-1": {"output": {"talents": [
        {"text": "talent-a", "locked": False, "source": None},
        {"text": "calm-b", "locked": False, "source": None},
    ]}}}
    _, user = build_step_prompt(
        "role",
        cfg,
        exercise,
        prior,
        {"reference_strengths": [{"text": "calm-b"}, {"text": "energy-c"}]},
    )
    candidate_block = user.rsplit("[CH05 MERGED TALENT CANDIDATES]", 1)[1]
    assert candidate_block.count("talent-a") == 1
    assert candidate_block.count("calm-b") == 1
    assert candidate_block.count("energy-c") == 1
    assert '"source": "100_examples"' in candidate_block


def test_ch05_output_normalization_preserves_sources_and_empty_rating(monkeypatch):
    from app.routers import steps

    monkeypatch.setattr(
        steps,
        "_ch05_step2_candidates",
        lambda answers: [
            {"text": "talent-a", "source": None},
            {"text": "energy-c", "source": "100_examples"},
        ],
    )
    parsed = {
        "talents": [
            {"text": "talent-a", "rating": GOOD, "locked": False},
            {"text": "energy-c", "rating": "", "locked": False},
            {"text": "invented", "rating": SOME, "locked": False},
        ],
        "user_manual": "manual-a",
    }
    normalized = steps._normalize_ch05_run_output(parsed, "step-2", {"reference_strengths": []})
    assert normalized["talents"] == [
        {"text": "talent-a", "rating": GOOD, "locked": False, "source": None},
        {"text": "energy-c", "rating": "", "locked": False, "source": "100_examples"},
    ]
    assert not steps._validate_ch05_output(normalized, "step-2")


def test_compaction_removes_locked_from_profile_talents():
    from app.services.compaction import compact_profile

    profile = compact_profile([{
        "talents": [
            {"text": "talent-a", "rating": GOOD, "locked": True, "source": None},
            {"text": "energy-c", "rating": "", "locked": False, "source": "100_examples"},
        ]
    }])
    assert profile["talents"] == [
        {"text": "talent-a", "rating": GOOD, "source": None},
        {"text": "energy-c", "rating": "", "source": "100_examples"},
    ]


@pytest.mark.asyncio
async def test_ch05_two_step_http_cascade_and_profile(tmp_path, monkeypatch):
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
               VALUES ('ch05', 1, ?, 1, datetime('now'))""",
            (json.dumps(cfg, ensure_ascii=False),),
        )
        conn.execute(
            """INSERT INTO llm_roles
               (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES (?, 'psychologist', 'test', 'role', 'deepseek', 'deepseek-chat', 0.5, 1500, 1)""",
            (str(uuid.uuid4()),),
        )

    calls = []
    responses = [
        {"commentary": "evidence-a", "talents": [
            {"text": "talent-a", "locked": False},
            {"text": "calm-b", "locked": False},
        ]},
        {"user_manual": "manual-a", "talents": [
            {"text": "talent-a", "rating": GOOD, "locked": False},
            {"text": "calm-b", "rating": SOME, "locked": False},
            {"text": "energy-c", "rating": "", "locked": False},
        ]},
    ]
    import app.runtime.agent as agent_mod

    async def mock_call_llm(*args, **kwargs):
        calls.append(kwargs)
        return json.dumps(responses[len(calls) - 1], ensure_ascii=False)

    agent_mod.call_llm = mock_call_llm
    import app.main as main_mod
    reload(main_mod)

    answers1 = {f"q{index}": f"answer-{index}" for index in range(1, 6)}
    answers2 = {"reference_strengths": [{"text": "calm-b"}, {"text": "energy-c"}]}
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://test") as client:
        response = await client.post("/api/chapters/ch05/steps/step-1/run", json={"user_answers": answers1})
        assert response.status_code == 200, response.text
        response = await client.post("/api/chapters/ch05/steps/step-1/submit")
        assert response.status_code == 200, response.text
        response = await client.post("/api/chapters/ch05/steps/step-2/run", json={"user_answers": answers2})
        assert response.status_code == 200, response.text
        response = await client.post("/api/chapters/ch05/steps/step-2/submit")
        assert response.status_code == 200, response.text

    assert len(calls) == 2
    assert "CH05 MERGED TALENT CANDIDATES" in calls[1]["user"]
    with app.db.get_conn() as conn:
        row = conn.execute(
            """SELECT parsed_output FROM step_runs
               WHERE chapter_id='ch05' AND step_id='step-2' AND status='submitted'
               ORDER BY submitted_at DESC LIMIT 1"""
        ).fetchone()
        output = json.loads(row["parsed_output"])
        assert output["talents"] == [
            {"text": "talent-a", "rating": GOOD, "locked": False, "source": None},
            {"text": "calm-b", "rating": SOME, "locked": False, "source": None},
            {"text": "energy-c", "rating": "", "locked": False, "source": "100_examples"},
        ]
        profile_row = conn.execute("SELECT profile_json FROM learner_profiles WHERE user_id='local'").fetchone()
        profile = json.loads(profile_row[0])
        assert all("locked" not in item for item in profile["talents"])
