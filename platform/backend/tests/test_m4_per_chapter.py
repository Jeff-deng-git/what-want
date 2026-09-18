"""M4 per-chapter end-to-end verify: schema-aligned mock LLM populates output_fields.

Two-tier verification (matches handoff SS6.2 design intent):
  1. parsed_output must contain ALL declared output_fields (LLM captures them).
  2. PROFILE_FIELDS landing -- cross-chapter fields (PROFILE_FIELDS whitelist)
     land in learner_profiles; per-chapter artifacts (e.g. color_bath_log) stay
     in step_runs.parsed_output only.

This proves the runtime pipeline is end-to-end correct from config -> prompt
-> parse -> persist -> compaction without depending on a real LLM.
"""
import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")

CHAPTERS_ROOT = r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters"

# Per-chapter mock LLM responses aligned with output_fields.
PER_CHAPTER_MOCK = {
    "ch01": {
        "role": "career_counselor",
        "payload": {
            "misconceptions_cleared": ["must have unique right answer"],
            "external_voices": ["dad said choose right"],
            "commentary": "基于本章正文的分析",
        },
    },
    "ch02": {
        "role": "psychologist",
        "payload": {
            "commentary": "这两件事的驱动力不同：一件更依赖外部评价，另一件更接近自己的满足感。",
            "internal_external_ratio": {"external_pct": 99, "internal_pct": 1, "method": "llm_guess"},
            "reclaim_item": "use my evening for my own things",
        },
    },
    "ch03": {
        "role": "psychologist",
        "payload": {
            "commentary": "结合三要素输入校正混淆",
            "likes": ["deep conversation", "making tools", "discussing ideas"],
            "talents": ["empathy framing", "explaining complexity", "organizing collaboration"],
            "importance": ["help others grow", "keep learning", "create room for possibility"],
            "intersection": "helping via conversation",
        },
    },
    "ch05": {
        "roles": {"step-1": "psychologist", "step-2": "psychologist"},
        "payload": {
            "step-1": {
                "commentary": "从五个回答中看到稳定的才能线索。",
                "talents": [{"text": "empathy framing", "locked": False}],
            },
            "step-2": {
                "user_manual": "先理解对方，再帮助对方把复杂问题讲清楚。",
                "talents": [
                    {"text": "empathy framing", "rating": "\u25ce", "locked": False},
                    {"text": "explaining complexity", "rating": "", "locked": False},
                ],
            },
        },
    },
    "ch06": {
        "roles": {"step-1": "psychologist", "step-2": "career_counselor"},
        "payload": {
            "step-1": {
                "commentary": "从回答中提炼持续有能量的兴趣线索。",
                "likes": [{"text": "independent exploration", "locked": False}],
            },
            "step-2": {
                "commentary": "将领域拆成具体喜欢的方面，并连接已有才能。",
                "likes": [{
                    "field": "independent exploration",
                    "aspects": [{"text": "thinking deeply"}],
                    "linked_strengths": [{"text": "empathy framing"}],
                    "sources": ["q1"],
                    "locked": False,
                }],
            },
        },
    },
    "ch07": {
        "roles": {"step-1": "career_counselor", "step-2": "mentor"},
        "payload": {
            "ideal_works": [{
                "title": "帮助他人成长的对话工作",
                "like_source": "深度对话",
                "strength_source": "倾听并梳理复杂情绪",
                "bucket": "未定",
                "locked": False,
            }],
            "commentary": "把喜欢的方面和擅长之事组合成待验证的想做之事。",
            "next_action": "从一个候选开始设计低成本验证。",
        },
    },
    "ch08": {
        "role": "career_counselor",
        "payload": {
            "success_statement": "help people find their direction",
            "color_bath_log": [
                {"date": "2026-08-01", "signal": "podcast on writing", "what_i_did": "took notes"},
            ],
        },
    },
}

# Mirror of app.services.compaction.PROFILE_FIELDS whitelist (cross-chapter fields).
PROFILE_FIELDS_WHITELIST = {
    "misconceptions_cleared", "external_voices",
    "internal_external_ratio", "reclaim_item",
    "likes", "talents", "importance",
    "work_purpose", "values", "ranked", "intersection",
    "success_statement", "formula",
    "ideal_works",
    "current_chapter", "open_questions", "milestones",
}


def _load_cfg(chapter_id):
    p = os.path.join(CHAPTERS_ROOT, "chapter_config_" + chapter_id + ".json")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _declared_field_names(exercises):
    names = []
    for ex in exercises:
        for f in ex.get("output_fields") or []:
            if isinstance(f, dict):
                names.append(f["name"])
            else:
                names.append(f)
    return names


def _make_app(chapter_id, mock_payload, tmp_path, monkeypatch):
    db = tmp_path / "ww.db"
    monkeypatch.setenv("WW_DB_PATH", str(db))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    from importlib import reload
    import app.config
    import app.db
    reload(app.config)
    reload(app.db)
    app.db.init_db()
    cfg = _load_cfg(chapter_id)
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, ?, ?, 1, datetime('now'))",
            (chapter_id, 1, json.dumps(cfg)),
        )
        if chapter_id == "ch07":
            for producer in ("ch04", "ch05", "ch06"):
                producer_cfg = _load_cfg(producer)
                conn.execute(
                    "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, ?, ?, 1, datetime('now'))",
                    (producer, 1, json.dumps(producer_cfg)),
                )
                for exercise in producer_cfg.get("exercises") or []:
                    conn.execute(
                        """INSERT INTO step_runs
                           (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status, updated_at)
                           VALUES (?, ?, ?, '[]', 'career_counselor', '', '{}', '{}', 'submitted', datetime('now'))""",
                        (str(uuid.uuid4()), producer, exercise["step_id"]),
                    )
            conn.execute(
                "INSERT INTO learner_profiles (user_id, profile_json) VALUES (?, ?)",
                ("local", json.dumps({
                    "likes": [{"field": "deep conversation", "aspects": [{"text": "exploring ideas"}], "linked_strengths": [], "sources": [], "locked": False}],
                    "talents": [{"text": "empathy framing", "rating": "\u25ce", "source": None}],
                    "values": ["help others grow"],
                    "work_purpose": "help people find direction",
                })),
            )
        for role_name in ("psychologist", "career_counselor", "mentor"):
            conn.execute(
                """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (str(uuid.uuid4()), role_name, "test", "You are " + role_name,
                 "deepseek", "deepseek-chat", 0.5, 1500),
            )
    import app.runtime.agent as agent_mod
    canned = json.dumps(mock_payload, ensure_ascii=False)
    call_index = 0

    async def mock_call_llm(*args, **kwargs):
        nonlocal call_index
        if isinstance(mock_payload, dict) and {"step-1", "step-2"}.issubset(mock_payload):
            step_id = ("step-1", "step-2")[call_index]
            call_index += 1
            return json.dumps(mock_payload[step_id], ensure_ascii=False)
        return canned
    agent_mod.call_llm = mock_call_llm
    import app.main as main_mod
    reload(main_mod)
    return main_mod.app


async def _run_step(ac, ch, step_id):
    body = {"user_answers": ["a sample answer"]}
    if ch == "ch02":
        body = {"user_answers": {"drive_items": [
            {"text": "加班做项目", "drive": "external", "note": "领导会看到我的进步"},
            {"text": "周末画画", "drive": "internal", "note": "自己真的喜欢"},
            {"text": "准备资格考试", "drive": "external", "note": "家人觉得更体面"},
        ], "notes": "想分清哪些选择是我自己的"}}
    if ch == "ch05" and step_id == "step-1":
        body = {"user_answers": {
            "q1": "帮助同事梳理问题时很有充实感",
            "q2": "表达混乱会让我烦躁",
            "q3": "朋友说我善于倾听",
            "q4": "会想念一起解决问题的过程",
            "q5": "曾把复杂协作整理成方案",
        }}
    if ch == "ch05" and step_id == "step-2":
        body = {"user_answers": {"reference_strengths": [{"text": "explaining complexity"}]}}
    if ch == "ch06" and step_id == "step-1":
        body = {"user_answers": {
            "q1": "我会花钱学习心理学和工具制作",
            "q2": "书架上有心理学和设计书",
            "q3": "被一个帮助我理解自己的播客拯救过",
            "q4": "想感谢帮我打开视野的老师",
            "q5": "对低效沟通很愤怒",
        }}
    if ch == "ch06" and step_id == "step-2":
        body = {"user_answers": {"reference_talents": [{"text": "empathy framing"}]}}
    r = await ac.post("/api/chapters/" + ch + "/steps/" + step_id + "/draft", json=body)
    assert r.status_code == 200, r.text
    r = await ac.post("/api/chapters/" + ch + "/steps/" + step_id + "/run", json=body)
    assert r.status_code == 200, r.text
    return r.json()


async def _submit_step(ac, ch, step_id):
    r = await ac.post("/api/chapters/" + ch + "/steps/" + step_id + "/submit")
    assert r.status_code == 200, r.text
    return r.json()


async def _run_one_chapter(chapter_id, tmp_path, monkeypatch):
    from httpx import AsyncClient, ASGITransport
    import app.db
    cfg = _load_cfg(chapter_id)
    exercises = cfg["exercises"]
    mock_spec = PER_CHAPTER_MOCK[chapter_id]
    expected_roles = mock_spec.get("roles") or {"step-1": mock_spec["role"]}
    mock_payload = mock_spec["payload"]
    app_obj = _make_app(chapter_id, mock_payload, tmp_path, monkeypatch)
    async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as ac:
        for index, exercise in enumerate(exercises):
            step_id = exercise["step_id"]
            declared = {field["name"] for field in exercise.get("output_fields") or []}
            run = await _run_step(ac, chapter_id, step_id)
            expected_role = expected_roles[step_id]
            assert run["role_id"] == expected_role, (
                chapter_id + "/" + step_id + " expected role " + expected_role
                + " got " + str(run["role_id"])
            )
            parsed = run["parsed_output"]
            assert declared.issubset(set(parsed.keys())), (
                chapter_id + "/" + step_id + " missing fields: " + str(declared - set(parsed.keys()))
            )
            sub = await _submit_step(ac, chapter_id, step_id)
            assert sub["compacted"] is (index == len(exercises) - 1), (
                chapter_id + "/" + step_id + " compaction state mismatch"
            )
    final_step = exercises[-1]
    final_step_id = final_step["step_id"]
    declared = {field["name"] for field in final_step.get("output_fields") or []}
    with app.db.get_conn() as conn:
        # Verify parsed_output persisted in step_runs.
        run_row = conn.execute(
            "SELECT parsed_output, status FROM step_runs WHERE chapter_id = ? AND step_id = ?",
            (chapter_id, final_step_id),
        ).fetchone()
        assert run_row["status"] == "submitted"
        persisted_parsed = json.loads(run_row["parsed_output"])
        assert declared.issubset(set(persisted_parsed.keys()))
        # Tier 2: cross-chapter fields land in profile; per-chapter artifacts stay in step_runs.
        prof = conn.execute("SELECT profile_json FROM learner_profiles WHERE user_id='local'").fetchone()
        assert prof is not None, chapter_id + " should have created profile"
        prof_json = json.loads(prof["profile_json"])
        assert prof_json["current_chapter"] == chapter_id
        cross_chapter = declared & PROFILE_FIELDS_WHITELIST
        per_chapter = declared - PROFILE_FIELDS_WHITELIST
        for f in cross_chapter:
            assert f in prof_json, chapter_id + " profile missing cross-chapter field " + f
        for f in per_chapter:
            assert f not in prof_json, (
                chapter_id + " profile should NOT carry per-chapter artifact " + f
            )


@pytest.mark.asyncio
async def test_m4_ch01_output_fields_populated(tmp_path, monkeypatch):
    await _run_one_chapter("ch01", tmp_path, monkeypatch)


@pytest.mark.asyncio
async def test_m4_ch02_output_fields_populated(tmp_path, monkeypatch):
    await _run_one_chapter("ch02", tmp_path, monkeypatch)


@pytest.mark.asyncio
async def test_m4_ch03_output_fields_populated(tmp_path, monkeypatch):
    await _run_one_chapter("ch03", tmp_path, monkeypatch)


@pytest.mark.asyncio
async def test_m4_ch05_output_fields_populated(tmp_path, monkeypatch):
    await _run_one_chapter("ch05", tmp_path, monkeypatch)


@pytest.mark.asyncio
async def test_m4_ch06_output_fields_populated(tmp_path, monkeypatch):
    await _run_one_chapter("ch06", tmp_path, monkeypatch)


@pytest.mark.asyncio
async def test_m4_ch07_output_fields_populated(tmp_path, monkeypatch):
    await _run_one_chapter("ch07", tmp_path, monkeypatch)


@pytest.mark.asyncio
async def test_m4_ch08_output_fields_populated(tmp_path, monkeypatch):
    cfg = _load_cfg("ch08")
    assert cfg.get("page_type") == "flowchart"
    assert not cfg.get("exercises")
    decision_ids = [
        decision["id"]
        for stage in cfg["flowchart"]["stages"]
        for decision in stage["decision_points"]
    ]
    assert decision_ids == ["dp-1", "dp-2", "dp-3", "dp-4", "dp-refine", "dp-5"]
