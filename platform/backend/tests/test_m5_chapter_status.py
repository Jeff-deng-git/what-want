"""M5.1: chapter_status endpoint.

GET /api/book/chapters/{chapter_id}/status returns:
  - chapter_id, is_submitted, submitted_steps, submitted_count, total_steps
  - lock_state (only for ch07 today): upstream ch04/ch05/ch06 status

Tests cover:
  1. Empty chapter -> is_submitted=False, total_steps > 0, no submitted_steps
  2. Partially submitted -> is_submitted=False, submitted_count < total_steps
  3. Fully submitted -> is_submitted=True
  4. ch07 lock_state.ready is False when ch04/ch05/ch06 are not submitted
  5. ch07 lock_state.ready is True when ch04 + ch05 + ch06 fully submitted
  6. non-ch07 chapters return lock_state=None
"""
import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")

CHAPTERS_ROOT = r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters"

# Chapters relevant to the lock test (ch07 needs ch04 + ch05 + ch06).
NEEDED_CHAPTERS = ["ch04", "ch05", "ch06", "ch07", "ch01"]


def _load_cfg(chapter_id):
    p = os.path.join(CHAPTERS_ROOT, "chapter_config_" + chapter_id + ".json")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_app(tmp_path, monkeypatch, chapters):
    db = tmp_path / "ww.db"
    monkeypatch.setenv("WW_DB_PATH", str(db))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    from importlib import reload
    import app.config
    import app.db
    reload(app.config)
    reload(app.db)
    app.db.init_db()
    for ch in chapters:
        cfg = _load_cfg(ch)
        with app.db.get_conn() as conn:
            conn.execute(
                "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, ?, ?, 1, datetime('now'))",
                (ch, 1, json.dumps(cfg)),
            )
    import app.main as main_mod
    reload(main_mod)
    return main_mod.app


def _seed_step_run(chapter_id, step_id, status="submitted"):
    import app.db
    with app.db.get_conn() as conn:
        conn.execute(
            """INSERT INTO step_runs (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status, updated_at)
               VALUES (?, ?, ?, '[]', 'career_counselor', '', '', '{}', ?, datetime('now'))""",
            (str(uuid.uuid4()), chapter_id, step_id, status),
        )


def _seed_profile(**fields):
    import app.db
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO learner_profiles (user_id, profile_json) VALUES (?, ?)",
            ("local", json.dumps(fields)),
        )


async def _get_status(ac, chapter_id):
    import app.db as _db
    r = await ac.get("/api/book/chapters/" + chapter_id + "/status")
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_m5_chapter_status_empty(tmp_path, monkeypatch):
    """No step runs -> is_submitted=False, total_steps=1 (ch01 has 1 exercise)."""
    from httpx import AsyncClient, ASGITransport
    app_obj = _make_app(tmp_path, monkeypatch, ["ch01"])
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as ac:
        s = await _get_status(ac, "ch01")
    assert s["chapter_id"] == "ch01"
    assert s["is_submitted"] is False
    assert s["submitted_steps"] == []
    assert s["submitted_count"] == 0
    assert s["total_steps"] == 1
    assert s["lock_state"] is None


@pytest.mark.asyncio
async def test_m5_chapter_status_partial(tmp_path, monkeypatch):
    """ch04 has 5 steps; submit 2 -> is_submitted=False, submitted_count=2."""
    from httpx import AsyncClient, ASGITransport
    import app.db
    app_obj = _make_app(tmp_path, monkeypatch, ["ch04"])
    _seed_step_run("ch04", "step-1")
    _seed_step_run("ch04", "step-2")
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as ac:
        s = await _get_status(ac, "ch04")
    assert s["chapter_id"] == "ch04"
    assert s["is_submitted"] is False
    assert sorted(s["submitted_steps"]) == ["step-1", "step-2"]
    assert s["submitted_count"] == 2
    assert s["total_steps"] == 5


@pytest.mark.asyncio
async def test_m5_chapter_status_fully_submitted(tmp_path, monkeypatch):
    """ch04 all 5 steps submitted -> is_submitted=True."""
    from httpx import AsyncClient, ASGITransport
    import app.db
    app_obj = _make_app(tmp_path, monkeypatch, ["ch04"])
    for sid in ["step-1", "step-2", "step-3", "step-4", "step-5"]:
        _seed_step_run("ch04", sid)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as ac:
        s = await _get_status(ac, "ch04")
    assert s["is_submitted"] is True
    assert sorted(s["submitted_steps"]) == ["step-1", "step-2", "step-3", "step-4", "step-5"]
    assert s["submitted_count"] == 5
    assert s["total_steps"] == 5


@pytest.mark.asyncio
async def test_m5_ch07_lock_state_no_upstream(tmp_path, monkeypatch):
    """ch07 with no submitted upstream chapters -> lock_state.ready=False."""
    from httpx import AsyncClient, ASGITransport
    app_obj = _make_app(tmp_path, monkeypatch, ["ch04", "ch05", "ch06", "ch07"])
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as ac:
        s = await _get_status(ac, "ch07")
    assert s["chapter_id"] == "ch07"
    assert s["lock_state"] is not None
    assert s["lock_state"]["upstream"] == ["ch04", "ch05", "ch06"]
    assert s["lock_state"]["ready"] is False
    assert s["lock_state"]["upstream_status"]["ch04"]["is_submitted"] is False
    assert s["lock_state"]["upstream_status"]["ch05"]["is_submitted"] is False
    assert s["lock_state"]["upstream_status"]["ch06"]["is_submitted"] is False


@pytest.mark.asyncio
async def test_m5_ch07_lock_state_partial_upstream(tmp_path, monkeypatch):
    """ch07 with only ch04 submitted -> lock_state.ready still False."""
    from httpx import AsyncClient, ASGITransport
    app_obj = _make_app(tmp_path, monkeypatch, ["ch04", "ch05", "ch06", "ch07"])
    for sid in ["step-1", "step-2", "step-3", "step-4", "step-5"]:
        _seed_step_run("ch04", sid)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as ac:
        s = await _get_status(ac, "ch07")
    assert s["lock_state"]["ready"] is False
    assert s["lock_state"]["upstream_status"]["ch04"]["is_submitted"] is True
    assert s["lock_state"]["upstream_status"]["ch05"]["is_submitted"] is False
    assert s["lock_state"]["upstream_status"]["ch06"]["is_submitted"] is False


@pytest.mark.asyncio
async def test_m5_ch07_lock_state_ready(tmp_path, monkeypatch):
    """ch07 unlocks only after ch04, ch05, and both ch06 steps submit."""
    from httpx import AsyncClient, ASGITransport
    app_obj = _make_app(tmp_path, monkeypatch, ["ch04", "ch05", "ch06", "ch07"])
    for sid in ["step-1", "step-2", "step-3", "step-4", "step-5"]:
        _seed_step_run("ch04", sid)
    _seed_step_run("ch05", "step-1")
    _seed_step_run("ch05", "step-2")
    _seed_step_run("ch06", "step-1")
    _seed_step_run("ch06", "step-2")
    _seed_profile(
        likes=[{"field": "deep conversation", "aspects": [{"text": "listening"}]}],
        talents=[{"text": "empathy framing", "rating": "\u25ce", "source": None}],
        values=["help others grow"],
        work_purpose="help people find direction",
    )
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as ac:
        s = await _get_status(ac, "ch07")
    assert s["lock_state"]["ready"] is True
    assert s["lock_state"]["upstream_status"]["ch04"]["is_submitted"] is True
    assert s["lock_state"]["upstream_status"]["ch05"]["is_submitted"] is True
    assert s["lock_state"]["upstream_status"]["ch06"]["is_submitted"] is True


@pytest.mark.asyncio
async def test_m5_ch07_lock_state_missing_profile_fields(tmp_path, monkeypatch):
    """Submitted upstream runs without required profile fields stay locked."""
    from httpx import AsyncClient, ASGITransport
    app_obj = _make_app(tmp_path, monkeypatch, ["ch04", "ch05", "ch06", "ch07"])
    for sid in ["step-1", "step-2", "step-3", "step-4", "step-5"]:
        _seed_step_run("ch04", sid)
    _seed_step_run("ch05", "step-1")
    _seed_step_run("ch05", "step-2")
    _seed_step_run("ch06", "step-1")
    _seed_step_run("ch06", "step-2")
    _seed_profile(likes=[{"field": "deep conversation"}], talents=["empathy framing"])
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as ac:
        s = await _get_status(ac, "ch07")
    assert s["lock_state"]["ready"] is False
    assert s["lock_state"]["missing_profile_fields"] == {
        "ch04": ["work_purpose", "values"],
    }


@pytest.mark.asyncio
async def test_m5_ch07_step_routes_reject_incomplete_context(tmp_path, monkeypatch):
    """The API cannot bypass the ch07 upstream lock."""
    from httpx import AsyncClient, ASGITransport
    app_obj = _make_app(tmp_path, monkeypatch, ["ch04", "ch05", "ch06", "ch07"])
    for sid in ["step-1", "step-2", "step-3", "step-4", "step-5"]:
        _seed_step_run("ch04", sid)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as ac:
        draft = await ac.post(
            "/api/chapters/ch07/steps/step-1/draft",
            json={"user_answers": "candidate"},
        )
    assert draft.status_code == 409
    assert "Chapter context incomplete" in draft.text


@pytest.mark.asyncio
async def test_m5_non_ch07_no_lock_state(tmp_path, monkeypatch):
    """ch01/ch05 etc. return lock_state=None (lock is only for ch07 today)."""
    from httpx import AsyncClient, ASGITransport
    import app.db
    app_obj = _make_app(tmp_path, monkeypatch, ["ch01", "ch05"])
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as ac:
        s1 = await _get_status(ac, "ch01")
        s2 = await _get_status(ac, "ch05")
    assert s1["lock_state"] is None
    assert s2["lock_state"] is None


@pytest.mark.asyncio
async def test_m5_chapter_status_draft_does_not_count(tmp_path, monkeypatch):
    """Steps in 'draft' status must not count toward submitted."""
    from httpx import AsyncClient, ASGITransport
    import app.db
    app_obj = _make_app(tmp_path, monkeypatch, ["ch01"])
    _seed_step_run("ch01", "step-1", status="draft")
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as ac:
        s = await _get_status(ac, "ch01")
    assert s["is_submitted"] is False
    assert s["submitted_count"] == 0
    assert s["submitted_steps"] == []
