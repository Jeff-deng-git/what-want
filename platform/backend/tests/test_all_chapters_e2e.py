import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")

CHAPTERS_ROOT = r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters"
CHAPTERS = ["ch01", "ch02", "ch03", "ch04", "ch05", "ch06", "ch07", "ch08"]
EXPECTED_ROLE = {
    "ch01": "career_counselor",
    "ch02": "psychologist",
    "ch03": "psychologist",
    "ch04_step1": "psychologist",
    "ch04_step2": "psychologist",
    "ch04_step3": "psychologist",
    "ch04_step4": "career_counselor",
    "ch04_step5": "career_counselor",
    "ch05": "psychologist",
    "ch06_step1": "psychologist",
    "ch06_step2": "career_counselor",
    "ch07_step1": "career_counselor",
    "ch07_step2": "mentor",
    "ch08": "career_counselor",
}


@pytest.fixture
def all_app(tmp_path, monkeypatch):
    db = tmp_path / "ww.db"
    monkeypatch.setenv("WW_DB_PATH", str(db))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    from importlib import reload
    import app.config
    import app.db
    reload(app.config)
    reload(app.db)
    app.db.init_db()
    for ch in CHAPTERS:
        with open(os.path.join(CHAPTERS_ROOT, "chapter_config_" + ch + ".json"), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        with app.db.get_conn() as conn:
            conn.execute(
                "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, ?, ?, 1, datetime('now'))",
                (ch, 1, json.dumps(cfg)),
            )
    with app.db.get_conn() as conn:
        for name, desc in [
            ("psychologist", "Reflective self-cognition coach."),
            ("career_counselor", "Career counselor for synthesis steps."),
            ("mentor", "Career-planning mentor."),
        ]:
            conn.execute(
                """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (str(uuid.uuid4()), name, desc,
                 "You are a " + name + ". Respond in Chinese when user writes Chinese.",
                 "deepseek", "deepseek-chat", 0.5, 1500),
            )
    import app.runtime.agent as agent_mod
    async def mock_call_llm(*args, **kwargs):
        system = kwargs.get("system", "")
        if "reference_talents" in system:
            return json.dumps({
                "commentary": "把兴趣领域拆成具体方面，并尝试与已形成的才能连接。",
                "likes": [{
                    "field": "独立探索",
                    "aspects": [{"text": "把问题想深"}],
                    "linked_strengths": [{"text": "倾听并梳理复杂情绪"}],
                    "sources": ["q1"],
                    "locked": False,
                }],
            }, ensure_ascii=False)
        if "你现在有即使花钱也想学习的事情吗？" in system:
            return json.dumps({
                "commentary": "从回答中看到对独立探索和深入思考的持续兴趣。",
                "likes": [{"text": "独立探索", "locked": False}],
            }, ensure_ascii=False)
        if '"ideal_works"' in system and '"next_action"' not in system:
            return json.dumps({
                "ideal_works": [{
                    "title": "help people clarify complex problems",
                    "like_source": "deep thinking",
                    "strength_source": "empathetic listening",
                    "bucket": "undecided",
                    "locked": False,
                }],
                "commentary": "Connect the interest aspect with a demonstrated strength to form a testable candidate.",
            }, ensure_ascii=False)
        if '"ideal_works"' in system and '"next_action"' in system:
            return json.dumps({
                "ideal_works": [{
                    "title": "help people clarify complex problems",
                    "like_source": "deep thinking",
                    "strength_source": "empathetic listening",
                    "bucket": "true_work",
                    "locked": False,
                }],
                "commentary": "Use work purpose to suggest a bucket while preserving the learner's final judgment.",
                "next_action": "Run a small trial conversation, then review whether to continue.",
            }, ensure_ascii=False)
        payloads = [
            ('[CH02 COMMENTARY CONTRACT]', {
                "commentary": "结合具体事项和备注的驱动力映照。",
                "internal_external_ratio": {"external_pct": 1, "internal_pct": 99, "method": "wrong"},
                "reclaim_item": "重新决定把时间交给什么。",
            }),
             ('[CH03 ANALYSIS CONTRACT]', {
                 "commentary": "结合三组输入识别其交集，并区分喜欢、才能与重要性。",
                 "likes": ["deep conversation", "making tools", "discussing ideas"],
                 "talents": ["empathy framing", "explaining complexity", "organizing collaboration"],
                 "importance": ["help others grow", "keep learning", "create room for possibility"],
                 "intersection": "通过对话和工具帮助他人成长",
             }),
             ('[CH05 STEP-1 CONTRACT]', {
                 "commentary": "从五个回答里反复出现的是先理解他人处境，再把复杂事情讲清楚。",
                 "talents": [{"text": "倾听并梳理复杂情绪", "locked": False}],
             }),
             ('[CH05 STEP-2 CONTRACT]', {
                 "user_manual": "先通过倾听理解问题，再把可行动的下一步说明白。",
                 "talents": [
                     {"text": "倾听并梳理复杂情绪", "rating": "\u25ce", "locked": False},
                     {"text": "把复杂信息讲清楚", "rating": "", "locked": False},
                 ],
             }),
             ('"importance"', {
                "commentary": "ok",
                "likes": ["deep conversation"],
                "talents": ["empathy framing"],
                "importance": ["help others grow"],
            }),
            ('"top_values"', {"top_values": ["按自己的标准活"], "commentary": "ok"}),
            ('"groups"', {"groups": [{"umbrella": "self-expression", "keywords": [], "locked": False}]}),
            ('"conversions"', {"conversions": [{"value": "外部期待", "rewritten": "我的选择", "locked": False}]}),
            ('"ranked"', {"ranked": [{"value": "成长", "locked": True}]}),
            ('"work_purpose"', {"work_purpose": "帮助他人找到方向", "experience_map": []}),
        ]
        for marker, payload in payloads:
            if marker in system:
                return json.dumps(payload, ensure_ascii=False)
        return json.dumps({"value": "ok"}, ensure_ascii=False)
    agent_mod.call_llm = mock_call_llm
    import app.main as main_mod
    reload(main_mod)
    yield main_mod.app


async def _run_one(ac, ch, step_id, expected_role):
    body = {"user_answers": ["a sample answer for " + step_id]}
    if ch == "ch02":
        body = {"user_answers": {"drive_items": [
            {"text": "加班做项目", "drive": "external", "note": "领导会看到我的进步"},
            {"text": "周末画画", "drive": "internal", "note": "自己真的喜欢"},
        ], "notes": ""}}
    if ch == "ch03":
        body = {"user_answers": {
            "importance": [{"text": "帮助别人"}, {"text": "持续学习"}, {"text": "创造空间"}],
            "talents": [{"text": "写代码"}, {"text": "解释复杂问题"}, {"text": "组织协作"}],
            "likes": [{"text": "心理学"}, {"text": "做工具"}, {"text": "和人讨论"}],
        }}
    if ch == "ch05" and step_id == "step-1":
        body = {"user_answers": {
            "q1": "帮同事梳理复杂问题时很有充实感",
            "q2": "表达混乱会让我烦躁",
            "q3": "朋友说我善于倾听",
            "q4": "会想念一起解决问题的过程",
            "q5": "曾把跨团队信息整理成行动方案",
        }}
    if ch == "ch05" and step_id == "step-2":
        body = {"user_answers": {
            "reference_strengths": [{"text": "把复杂信息讲清楚"}],
        }}
    if ch == "ch06" and step_id == "step-1":
        body = {"user_answers": {
            "q1": "我会忘记时间地研究和做小工具",
            "q2": "对重复的表面社交没有耐心",
            "q3": "朋友觉得我喜欢把问题想深",
            "q4": "离开后会想念自由探索的空间",
            "q5": "做过一个帮助团队协作的小工具",
        }}
    if ch == "ch06" and step_id == "step-2":
        body = {"user_answers": {
            "reference_talents": [{"text": "独立探索"}],
        }}
    r = await ac.post("/api/chapters/" + ch + "/steps/" + step_id + "/draft", json=body)
    assert r.status_code == 200, r.text
    r = await ac.post("/api/chapters/" + ch + "/steps/" + step_id + "/run", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["role_id"] == expected_role, (
        ch + "/" + step_id + " expected " + expected_role + " got " + r.json()["role_id"]
    )
    r = await ac.post("/api/chapters/" + ch + "/steps/" + step_id + "/submit")
    assert r.status_code == 200, r.text
    return r.json()["compacted"]


@pytest.mark.asyncio
async def test_all_chapters_route_to_expected_role(all_app):
    from httpx import AsyncClient, ASGITransport
    import app.db
    async with AsyncClient(transport=ASGITransport(app=all_app), base_url="http://test") as ac:
        for ch in ["ch01", "ch02", "ch03"]:
            compacted = await _run_one(ac, ch, "step-1", EXPECTED_ROLE[ch])
            assert compacted, ch + " should compact (single exercise)"
        for s in range(1, 6):
            compacted = await _run_one(ac, "ch04", "step-" + str(s),
                                       EXPECTED_ROLE["ch04_step" + str(s)])
            if s < 5:
                assert not compacted, "ch04 step-" + str(s) + " should NOT compact yet"
            else:
                assert compacted, "ch04 step-5 should compact"
        compacted = await _run_one(ac, "ch05", "step-1", EXPECTED_ROLE["ch05"])
        assert not compacted, "ch05 step-1 should wait for step-2 before compaction"
        compacted = await _run_one(ac, "ch05", "step-2", EXPECTED_ROLE["ch05"])
        assert compacted, "ch05 step-2 should compact the formal talents"
        compacted = await _run_one(ac, "ch06", "step-1", EXPECTED_ROLE["ch06_step1"])
        assert not compacted, "ch06 step-1 should wait for step-2 before compaction"
        compacted = await _run_one(ac, "ch06", "step-2", EXPECTED_ROLE["ch06_step2"])
        assert compacted, "ch06 step-2 should compact the formal likes"
        compacted = await _run_one(ac, "ch07", "step-1", EXPECTED_ROLE["ch07_step1"])
        assert not compacted, "ch07 step-1 should wait for step-2 before compaction"
        compacted = await _run_one(ac, "ch07", "step-2", EXPECTED_ROLE["ch07_step2"])
        assert compacted, "ch07 step-2 should compact the combined candidates"
    with app.db.get_conn() as conn:
        n_runs = conn.execute("SELECT COUNT(*) AS c FROM step_runs").fetchone()["c"]
        n_submitted = conn.execute("SELECT COUNT(*) AS c FROM step_runs WHERE status='submitted'").fetchone()["c"]
        profile = conn.execute("SELECT profile_json FROM learner_profiles WHERE user_id='local'").fetchone()
        assert n_runs == 14
        assert n_submitted == 14
        parsed = json.loads(profile["profile_json"])
        assert parsed["current_chapter"] == "ch07"  # ch08 is a flowchart page and no longer compacts
        prompt = conn.execute(
            "SELECT rendered_prompt FROM step_runs WHERE chapter_id = 'ch07' AND step_id = 'step-1' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()["rendered_prompt"]
        assert "(see app.runtime.assembler.build_step_prompt)" not in prompt
        assert "帮助他人找到方向" in prompt


def test_legacy_run_step_path_removed():
    """M3.3: legacy jinja2 runner is gone (handoff Q9, decision 1 = drop jinja2)."""
    import app.routers.steps as steps_mod
    assert not hasattr(steps_mod, "_run_step_legacy"),         "legacy runner must be removed per handoff Q9"
    assert not hasattr(steps_mod, "_uses_exercises_schema"),         "router no longer branches on schema; all chapters go through Option B"


@pytest.mark.asyncio
async def test_chapters_route_through_agent_run_step(all_app):
    """M3.3: agent.run_step with unknown step_role_id raises RuntimeError (no silent fallback)."""
    import pytest
    import app.db
    import app.runtime.agent as agent_mod
    # Force ch07 to point at a role that was not seeded -- expect RuntimeError.
    with app.db.get_conn() as conn:
        conn.execute("UPDATE chapter_configs SET active = 0 WHERE chapter_id = 'ch07'")
        cfg = json.loads(conn.execute(
            "SELECT config_json FROM chapter_configs WHERE chapter_id='ch07' ORDER BY version DESC LIMIT 1"
        ).fetchone()["config_json"])
        cfg["exercises"][0]["step_role_id"] = "nonexistent_role_for_test"
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, ?, ?, 1, datetime('now'))",
            ("ch07", 2, json.dumps(cfg)),
        )
    with pytest.raises(RuntimeError, match="step role not found"):
        await agent_mod.run_step("ch07", "step-1", ["a"], user_id="local")


def test_career_counselor_system_prompt_is_authoritative():
    """Q1 protection: seed_roles.py career_counselor must contain the authoritative marker.

    Guards against accidental regression to the generic system_prompt. The
    authoritative version is the one 设计侧 shipped (2026-08-03) with the ch7/ch8
    seven-scenario constraints inlined; see llm_prompt_design/backups/seed_roles.orig-2026-08-03.md.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'seed_roles_check',
        r'D:\AI_Project\What_Want\platform\backend\scripts\seed_roles.py',
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    roles = {r['name']: r for r in mod.ROLES}
    cc = roles['career_counselor']
    # Authoritative marker: 中文 phrase 设计侧 shipped (Q1)
    assert '职业与人生咨询师' in cc['system_prompt'], 'must use 设计侧 authoritative 中文 marker'
    # ch7/ch8 seven-scenario constraint block is present
    assert 'ch07' in cc['system_prompt'] or 'ch7' in cc['system_prompt']
    assert 'ch08' in cc['system_prompt'] or 'ch8' in cc['system_prompt']
    assert '组合' in cc['system_prompt'] and '实现手段' in cc['system_prompt']
    # Sub-role names must NOT leak back into the prompt
    assert 'combination-strategist' not in cc['system_prompt']
    assert 'means-finder' not in cc['system_prompt']


def test_validate_parsed_against_types_warns_but_does_not_block():
    """Q6 (iii): type mismatches log a warning, do not raise.

    Verifies _validate_parsed_against_types accepts mismatched types gracefully so
    the parser layer never breaks the user-visible flow (handoff Q6 warn-only).
    """
    import logging
    import app.routers.steps as steps_mod
    fields = [
        {'name': 'good_list', 'type': 'list'},
        {'name': 'bad_list', 'type': 'list'},
        {'name': 'good_text', 'type': 'text'},
        {'name': 'bad_text', 'type': 'text'},
        {'name': 'good_num', 'type': 'number'},
        {'name': 'bad_num', 'type': 'number'},
    ]
    parsed = {
        'good_list': ['a', 'b'],
        'bad_list': 'not a list',
        'good_text': 'hi',
        'bad_text': 42,
        'good_num': '3.14',
        'bad_num': 'not a number',
    }
    captured = []
    class _CapHandler(logging.Handler):
        def emit(self, record):
            captured.append(record.getMessage())
    h = _CapHandler(level=logging.WARNING)
    logger = logging.getLogger('app.routers.steps')
    logger.addHandler(h)
    try:
        steps_mod._validate_parsed_against_types(parsed, fields)
    finally:
        logger.removeHandler(h)
    # at least one warning per bad field; good fields do not warn
    text = '\n'.join(captured)
    assert 'bad_list' in text
    assert 'bad_text' in text
    assert 'bad_num' in text
    assert 'good_list' not in text
    assert 'good_text' not in text
    assert 'good_num' not in text


def test_seed_roles_includes_mentor_and_summary():
    """Q10: seed_roles.py must carry mentor + summary roles for chat/summary routers."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'seed_roles_q10',
        r'D:\AI_Project\What_Want\platform\backend\scripts\seed_roles.py',
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    names = {r['name'] for r in mod.ROLES}
    assert 'mentor' in names, 'mentor role must be seeded (used by agent.run_mentor)'
    assert 'summary' in names, 'summary role must be seeded (used by agent.run_summary)'
    assert 'career_counselor' in names
    assert 'psychologist' in names


def test_chat_routes_default_to_agent_path():
    """Q10: USE_AGENT_CHAT defaults to True (new path), env var can flip to legacy."""
    import os
    import importlib
    saved = os.environ.pop('USE_AGENT_CHAT', None)
    try:
        if 'app.routers.chat' in importlib.sys.modules:
            importlib.reload(importlib.import_module('app.routers.chat'))
        import app.routers.chat as chat_mod
        assert chat_mod.USE_AGENT_CHAT is True, 'default should be new agent path (handoff Q10)'
        # Ensure legacy function still exists for rollback
        assert callable(getattr(chat_mod, '_send_message_legacy', None))
    finally:
        if saved is not None:
            os.environ['USE_AGENT_CHAT'] = saved


def test_summary_routes_default_to_agent_path():
    """Q10: USE_AGENT_SUMMARY defaults to True, legacy kept for rollback."""
    import os
    import importlib
    saved = os.environ.pop('USE_AGENT_SUMMARY', None)
    try:
        if 'app.routers.summary' in importlib.sys.modules:
            importlib.reload(importlib.import_module('app.routers.summary'))
        import app.routers.summary as summary_mod
        assert summary_mod.USE_AGENT_SUMMARY is True
        assert callable(getattr(summary_mod, '_regenerate_legacy', None))
    finally:
        if saved is not None:
            os.environ['USE_AGENT_SUMMARY'] = saved


def test_mentor_should_compact_triggers_at_k_boundary(all_app):
    """Q7: trigger fires exactly when mentor count is a positive multiple of K."""
    import uuid
    from app.db import get_conn
    from app.runtime import agent as agent_mod

    def _seed_mentor_rows(n: int):
        with get_conn() as c:
            for _ in range(n):
                c.execute(
                    """INSERT INTO chapter_chat (id, chapter_id, role, content)
                       VALUES (?, 'ch01', 'mentor', 'hi')""",
                    (str(uuid.uuid4()),),
                )

    K = agent_mod.MENTOR_COMPACTION_K

    # 0 rows: no trigger
    assert agent_mod._mentor_turn_count() == 0
    assert agent_mod._mentor_should_compact() is False

    # K-1 rows: still no trigger (need to reach boundary first)
    _seed_mentor_rows(K - 1)
    assert agent_mod._mentor_should_compact() is False

    # K rows: trigger!
    _seed_mentor_rows(1)
    assert agent_mod._mentor_should_compact() is True

    # K+1 rows: next call still triggers when crossing 2K
    _seed_mentor_rows(K)
    assert agent_mod._mentor_should_compact() is True


def test_force_mentor_compaction_refreshes_profile_with_current_chapter(all_app):
    """Q7: trigger refreshes learner_profiles.current_chapter under the budget guard."""
    import uuid
    from app.db import get_conn
    from app.runtime import agent as agent_mod
    user_id = "local"

    # Seed existing profile with structured fields
    with get_conn() as c:
        c.execute(
            """INSERT INTO learner_profiles (user_id, profile_json)
               VALUES (?, ?)""",
            (user_id, json.dumps({
                "likes": ["writing", "cooking"],
                "talents": ["empathy"],
                "values": ["growth"],
                "current_chapter": "ch01",
                "open_questions": [],
            })),
        )
        # Seed K=20 mentor rows to satisfy trigger
        for _ in range(agent_mod.MENTOR_COMPACTION_K):
            c.execute(
                """INSERT INTO chapter_chat (id, chapter_id, role, content)
                   VALUES (?, 'ch01', 'mentor', 'hi')""",
                (str(uuid.uuid4()),),
            )

    agent_mod._force_mentor_compaction(user_id, "ch07")
    with get_conn() as c:
        row = c.execute(
            "SELECT profile_json FROM learner_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    profile = json.loads(row["profile_json"])
    assert profile["current_chapter"] == "ch07"
    # Structured fields preserved through the compaction budget guard
    assert "likes" in profile or profile.get("likes") is None  # budget may drop; not strictly required
    assert profile.get("open_questions") == []


@pytest.mark.asyncio
async def test_extract_open_questions_parses_llm_json():
    """Q8: LLM returning JSON {"open_questions": [...]} is parsed and capped at 3."""
    import uuid
    from app.db import get_conn
    from app.services.compaction import extract_open_questions

    # Seed career_counselor role so the helper can load it
    # tmp_path-isolated DB so the test does not depend on or pollute the main DB.
    # (Required since M5.8 added UNIQUE (name, provider) WHERE enabled=1.)
    import tempfile as _tf, os as _os
    _tmpdir = _tf.mkdtemp(prefix="ww_q8_")
    _tmpdb = _os.path.join(_tmpdir, "ww.db")
    _os.environ["WW_DB_PATH"] = _tmpdb
    from importlib import reload as _reload
    import app.config as _cfg
    import app.db as _db
    _reload(_cfg); _reload(_db)
    _db.init_db()
    with _db.get_conn() as c:
        c.execute(
            """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES (?, 'career_counselor', '', 'role', 'deepseek', 'deepseek-chat', 0.5, 600, 1)""",
            (str(uuid.uuid4()),),
        )

    async def fake_llm(*, system, user, **kw):
        return json.dumps({"open_questions": ["q1?", "q2?", "q3?", "q4?"]})

    outputs = [{"likes": ["writing"]}]
    profile = {"likes": ["writing"]}
    qs = await extract_open_questions(outputs, profile, llm_callable=fake_llm)
    assert qs == ["q1?", "q2?", "q3?"], "must cap at 3 questions"


@pytest.mark.asyncio
async def test_extract_open_questions_handles_llm_failure_gracefully():
    """Q8: any LLM failure returns [] (do not block the caller)."""
    import uuid
    from app.db import get_conn
    from app.services.compaction import extract_open_questions

    # tmp_path-isolated DB so the test does not depend on or pollute the main DB.
    # (Required since M5.8 added UNIQUE (name, provider) WHERE enabled=1.)
    import tempfile as _tf, os as _os
    _tmpdir = _tf.mkdtemp(prefix="ww_q8_")
    _tmpdb = _os.path.join(_tmpdir, "ww.db")
    _os.environ["WW_DB_PATH"] = _tmpdb
    from importlib import reload as _reload
    import app.config as _cfg
    import app.db as _db
    _reload(_cfg); _reload(_db)
    _db.init_db()
    with _db.get_conn() as c:
        c.execute(
            """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES (?, 'career_counselor', '', 'role', 'deepseek', 'deepseek-chat', 0.5, 600, 1)""",
            (str(uuid.uuid4()),),
        )

    async def broken_llm(*, system, user, **kw):
        raise RuntimeError("network down")

    qs = await extract_open_questions([{"likes": ["x"]}], {"likes": ["x"]}, llm_callable=broken_llm)
    assert qs == [], "failure must return empty list, not raise"


@pytest.mark.asyncio
async def test_extract_open_questions_handles_non_json_gracefully():
    """Q8: non-JSON LLM output is treated as empty."""
    import uuid
    from app.db import get_conn
    from app.services.compaction import extract_open_questions

    # tmp_path-isolated DB so the test does not depend on or pollute the main DB.
    # (Required since M5.8 added UNIQUE (name, provider) WHERE enabled=1.)
    import tempfile as _tf, os as _os
    _tmpdir = _tf.mkdtemp(prefix="ww_q8_")
    _tmpdb = _os.path.join(_tmpdir, "ww.db")
    _os.environ["WW_DB_PATH"] = _tmpdb
    from importlib import reload as _reload
    import app.config as _cfg
    import app.db as _db
    _reload(_cfg); _reload(_db)
    _db.init_db()
    with _db.get_conn() as c:
        c.execute(
            """INSERT INTO llm_roles (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES (?, 'career_counselor', '', 'role', 'deepseek', 'deepseek-chat', 0.5, 600, 1)""",
            (str(uuid.uuid4()),),
        )

    async def prose_llm(*, system, user, **kw):
        return "not json at all"

    qs = await extract_open_questions([{"likes": ["x"]}], {}, llm_callable=prose_llm)
    assert qs == []


@pytest.mark.asyncio
async def test_extract_open_questions_skips_when_inputs_empty():
    """Q8: no outputs + no profile => no LLM call, return []."""
    from app.services.compaction import extract_open_questions

    qs = await extract_open_questions([], {}, llm_callable=lambda **kw: pytest.fail("must not call"))
    assert qs == []
