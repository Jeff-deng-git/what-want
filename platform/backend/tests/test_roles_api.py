"""LLM roles CRUD + enabled filter."""
import pytest


@pytest.mark.asyncio
async def test_role_crud_and_enabled_filter(client):
    payload = {
        "name": "测试", "description": "d", "system_prompt": "s",
        "provider": "deepseek", "model": "deepseek-chat",
    }
    r = await client.post("/api/roles", json=payload)
    assert r.status_code == 200
    rid = r.json()["id"]

    r = await client.get("/api/roles")
    assert any(x["id"] == rid for x in r.json())

    r = await client.get("/api/roles", params={"enabled_only": "true"})
    assert any(x["id"] == rid for x in r.json())

    r = await client.put(f"/api/roles/{rid}", json={"enabled": False})
    assert r.status_code == 200

    r = await client.get("/api/roles", params={"enabled_only": "true"})
    assert not any(x["id"] == rid for x in r.json())

    r = await client.delete(f"/api/roles/{rid}")
    assert r.status_code == 200
    r = await client.get("/api/roles")
    assert not any(x["id"] == rid for x in r.json())


@pytest.mark.asyncio
async def test_role_put_rejects_empty_update(client):
    payload = {
        "name": "x", "description": "d", "system_prompt": "s",
        "provider": "deepseek", "model": "deepseek-chat",
    }
    rid = (await client.post("/api/roles", json=payload)).json()["id"]
    r = await client.put(f"/api/roles/{rid}", json={})
    assert r.status_code == 400
