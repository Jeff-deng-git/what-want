"""ch01 end-to-end smoke as a pytest (mocked LLM).

Verifies the runtime refactor path: draft -> run -> submit -> compaction.
LLM is monkey-patched (sandbox blocks deepseek). Real LLM testing requires
network access and a valid DEEPSEEK_API_KEY.
"""
import json
import os
import tempfile
import uuid

import pytest

CFG_PATH = r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch01.json"


@pytest.fixture
def fresh_app(tmp_path, monkeypatch):
    db = tmp_path / "ww.db"
    monkeypatch.setenv("WW_DB_PATH", str(db))
    from importlib import reload
    import app.config
    import app.db
    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, ?, ?, 1, datetime('now'))",
            ("ch01", 1, json.dumps(cfg)),
        )
        conn.execute(
            """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (str(uuid.uuid4()), "career_counselor", "test",
             "You are a career counselor.", "deepseek", "deepseek-chat", 0.5, 1500),
        )
    # Patch the LLM call BEFORE reloading app.main so the module binds to the mock
    import app.runtime.agent as agent_mod
    canned = json.dumps({
        "commentary": "基于本章正文解释误区1",
        "misconceptions_cleared": ["must have unique right answer"],
        "external_voices": ["dad said choose right"],
    })

    async def mock_call_llm(*args, **kwargs):
        return canned
    agent_mod.call_llm = mock_call_llm
    import app.main as main_mod
    reload(main_mod)
    yield main_mod.app


@pytest.mark.asyncio
async def test_ch01_e2e_draft_run_submit_compacts(fresh_app):
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=fresh_app), base_url="http://test") as ac:
        body = {"user_answers": ["I ticked (1) and (3)."]}
        r = await ac.post("/api/chapters/ch01/steps/step-1/draft", json=body)
        assert r.status_code == 200, r.text
        run_id = r.json()["id"]
        r = await ac.post("/api/chapters/ch01/steps/step-1/run", json=body)
        assert r.status_code == 200, r.text
        parsed = r.json()["parsed_output"]
        assert "misconceptions_cleared" in parsed
        assert "commentary" in parsed
        assert r.json()["role_id"] == "career_counselor"
        r = await ac.post("/api/chapters/ch01/steps/step-1/submit")
        assert r.status_code == 200, r.text
        assert r.json()["compacted"] is True
    import app.db
    with app.db.get_conn() as conn:
        run = conn.execute("SELECT status, role_id FROM step_runs WHERE id = ?", (run_id,)).fetchone()
        assert run["status"] == "submitted"
        assert run["role_id"] == "career_counselor"
        prof = conn.execute("SELECT profile_json FROM learner_profiles WHERE user_id = 'local'").fetchone()
        assert prof is not None
        parsed = json.loads(prof["profile_json"])
        assert parsed["current_chapter"] == "ch01"
        assert "misconceptions_cleared" in parsed


@pytest.mark.asyncio
async def test_ch01_run_rejects_invalid_input_schema(fresh_app):
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=fresh_app), base_url="http://test") as ac:
        body = {"user_answers": {"misconceptions": {"checked_ids": ["not-a-real-misconception"], "external_voices": {}}}}
        response = await ac.post("/api/chapters/ch01/steps/step-1/run", json=body)
        assert response.status_code == 422, response.text
        detail = response.json()["detail"]
        assert detail["detail"] == "schema validation failed"
        assert "unknown id" in detail["errors"][0]
@pytest.mark.asyncio
async def test_ch01_run_uses_exercises_schema_path(fresh_app):
    """Sanity: ch01 run_step works without role_id (Option B path is unconditional)."""
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=fresh_app), base_url="http://test") as ac:
        body = {"user_answers": ["a"]}
        r = await ac.post("/api/chapters/ch01/steps/step-1/run", json=body)
        assert r.status_code == 200, "Option B path must not require role_id"


@pytest.mark.asyncio
async def test_ch01_run_after_submit_preserves_submitted_history(fresh_app):
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=fresh_app), base_url="http://test") as ac:
        first_body = {"user_answers": ["first submitted answer"]}
        first_run = await ac.post("/api/chapters/ch01/steps/step-1/run", json=first_body)
        assert first_run.status_code == 200, first_run.text
        first_id = first_run.json()["id"]

        submitted = await ac.post("/api/chapters/ch01/steps/step-1/submit")
        assert submitted.status_code == 200, submitted.text

        second_body = {"user_answers": ["second answer"]}
        second_run = await ac.post("/api/chapters/ch01/steps/step-1/run", json=second_body)
        assert second_run.status_code == 200, second_run.text
        second_id = second_run.json()["id"]
        assert second_id != first_id

    import app.db
    with app.db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, status, user_answers FROM step_runs WHERE chapter_id = 'ch01' AND step_id = 'step-1' ORDER BY created_at, rowid"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["id"] == first_id
        assert rows[0]["status"] == "submitted"
        assert "first submitted answer" in rows[0]["user_answers"]
        assert rows[1]["id"] == second_id
        assert rows[1]["status"] == "saved"
        assert "second answer" in rows[1]["user_answers"]

@pytest.mark.asyncio
async def test_ch01_submitted_output_cannot_be_edited(fresh_app):
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=fresh_app), base_url="http://test") as ac:
        run_response = await ac.post("/api/chapters/ch01/steps/step-1/run", json={"user_answers": ["answer"]})
        assert run_response.status_code == 200, run_response.text
        original = run_response.json()["parsed_output"]
        submitted = await ac.post("/api/chapters/ch01/steps/step-1/submit")
        assert submitted.status_code == 200, submitted.text

        edit_response = await ac.put(
            "/api/chapters/ch01/steps/step-1/output",
            json={"parsed_output": {"tampered": True}},
        )
        assert edit_response.status_code == 409, edit_response.text

        current = await ac.get("/api/chapters/ch01/steps/step-1")
        assert current.status_code == 200, current.text
        assert json.loads(current.json()["current_run"]["parsed_output"]) == original


@pytest.mark.asyncio
async def test_ch01_empty_llm_response_cannot_be_saved_or_submitted(fresh_app):
    import app.runtime.agent as agent_mod

    async def empty_call(*args, **kwargs):
        return ""

    agent_mod.call_llm = empty_call
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=fresh_app), base_url="http://test") as ac:
        body = {"user_answers": ["a"]}
        r = await ac.post("/api/chapters/ch01/steps/step-1/run", json=body)
        assert r.status_code == 502, r.text
        r = await ac.post("/api/chapters/ch01/steps/step-1/submit")
        assert r.status_code == 409, r.text
