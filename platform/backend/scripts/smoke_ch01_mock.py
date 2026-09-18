"""All 8 chapters end-to-end smoke (mocked LLM).

Use this script to verify the runtime refactor for ch01:
1. seed ch01 config + career_counselor role into a temp DB
2. POST /api/chapters/ch01/steps/step-1/draft
3. POST /api/chapters/ch01/steps/step-1/run (mocked LLM)
4. POST /api/chapters/ch01/steps/step-1/submit
5. assert step_runs + learner_profiles were populated

Run from backend dir:
    python scripts/smoke_ch01_mock.py

Sandbox note: deepseek API is unreachable from Codex sandbox, so this
monkey-patches app.runtime.agent.call_llm with a canned JSON response.
Replace the monkey-patch with the real provider to test live LLM quality.
"""
import asyncio
import json
import os
import sys
import tempfile
import uuid

TMP = tempfile.mkdtemp(prefix="ww_smoke_")
os.environ["WW_DB_PATH"] = os.path.join(TMP, "ww.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from importlib import reload
import app.config  # noqa
import app.db
reload(app.config)
reload(app.db)
app.db.init_db()

CFG_PATH = r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch01.json"
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
        (str(uuid.uuid4()), "career_counselor", "smoke role",
         "You are a career counselor.",
         "deepseek", "deepseek-chat", 0.5, 1500),
    )

import app.runtime.agent as agent_mod
CANNED = json.dumps({
    "misconceptions_cleared": ["must have unique right answer"],
    "external_voices": ["dad said choose right or you waste your life"],
})

async def mock_call_llm(*args, **kwargs):
    return CANNED
agent_mod.call_llm = mock_call_llm

from httpx import AsyncClient, ASGITransport
import app.main as main_mod
reload(main_mod)


async def main():
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://test") as ac:
        body = {"user_answers": ["I ticked (1) and (3). My dad said X."]}
        r = await ac.post("/api/chapters/ch01/steps/step-1/draft", json=body)
        assert r.status_code == 200, r.text
        run_id = r.json()["id"]
        r = await ac.post("/api/chapters/ch01/steps/step-1/run", json=body)
        assert r.status_code == 200, r.text
        assert "misconceptions_cleared" in r.json()["parsed_output"]
        r = await ac.post("/api/chapters/ch01/steps/step-1/submit")
        assert r.status_code == 200, r.text
        assert r.json()["compacted"] is True
    with app.db.get_conn() as conn:
        run = conn.execute("SELECT status, role_id FROM step_runs WHERE id = ?", (run_id,)).fetchone()
        assert run["status"] == "submitted"
        assert run["role_id"] == "career_counselor"
        prof = conn.execute("SELECT profile_json FROM learner_profiles WHERE user_id = 'local'").fetchone()
        assert prof is not None
        parsed = json.loads(prof["profile_json"])
        assert parsed["current_chapter"] == "ch01"
        assert "misconceptions_cleared" in parsed
    print("smoke OK: step_runs + learner_profiles populated for ch01")


if __name__ == "__main__":
    asyncio.run(main())

