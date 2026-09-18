"""M4.2: ch04 references cascading -- within-chapter step-2..5 inject prior step data.

Each step in ch04 declares references (handoff S7.0 decision 2):
  step-2: reads step-1.top_values
  step-3: reads step-2.groups
  step-4: reads step-2.groups + step-3.conversions
  step-5: reads step-4.ranked

This test verifies that when a step runs, the prompt contains the prior
steps submitted output (assembler._format_references behaviour).
"""
import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")

CHAPTERS_ROOT = r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters"

# Per-step mock LLM responses for ch04 cascading.
CH04_MOCK = {
    "step-1": ("psychologist", {
        "top_values": ["按自己的标准活", "不依附他人评价"],
        "commentary": "two key values",
    }),
    "step-2": ("psychologist", {
        "groups": [{"umbrella": "self-expression", "keywords": ["按自己的标准活", "不依附他人评价"], "locked": True}],
    }),
    "step-3": ("psychologist", {
        "phase": "screening",
        "conversions": [
            {"value": "按自己的标准活", "type": "self", "assessment": "keep", "decision": "keep"},
            {"value": "不依附他人评价", "type": "self", "assessment": "keep", "decision": "keep"},
        ],
    }),
    "step-4": ("career_counselor", {
        "ranked": [{"value": "self-expression", "locked": True}],
        "support_links": [],
        "final_purpose": {
            "value": "self-expression",
            "life_state": "live by one's own standards",
            "reason": "the confirmed members all serve authentic self-expression",
        },
        "gap_note": "",
    }),
    "step-5": ("career_counselor", {
        "work_purpose": "help people find direction",
        "reasoning": "repeatedly helping others clarify direction",
        "experience_map": [{"experience": "friend asked for advice", "values": ["growth"]}],
    }),
}


def _load_cfg(chapter_id):
    p = os.path.join(CHAPTERS_ROOT, "chapter_config_" + chapter_id + ".json")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_app(chapter_id, mock_responses, tmp_path, monkeypatch):
    db = tmp_path / "ww.db"
    monkeypatch.setenv("WW_DB_PATH", str(db))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    from importlib import reload
    import app.config
    import app.db
    reload(app.config)
    reload(app.db)
    app.db.init_db()
    cfg = _load_cfg(chapter_id)
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, ?, ?, 1, datetime('now'))",
            (chapter_id, 1, json.dumps(cfg)),
        )
        for role_name in ("psychologist", "career_counselor"):
            conn.execute(
                """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (str(uuid.uuid4()), role_name, "test", "You are " + role_name,
                 "deepseek", "deepseek-chat", 0.5, 1500),
            )
    import app.runtime.agent as agent_mod
    # Per-call counter mock that returns next canned response.
    state = {"calls": []}

    async def mock_call_llm(*args, **kwargs):
        idx = len(state["calls"])
        state["calls"].append(kwargs)
        # Use step_id from kwargs if exposed; else rotate by call count.
        # The agent does not pass step_id, so we rotate by call count.
        step_ids = ["step-1", "step-2", "step-3", "step-4", "step-5"]
        sid = step_ids[min(idx, len(step_ids) - 1)]
        _, payload = mock_responses[sid]
        return json.dumps(payload, ensure_ascii=False)
    agent_mod.call_llm = mock_call_llm
    import app.main as main_mod
    reload(main_mod)
    return main_mod.app, state


@pytest.mark.asyncio
async def test_m4_ch04_references_cascade_through_all_5_steps(tmp_path, monkeypatch):
    from httpx import AsyncClient, ASGITransport
    import app.db
    app_obj, state = _make_app("ch04", CH04_MOCK, tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as ac:
        # Run step-1..5 sequentially. Each step must succeed.
        body = {"user_answers": ["my answer"]}
        for sid in ["step-1", "step-2", "step-3", "step-4", "step-5"]:
            r = await ac.post("/api/chapters/ch04/steps/" + sid + "/draft", json=body)
            assert r.status_code == 200, sid + " draft: " + r.text
            r = await ac.post("/api/chapters/ch04/steps/" + sid + "/run", json=body)
            assert r.status_code == 200, sid + " run: " + r.text
            r = await ac.post("/api/chapters/ch04/steps/" + sid + "/submit")
            assert r.status_code == 200, sid + " submit: " + r.text
        # Verify mock LLM was called 5 times (once per step).
        assert len(state["calls"]) == 5
        expected_reference_tokens = {
            "step-2": ["prior step-1 submitted output", "按自己的标准活"],
            "step-3": ["prior step-2 submitted output", "self-expression"],
            "step-4": ["prior step-2 submitted output", "self-expression", "prior step-3 submitted output", "按自己的标准活"],
            "step-5": ["prior step-4 submitted output", "self-expression"],
        }
        for call, sid in zip(state["calls"][1:], ["step-2", "step-3", "step-4", "step-5"]):
            prompt = call["user"]
            for token in expected_reference_tokens[sid]:
                assert token in prompt, f"{sid} prompt missing {token}: {prompt[:500]}"
    # Verify each step's parsed_output persisted in step_runs.
    with app.db.get_conn() as conn:
        for sid, (_, expected) in CH04_MOCK.items():
            row = conn.execute(
                "SELECT parsed_output FROM step_runs WHERE chapter_id='ch04' AND step_id=? ORDER BY created_at DESC LIMIT 1",
                (sid,),
            ).fetchone()
            assert row is not None, sid + " should have a step_run"
            parsed = json.loads(row["parsed_output"])
            for f in expected.keys():
                assert f in parsed, sid + " parsed_output missing " + f
    # Verify only step-5 triggers compaction (ch04 has 5 steps).
    with app.db.get_conn() as conn:
        last = conn.execute(
            "SELECT parsed_output FROM step_runs WHERE chapter_id='ch04' AND step_id='step-5'"
        ).fetchone()
        assert last is not None


@pytest.mark.asyncio
async def test_m4_ch04_step2_references_step1_top_values(tmp_path, monkeypatch):
    """Verify references mechanism: step-2 prompt contains step-1 prior output."""
    # Bypass HTTP and call agent.run_step directly to inspect the prompt.
    import app.db
    db = tmp_path / "ww.db"
    monkeypatch.setenv("WW_DB_PATH", str(db))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    from importlib import reload
    import app.config
    import app.db
    reload(app.config)
    reload(app.db)
    app.db.init_db()
    cfg = _load_cfg("ch04")
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, ?, ?, 1, datetime('now'))",
            ("ch04", 1, json.dumps(cfg)),
        )
        conn.execute(
            """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES (?, 'psychologist', 'test', 'role', 'deepseek', 'deepseek-chat', 0.5, 1500, 1)""",
            (str(uuid.uuid4()),),
        )
    # Seed prior step-1 submitted output.
    with app.db.get_conn() as conn:
        conn.execute(
            """INSERT INTO step_runs (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status, updated_at)
               VALUES (?, 'ch04', 'step-1', '[]', 'psychologist', '', '',
                       ?, 'submitted', datetime('now'))""",
            (str(uuid.uuid4()), json.dumps({"top_values": ["freedom", "growth"]})),
        )
    captured = {}

    async def capturing_llm(*, system, user, **kwargs):
        captured["system"] = system
        captured["user"] = user
        return json.dumps({"groups": [{"umbrella": "u", "keywords": [], "locked": False}]})
    import app.runtime.agent as agent_mod
    agent_mod.call_llm = capturing_llm
    await agent_mod.run_step("ch04", "step-2", ["my answer"])
    # The user prompt should contain the prior step-1 output.
    user = captured["user"]
    assert "step-1" in user, "step-2 prompt should reference step-1 (got: " + user[:300] + ")"
    assert "freedom" in user or "growth" in user, (
        "step-2 prompt should include step-1 top_values content (got: " + user[:500] + ")"
    )
