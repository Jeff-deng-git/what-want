"""step_runner: parse-failure must persist status='failed' + error message."""
import json
import pytest
import pytest_asyncio

from importlib import reload
import app.config, app.db


@pytest_asyncio.fixture
async def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with app.db.get_conn() as c:
        c.execute(
            "INSERT INTO llm_roles (id,name,description,system_prompt,provider,model) "
            "VALUES (?,?,?,?,?,?)",
            ("r1", "测试", "d", "s", "deepseek", "deepseek-chat"),
        )
        cfg = {
            "chapter_id": "c1",
            "steps": [{
                "step_id": "step-1",
                "title": "t",
                "llm_op": {
                    "role_id": "r1",
                    "prompt_template": "hi",
                    "output_schema": {
                        "type": "structured",
                        "fields": [{"name": "commentary", "type": "markdown"}],
                    },
                },
            }],
        }
        c.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active) "
            "VALUES (?,?,?,1)",
            ("c1", 1, json.dumps(cfg)),
        )
    return "c1"


@pytest.mark.asyncio
async def test_run_step_records_error_on_parse_failure(fresh_db, monkeypatch):
    async def fake_call(*a, **kw):
        return "not json at all"

    monkeypatch.setattr("app.services.step_runner.call_llm", fake_call)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")

    from app.services.step_runner import StepRunner
    runner = StepRunner()
    role_row = {
        "id": "r1", "provider": "deepseek", "model": "deepseek-chat",
        "system_prompt": "x", "temperature": 0.7, "max_tokens": 2000,
    }
    # run_step should NOT raise on parse failure; instead return status='failed'
    result = await runner.run_step(
        "c1", "step-1", user_answers=[], role_row=role_row,
    )
    assert result.get("status") == "failed"
    assert "parse_error" in result["parsed"]
    with app.db.get_conn() as c:
        run = c.execute(
            "SELECT status, error FROM step_runs WHERE step_id='step-1' "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    assert run is not None
    assert run["status"] == "failed"
    assert "JSON" in (run["error"] or "") or "parse" in (run["error"] or "").lower()


@pytest.mark.asyncio
async def test_run_step_persists_saved_on_success(fresh_db, monkeypatch):
    async def fake_call(*a, **kw):
        return json.dumps({"commentary": "hello world"})

    monkeypatch.setattr("app.services.step_runner.call_llm", fake_call)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")

    from app.services.step_runner import StepRunner
    runner = StepRunner()
    role_row = {
        "id": "r1", "provider": "deepseek", "model": "deepseek-chat",
        "system_prompt": "x", "temperature": 0.7, "max_tokens": 2000,
    }
    result = await runner.run_step(
        "c1", "step-1", user_answers=[{"question_id": "q1", "text": "hi", "answer": "world"}],
        role_row=role_row,
    )
    assert result.get("status") in (None, "saved")
    with app.db.get_conn() as c:
        run = c.execute(
            "SELECT status, parsed_output, error FROM step_runs WHERE step_id='step-1' "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    assert run["status"] == "saved"
    assert run["error"] in (None, "")
    parsed = json.loads(run["parsed_output"])
    assert parsed["commentary"] == "hello world"
