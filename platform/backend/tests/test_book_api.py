"""Book API: chapter list, content 404, image 404, reading state round-trip."""
import pytest


@pytest.mark.asyncio
async def test_list_chapters_returns_at_least_one(client):
    r = await client.get("/api/book/chapters")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    # Hard-coded CHAPTERS list contains at least ch04
    assert any(ch["id"] == "ch04" for ch in body)


@pytest.mark.asyncio
async def test_unknown_chapter_404(client):
    r = await client.get("/api/book/chapters/no-such-chapter")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_unknown_chapter_content_404(client):
    r = await client.get("/api/book/chapters/no-such-chapter/content")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_image_404(client):
    r = await client.get("/api/book-images/ch04/missing.png")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_state_round_trip(client):
    r = await client.put(
        "/api/book/chapters/ch04/state",
        json={"scroll_position": 123.4, "last_step_id": "step-2"},
    )
    assert r.status_code == 200
    r = await client.get("/api/book/chapters/ch04/state")
    body = r.json()
    assert body["scroll_position"] == 123.4
    assert body["last_step_id"] == "step-2"


@pytest.mark.asyncio
async def test_chapter_config_endpoint_returns_steps(client):
    """Pre-seeded ch04 config should be reachable (handoff v2.0 决策 4)."""
    r = await client.get("/api/book/chapters/ch04/config")
    # Either returns the seeded config (200) or empty list (200) — never 500
    assert r.status_code == 200
    body = r.json()
    assert "chapter_id" in body
    assert "steps" in body


@pytest.mark.asyncio
async def test_post_chapter_config_creates_next_active_version(client):
    from app.db import get_conn
    import json

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active) VALUES (?,?,?,1)",
            ("ch01", 4, json.dumps({"chapter_id": "ch01", "steps": []})),
        )

    payload = {"chapter_id": "ch01", "steps": [{"step_id": "step-1"}]}
    r = await client.post("/api/book/chapters/ch01/config", json=payload)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "chapter_id": "ch01", "version": 5}

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT version, active, config_json FROM chapter_configs WHERE chapter_id = ? ORDER BY version",
            ("ch01",),
        ).fetchall()
    assert [(row["version"], row["active"]) for row in rows] == [(4, 0), (5, 1)]
    assert json.loads(rows[-1]["config_json"]) == payload


# -------- Phase A: multi-chapter discovery --------

@pytest.mark.asyncio
async def test_chapters_returns_all_10(client):
    """Phase A: scan discovers 10 chapters from chapter_html/ + chapter_md/."""
    r = await client.get("/api/book/chapters")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 10
    ids = {ch["id"] for ch in body}
    expected = {"preface", "ch01", "ch02", "ch03", "ch04", "ch05", "ch06", "ch07", "ch08", "questions"}
    assert ids == expected


@pytest.mark.asyncio
async def test_chapter_content_is_single_html(client):
    r = await client.get("/api/book/chapters/ch01/content")
    assert r.status_code == 200
    body = r.json()
    assert body["format"] == "html"
    assert len(body["pages"]) == 1
    page = body["pages"][0].lower()
    assert "<html" in page or "<body" in page


@pytest.mark.asyncio
async def test_preface_chapter_works(client):
    r = await client.get("/api/book/chapters/preface/content")
    assert r.status_code == 200
    assert r.json()["format"] == "html"


@pytest.mark.asyncio
async def test_questions_chapter_works(client):
    """'questions' has no HTML, but the chapter is still registered (has_md=True)."""
    r = await client.get("/api/book/chapters/questions")
    assert r.status_code == 200
    # Content endpoint may 404 (no HTML) — that's expected, the chapter is in the list
    assert any(ch["id"] == "questions" and ch["has_md"] for ch in (await client.get("/api/book/chapters")).json())


@pytest.mark.asyncio
async def test_ch04_uses_canonical_id(client):
    """After migration, ch4 is exposed with the canonical id 'ch04' (handoff v2.0 决策 4).
    The legacy '04-important' id is no longer accepted."""
    # Canonical id works
    r = await client.get("/api/book/chapters/ch04/content")
    assert r.status_code == 200
    body = r.json()
    assert body["chapter_id"] == "ch04"
    assert body["format"] == "html"

    # Legacy id returns 404 (alias removed)
    r = await client.get("/api/book/chapters/04-important/content")
    assert r.status_code == 404


# -------- Phase C: continue reading + progress --------

@pytest.mark.asyncio
async def test_last_reading_returns_latest(client):
    # No reading state yet
    r = await client.get("/api/book/last-reading")
    assert r.json() is None

    # Write two reading states
    await client.put("/api/book/chapters/ch01/state", json={"scroll_position": 10.0})
    await client.put("/api/book/chapters/ch02/state", json={"scroll_position": 20.0})

    r = await client.get("/api/book/last-reading")
    body = r.json()
    assert body["chapter_id"] == "ch02"
    assert body["scroll_position"] == 20.0


@pytest.mark.asyncio
async def test_chapters_include_has_steps_and_progress(client):
    # Fresh tmp DB: no configs yet -> all has_steps False
    r = await client.get("/api/book/chapters")
    body = r.json()
    assert all("has_steps" in ch for ch in body)
    assert all("progress_pct" in ch for ch in body)
    assert all(ch["has_steps"] is False for ch in body)

    # Seed a config for ch1 -> has_steps flips True
    from app.db import get_conn
    import json as _json
    with get_conn() as c:
        c.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active) VALUES (?,?,?,1)",
            ("ch01", 1, _json.dumps({"steps": [{"step_id": "s1"}]})),
        )
    r = await client.get("/api/book/chapters")
    ch1 = next(ch for ch in r.json() if ch["id"] == "ch01")
    assert ch1["has_steps"] is True
    assert ch1["total_steps"] == 1


@pytest.mark.asyncio
async def test_get_chapter_has_steps_matches_list(client):
    """Regression: get_chapter() must use the same canonical id as list_chapters()
    when checking _chapters_with_configs(), so ch04 renders as 3-col with step nav."""
    from app.db import get_conn
    import json as _json
    with get_conn() as c:
        c.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active) VALUES (?,?,?,1)",
            ("ch04", 1, _json.dumps({"steps": [{"step_id": "s1"}]})),
        )
    # both list and get must agree
    r = await client.get("/api/book/chapters")
    ch4_list = next(ch for ch in r.json() if ch["id"] == "ch04")
    r = await client.get("/api/book/chapters/ch04")
    ch4_get = r.json()
    assert ch4_list["has_steps"] is True
    assert ch4_get["has_steps"] is True
