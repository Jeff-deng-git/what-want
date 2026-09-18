"""Mentor chat API: send (mock LLM), history order, clear."""
import json
import sys
import uuid

import pytest

sys.path.insert(0, r'D:\AI_Project\What_Want\platform\backend')


def _seed_chat_roles():
    """Seed llm_roles for chat e2e tests (M3.3 mentor path needs the DB-backed role)."""
    from app.db import get_conn
    seed = [
        ("mentor", "Liu laoshi.", "You are Liu laoshi. Socratic."),
        ("career_counselor", "Career counselor.", "You are a career counselor."),
        ("psychologist", "Self coach.", "You are a reflective coach."),
    ]
    with get_conn() as c:
        for name, desc, sp in seed:
            c.execute(
                """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (str(uuid.uuid4()), name, desc, sp, "deepseek", "deepseek-chat", 0.5, 1500),
            )


@pytest.mark.asyncio
async def test_chat_send_persists_both(client, monkeypatch):
    """M3.3: chat routes through agent.run_mentor, which calls agent.call_llm."""
    _seed_chat_roles()
    from app.runtime import agent as agent_mod
    async def fake_call(*a, **kw):
        return "你好，我们可以聊聊本章内容。"
    agent_mod.call_llm = fake_call

    r = await client.post("/api/chapters/ch01/chat/send", json={"content": "我最近很迷茫"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["role"] == "user"
    assert body["user"]["content"] == "我最近很迷茫"
    assert body["mentor"]["role"] == "mentor"

    # History: both present, user first
    r = await client.get("/api/chapters/ch01/chat")
    msgs = r.json()
    assert [m["role"] for m in msgs] == ["user", "mentor"]


@pytest.mark.asyncio
async def test_chat_empty_content_400(client):
    r = await client.post("/api/chapters/ch01/chat/send", json={"content": "   "})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_chat_timeout_returns_gateway_timeout(client, monkeypatch):
    _seed_chat_roles()
    from app.runtime import agent as agent_mod
    from app.services.llm_client import LLMTimeoutError

    async def timeout_call(*args, **kwargs):
        assert kwargs["timeout"] == agent_mod.MENTOR_LLM_TIMEOUT_SECONDS
        assert kwargs["max_tokens"] == 4000
        assert kwargs["reasoning_retry"] is False
        raise LLMTimeoutError("LLM provider timed out after 120s")

    monkeypatch.setattr(agent_mod, "call_llm", timeout_call)
    response = await client.post("/api/chapters/ch01/chat/send", json={"content": "hello"})

    assert response.status_code == 504
    assert "timed out after 120s" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_clear(client):
    _seed_chat_roles()
    from app.runtime import agent as agent_mod
    async def fake_call(*a, **kw):
        return "ok"
    agent_mod.call_llm = fake_call
    await client.post("/api/chapters/ch01/chat/send", json={"content": "x"})
    # simpler: directly insert a row, then clear
    from app.db import get_conn
    import uuid
    with get_conn() as c:
        c.execute(
            "INSERT INTO chapter_chat (id, chapter_id, role, content) VALUES (?,?,?,?)",
            (str(uuid.uuid4()), "ch01", "user", "直接插入"),
        )
    r = await client.get("/api/chapters/ch01/chat")
    assert len(r.json()) >= 1
    r = await client.delete("/api/chapters/ch01/chat")
    assert r.status_code == 200
    r = await client.get("/api/chapters/ch01/chat")
    assert r.json() == []


@pytest.mark.asyncio
async def test_chat_missing_md_404(client, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")
    r = await client.post("/api/chapters/no-such/chat/send", json={"content": "hi"})
    assert r.status_code == 404
