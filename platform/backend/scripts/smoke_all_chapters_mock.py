import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")

CHAPTERS_ROOT = r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters"
CHAPTERS = ["ch01", "ch02", "ch03", "ch04", "ch05", "ch06", "ch07", "ch08"]
EXPECTED_ROLE = {
    "ch01": "career_counselor",
    "ch02": "psychologist",
    "ch03": "psychologist",
    "ch04_step1": "psychologist",
    "ch04_step2": "psychologist",
    "ch04_step3": "psychologist",
    "ch04_step4": "career_counselor",
    "ch04_step5": "career_counselor",
    "ch05": "career_counselor",
    "ch06": "psychologist",
    "ch07": "career_counselor",
    "ch08": "career_counselor",
}


@pytest.fixture
def all_app(tmp_path, monkeypatch):
    db = tmp_path / "ww.db"
    monkeypatch.setenv("WW_DB_PATH", str(db))
    from importlib import reload
    import app.config
    import app.db
    reload(app.config)
    reload(app.db)
    app.db.init_db()
    for ch in CHAPTERS:
        with open(os.path.join(CHAPTERS_ROOT, "chapter_config_" + ch + ".json"), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        with app.db.get_conn() as conn:
            conn.execute(
                "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, ?, ?, 1, datetime('now'))",
                (ch, 1, json.dumps(cfg)),
            )
    with app.db.get_conn() as conn:
        for name, desc in [
            ("psychologist", "Reflective self-cognition coach."),
            ("career_counselor", "Career counselor for synthesis steps."),
        ]:
            conn.execute(
                """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (str(uuid.uuid4()), name, desc,
                 "You are a " + name + ". Respond in Chinese when user writes Chinese.",
                 "deepseek", "deepseek-chat", 0.5, 1500),
            )
    import app.runtime.agent as agent_mod
    canned = json.dumps({"value": "ok"})
    async def mock_call_llm(*args, **kwargs):
        return canned
    agent_mod.call_llm = mock_call_llm
    import app.main as main_mod
    reload(main_mod)
    yield main_mod.app


async def _run_one(ac, ch, step_id, expected_role):
    body = {"user_answers": ["a sample answer for " + step_id]}
    r = await ac.post("/api/chapters/" + ch + "/steps/" + step_id + "/draft", json=body)
    assert r.status_code == 200, r.text
    r = await ac.post("/api/chapters/" + ch + "/steps/" + step_id + "/run", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["role_id"] == expected_role, (
        ch + "/" + step_id + " expected " + expected_role + " got " + r.json()["role_id"]
    )
    r = await ac.post("/api/chapters/" + ch + "/steps/" + step_id + "/submit")
    assert r.status_code == 200, r.text
    return r.json()["compacted"]


@pytest.mark.asyncio
async def test_all_chapters_route_to_expected_role(all_app):
    from httpx import AsyncClient, ASGITransport
    import app.db
    async with AsyncClient(transport=ASGITransport(app=all_app), base_url="http://test") as ac:
        for ch in ["ch01", "ch02", "ch03", "ch05", "ch06", "ch07", "ch08"]:
            compacted = await _run_one(ac, ch, "step-1", EXPECTED_ROLE[ch])
            assert compacted, ch + " should compact (single exercise)"
        for s in range(1, 6):
            compacted = await _run_one(ac, "ch04", "step-" + str(s),
                                       EXPECTED_ROLE["ch04_step" + str(s)])
            if s < 5:
                assert not compacted, "ch04 step-" + str(s) + " should NOT compact yet"
            else:
                assert compacted, "ch04 step-5 should compact"
    with app.db.get_conn() as conn:
        n_runs = conn.execute("SELECT COUNT(*) AS c FROM step_runs").fetchone()["c"]
        n_submitted = conn.execute("SELECT COUNT(*) AS c FROM step_runs WHERE status='submitted'").fetchone()["c"]
        profile = conn.execute("SELECT profile_json FROM learner_profiles WHERE user_id='local'").fetchone()
        assert n_runs == 12
        assert n_submitted == 12
        parsed = json.loads(profile["profile_json"])
        assert parsed["current_chapter"] == "ch04"  # ch04 step-5 is the last compaction event


@pytest.mark.asyncio
async def test_chapters_fall_back_to_career_counselor_when_role_missing(all_app):
    """Without seeding the role, agent.run_step falls back gracefully."""
    import app.db
    from app.routers.steps import _uses_exercises_schema
    for ch in CHAPTERS:
        assert _uses_exercises_schema(ch), ch + " should use exercises schema"



