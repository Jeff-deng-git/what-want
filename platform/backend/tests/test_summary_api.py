"""AI summary API: GET cached, POST regenerate (mock LLM).

Note: get_chapter_md() reads real chapter_md/ on disk (independent of the tmp
test DB), so ch1's markdown is available during tests.
"""
import json
import sys
import uuid

import pytest

sys.path.insert(0, r'D:\AI_Project\What_Want\platform\backend')


def _seed_summary_roles():
    """Seed the summary role so agent.run_summary can resolve it."""
    from app.db import get_conn
    with get_conn() as c:
        c.execute(
            """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES (?, 'summary', 'Book editor.', 'You are a book editor.', 'deepseek', 'deepseek-chat', 0.5, 2000, 1)""",
            (str(uuid.uuid4()),),
        )


async def _get_summary(client, chapter_id):
    r = await client.get(f"/api/chapters/{chapter_id}/summary")
    assert r.status_code == 200
    return r.json()


@pytest.mark.asyncio
async def test_summary_returns_null_before_generate(client):
    body = await _get_summary(client, "ch01")
    assert body["summary"] is None


@pytest.mark.asyncio
async def test_summary_regenerate_mock_llm(client, monkeypatch):
    """M3.3: summary routes through agent.run_summary."""
    _seed_summary_roles()
    from app.runtime import agent as agent_mod
    async def fake_call(*a, **kw):
        return json.dumps({
            "summary": "第一章讲5种误区。",
            "core_concepts": ["误区是思维框架问题", "现在最想做的事", "兴趣渐进式"],
            "key_process": ["破除误区", "区分三圈"],
        })
    agent_mod.call_llm = fake_call
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")

    r = await client.post("/api/chapters/ch01/summary/regenerate")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["summary"] == "第一章讲5种误区。"
    assert len(body["summary"]["core_concepts"]) == 3

    # Now cached
    cached = await _get_summary(client, "ch01")
    assert cached["summary"]["summary"] == "第一章讲5种误区。"


@pytest.mark.asyncio
async def test_summary_regenerate_missing_md_404(client):
    r = await client.post("/api/chapters/no-such/summary/regenerate")
    assert r.status_code == 404
