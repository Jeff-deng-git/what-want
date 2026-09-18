"""M4.3: ch07 cross-chapter profile reads (mentor_hooks.references).

    ch07 config declares mentor_hooks.references = [talents, likes, work_purpose, values].
When ch07 step-1 runs, the assembler pulls these fields from learner_profiles
(Q2 handoff: cross-chapter anchor reads from compressed profile).

    This test seeds an existing profile with values from ch04/ch05/ch06, runs ch07,
and verifies the prompt contains the seeded profile fields.
"""
import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")

CHAPTERS_ROOT = r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters"


def _load_cfg(chapter_id):
    p = os.path.join(CHAPTERS_ROOT, "chapter_config_" + chapter_id + ".json")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_m4_ch07_prompts_contain_profile_references(tmp_path, monkeypatch):
    """ch07 step-1 prompt contains cross-chapter profile fields."""
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
    cfg = _load_cfg("ch07")
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, ?, ?, 1, datetime('now'))",
            ("ch07", 1, json.dumps(cfg)),
        )
        conn.execute(
            """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES (?, 'career_counselor', 'test', 'role', 'deepseek', 'deepseek-chat', 0.5, 1500, 1)""",
            (str(uuid.uuid4()),),
        )
    # Seed the final ch07 upstream profile fields.
    seeded_profile = {
        "work_purpose": "help people find direction",
        "talents": ["empathy framing", "structured writing"],
        "likes": [{"field": "deep conversation", "aspects": [{"text": "exploring ideas"}], "linked_strengths": [], "sources": [], "locked": False}],
        "values": ["help others grow", "act with integrity"],
        "current_chapter": "ch04",
        "open_questions": [],
    }
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO learner_profiles (user_id, profile_json) VALUES (?, ?)",
            ("local", json.dumps(seeded_profile)),
        )
    captured = {}

    async def capturing_llm(*, system, user, **kwargs):
        captured["system"] = system
        captured["user"] = user
        return json.dumps({"intersection": ["helping via conversation"]})
    import app.runtime.agent as agent_mod
    agent_mod.call_llm = capturing_llm
    await agent_mod.run_step("ch07", "step-1", ["my answer"], user_id="local")
    # The system prompt should contain the cross-chapter profile block.
    system = captured["system"]
    assert "learner cross-chapter profile" in system, (
        "ch07 prompt should include profile block (got: " + system[:600] + ")"
    )
    # Verify the four hook references are present.
    for f in ["work_purpose", "talents", "likes", "values"]:
        assert f in system, "ch07 prompt missing hook reference field " + f
    # Verify the seeded content is present.
    assert "help people find direction" in system, "work_purpose content missing"
    assert "empathy framing" in system, "talents content missing"
    assert "deep conversation" in system, "likes content missing"


@pytest.mark.asyncio
async def test_m4_ch02_prompts_contain_profile_references(tmp_path, monkeypatch):
    """ch02 step-1 prompt reads ch01 misconceptions_cleared from profile."""
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
    cfg = _load_cfg("ch02")
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, ?, ?, 1, datetime('now'))",
            ("ch02", 1, json.dumps(cfg)),
        )
        conn.execute(
            """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES (?, 'psychologist', 'test', 'role', 'deepseek', 'deepseek-chat', 0.5, 1500, 1)""",
            (str(uuid.uuid4()),),
        )
    seeded_profile = {
        "misconceptions_cleared": ["must have unique right answer"],
        "current_chapter": "ch01",
        "open_questions": [],
    }
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO learner_profiles (user_id, profile_json) VALUES (?, ?)",
            ("local", json.dumps(seeded_profile)),
        )
    captured = {}

    async def capturing_llm(*, system, user, **kwargs):
        captured["system"] = system
        captured["user"] = user
        return json.dumps({})
    import app.runtime.agent as agent_mod
    agent_mod.call_llm = capturing_llm
    await agent_mod.run_step("ch02", "step-1", ["my answer"], user_id="local")
    system = captured["system"]
    assert "misconceptions_cleared" in system, (
        "ch02 prompt should read ch01 misconceptions_cleared (got: " + system[:600] + ")"
    )
    assert "must have unique right answer" in system, "ch01 misconceptions content missing"
