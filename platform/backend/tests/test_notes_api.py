"""Notes API — 4 endpoints × 2 types. (Recreated 2026-08-01 after being lost.)"""
import pytest


@pytest.mark.asyncio
async def test_create_and_list_standalone_note(client):
    payload = {"chapter_id": "c1", "note_type": "standalone", "content": "hello", "tags": ["a"]}
    r = await client.post("/api/notes", json=payload)
    assert r.status_code == 200
    nid = r.json()["id"]
    r = await client.get("/api/notes", params={"chapter_id": "c1"})
    notes = r.json()
    assert any(n["id"] == nid and n["content"] == "hello" and n["note_type"] == "standalone"
               for n in notes)


@pytest.mark.asyncio
async def test_create_selection_note_with_context(client):
    payload = {
        "chapter_id": "c1", "note_type": "selection",
        "content": "useful", "source_text": "原文片段",
        "context_before": "前文", "context_after": "后文", "tags": [],
    }
    r = await client.post("/api/notes", json=payload)
    assert r.status_code == 200
    nid = r.json()["id"]
    r = await client.get("/api/notes", params={"chapter_id": "c1", "note_type": "selection"})
    notes = r.json()
    assert len(notes) == 1
    assert notes[0]["source_text"] == "原文片段"
    assert notes[0]["context_before"] == "前文"
    assert notes[0]["context_after"] == "后文"


@pytest.mark.asyncio
async def test_update_and_delete_note(client):
    payload = {"chapter_id": "c1", "note_type": "selection", "content": "x", "source_text": "src"}
    nid = (await client.post("/api/notes", json=payload)).json()["id"]
    r = await client.put(f"/api/notes/{nid}", json={"content": "y"})
    assert r.status_code == 200
    r = await client.get("/api/notes", params={"chapter_id": "c1"})
    assert r.json()[0]["content"] == "y"
    r = await client.delete(f"/api/notes/{nid}")
    assert r.status_code == 200
    r = await client.get("/api/notes", params={"chapter_id": "c1"})
    assert r.json() == []


@pytest.mark.asyncio
async def test_invalid_note_type_rejected(client):
    payload = {"chapter_id": "c1", "note_type": "unknown", "content": "x"}
    r = await client.post("/api/notes", json=payload)
    assert r.status_code == 400
