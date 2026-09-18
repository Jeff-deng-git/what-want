import json
import os
import sys
from importlib import reload

import pytest

sys.path.insert(0, r"D:\AI_Project\What_Want\platform\backend")


def test_ch04_step4_config_matches_the_books_pyramid_method():
    with open(
        r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch04.json",
        "r",
        encoding="utf-8",
    ) as handle:
        config = json.load(handle)
    step4 = next(item for item in config["exercises"] if item["step_id"] == "step-4")

    assert [field["name"] for field in step4["output_fields"]] == [
        "ranked", "support_links", "final_purpose", "gap_note",
    ]
    assert all(token in step4["instruction"] for token in (
        "核心价值观主题", "最终目的", "基础", "相邻", "支撑", "人生状态",
    ))
    assert "组内关键词" in step4["instruction"]
    assert "不是金字塔层级" in step4["instruction"]
    assert "删除" not in step4["user_action"]
    assert "step-5" not in json.dumps(step4.get("few_shot_examples", []), ensure_ascii=False)


def test_preserve_keeps_locked_items_at_original_positions():
    from app.runtime.assembler import merge_preserved_output

    old = {
        "ranked": [
            {"value": "基础", "locked": True},
            {"value": "旧中间项", "locked": False},
            {"value": "最终目的", "locked": True},
        ]
    }
    merged = merge_preserved_output(
        {"ranked": [{"value": "新建议", "locked": False}]},
        old,
    )

    assert merged["ranked"] == [
        {"value": "基础", "locked": True},
        {"value": "新建议", "locked": False},
        {"value": "最终目的", "locked": True},
    ]


def test_preserve_blocks_deletion_of_locked_items():
    from app.runtime.assembler import merge_preserved_output

    merged = merge_preserved_output(
        {"groups": []},
        {"groups": [{"umbrella": "真实", "keywords": [], "locked": True}]},
    )

    assert merged["groups"] == [{"umbrella": "真实", "keywords": [], "locked": True}]


def test_ch04_step2_prompt_honours_deleted_inherited_keywords():
    from app.runtime.assembler import build_step_prompt

    cfg = {"chapter_id": "ch04", "chapter_title": "重要的事", "core_concepts": [], "guiding_questions": [], "step_context": {"references": []}}
    exercise = {
        "step_id": "step-2",
        "instruction": "分组",
        "user_action": "审阅",
        "references": [{"from_exercise": "step-1", "fields": ["top_values"]}],
        "input_schema": [{"name": "supplemental_keywords", "type": "list_of_items"}],
        "output_fields": [{"name": "groups", "type": "editable_list"}],
    }
    system, user = build_step_prompt(
        "You are a value coach.",
        cfg,
        exercise,
        {"step-1": {"output": {"top_values": ["自由", "成长", "删除我"]}}},
        {"supplemental_keywords": [{"text": "创造"}], "excluded_top_values": ["删除我"]},
        preserve_output={"groups": [{"umbrella": "真实", "locked": True}]},
    )

    assert "删除我" not in user
    assert "自由" in user and "创造" in user
    assert "locked" in system


def test_ch04_step2_prompt_requires_keywords_and_complete_candidate_coverage():
    from app.runtime.assembler import build_step_prompt

    cfg = {"chapter_id": "ch04", "chapter_title": "重要的事", "core_concepts": [], "guiding_questions": [], "step_context": {"references": []}}
    exercise = {
        "step_id": "step-2",
        "instruction": "形成价值观思维导图",
        "user_action": "审阅",
        "references": [{"from_exercise": "step-1", "fields": ["top_values"]}],
        "input_schema": [{"name": "supplemental_keywords", "type": "list_of_items"}],
        "output_fields": [{"name": "groups", "type": "editable_list"}],
    }
    system, user = build_step_prompt(
        "You are a value coach.",
        cfg,
        exercise,
        {"step-1": {"output": {"top_values": [{"value": "自由"}, {"value": "成长"}]}}},
        {"supplemental_keywords": [{"text": "创造"}]},
    )

    assert "CH04 CONFIRMED VALUE CONTEXT" in user
    assert all(value in user for value in ("自由", "成长", "创造"))
    assert "keywords" in system
    assert "values" in system
    assert "exactly once" in system
    assert "number of groups" in system


def test_ch04_step3_prompt_uses_compact_basis_not_raw_answers():
    from app.runtime.assembler import build_step_prompt

    cfg = {"chapter_id": "ch04", "chapter_title": "重要的事", "core_concepts": [], "guiding_questions": [], "step_context": {"references": []}}
    exercise = {
        "step_id": "step-3", "instruction": "可控性检验", "user_action": "审阅",
        "references": [{"from_exercise": "step-1", "fields": ["top_values"]}, {"from_exercise": "step-2", "fields": ["groups"]}],
        "input_schema": [], "output_fields": [{"name": "conversions", "type": "editable_list"}],
    }
    system, user = build_step_prompt(
        "You are a value coach.", cfg, exercise,
        {"step-1": {"output": {"top_values": [{"value": "认可", "evidence": {"summary": "你重视自己的努力被理解"}}]}},
         "step-2": {"output": {"groups": [{"umbrella": "联结", "keywords": ["认可"]}]}}},
        {"clarifications": []},
    )

    assert "CH04 STEP-3 VALUE CONTEXT" in user
    assert "你重视自己的努力被理解" in user
    assert "CH04 STEP-3 CONTROLLED-VALUE CONTRACT" in system
    assert "original five answers or 30-question text" in system


def test_ch04_step3_proposal_prompt_contains_only_current_batch_values():
    from app.runtime.assembler import build_step_prompt

    cfg = {"chapter_id": "ch04", "chapter_title": "重要的事", "core_concepts": [], "guiding_questions": [], "step_context": {"references": []}}
    exercise = {
        "step_id": "step-3", "instruction": "可控性检验", "user_action": "审阅",
        "references": [{"from_exercise": "step-1", "fields": ["top_values"]}, {"from_exercise": "step-2", "fields": ["groups"]}],
        "input_schema": [], "output_fields": [{"name": "conversions", "type": "editable_list"}],
    }
    prior = {
        "step-1": {"output": {"top_values": [
            {"value": "认可", "evidence": {"summary": "希望努力被理解"}},
            {"value": "自由", "evidence": {"summary": "希望自主安排生活"}},
        ]}},
        "step-2": {"output": {"groups": [{"umbrella": "自主", "keywords": ["认可", "自由"]}]}},
    }
    system, user = build_step_prompt(
        "You are a value coach.", cfg, exercise, prior,
        {"clarifications": [{"value": "认可", "answer": "希望作品被真正理解"}]},
    )

    context_line = user.split("[CH04 STEP-3 VALUE CONTEXT]", 1)[1].splitlines()[1]
    context = json.loads(context_line)
    assert [item["value"] for item in context] == ["认可"]
    assert "[prior reference]" not in user


@pytest.mark.asyncio
async def test_ch04_step3_proposal_runs_high_thinking_in_batches_of_three(monkeypatch):
    from app.runtime import agent

    batch_sizes, call_kwargs = [], []

    def fake_build(*args, **kwargs):
        answers = args[4]
        return "system", json.dumps(answers, ensure_ascii=False)

    async def fake_call(**kwargs):
        call_kwargs.append(kwargs)
        batch = json.loads(kwargs["user"])["clarifications"]
        batch_sizes.append(len(batch))
        return json.dumps({"phase": "proposal", "conversions": [
            {"value": item["value"], "type": "other", "assessment": "convert_candidate", "converted_to": item["value"] + "-可控", "why_chain": [], "decision": "pending"}
            for item in batch
        ]}, ensure_ascii=False)

    monkeypatch.setattr(agent, "build_step_prompt", fake_build)
    monkeypatch.setattr(agent, "call_llm", fake_call)
    answers = {"clarifications": [
        {"value": f"词{i}", "answer": f"依据{i}"} for i in range(7)
    ]}
    result = await agent._run_ch04_step3_proposal_batches(
        role={"provider": "deepseek", "model": "deepseek-v4-flash", "system_prompt": "role", "temperature": 0.5, "max_tokens": 4000},
        cfg={"chapter_id": "ch04"}, exercise={"step_id": "step-3"}, prior={},
        user_answers=answers, chapter_md="", profile={}, preserve_output=None,
    )
    parsed = json.loads(result["raw"])

    assert sorted(batch_sizes, reverse=True) == [3, 3, 1]
    assert [item["value"] for item in parsed["conversions"]] == [f"词{i}" for i in range(7)]
    assert parsed["batch_warnings"] == []
    assert all(kwargs["thinking_mode"] == "enabled" for kwargs in call_kwargs)
    assert all(kwargs["max_tokens"] == 4000 for kwargs in call_kwargs)
    assert sorted(kwargs["reasoning_retry"] for kwargs in call_kwargs) == [False, True, True]


@pytest.mark.asyncio
async def test_ch04_step3_length_batch_splits_to_single_and_keeps_partial_success(monkeypatch):
    from app.runtime import agent
    from app.services.llm_client import LLMEmptyResponseError

    batch_sizes = []

    def fake_build(*args, **kwargs):
        return "system", json.dumps(args[4], ensure_ascii=False)

    async def fake_call(**kwargs):
        batch = json.loads(kwargs["user"])["clarifications"]
        batch_sizes.append(len(batch))
        if len(batch) > 1 or batch[0]["value"] == "乙":
            raise LLMEmptyResponseError("LLM returned an empty response (finish_reason=length)")
        item = batch[0]
        return json.dumps({"conversions": [{
            "value": item["value"], "type": "other", "assessment": "convert_candidate",
            "converted_to": "自主表达", "why_chain": [], "decision": "pending",
        }]}, ensure_ascii=False)

    monkeypatch.setattr(agent, "build_step_prompt", fake_build)
    monkeypatch.setattr(agent, "call_llm", fake_call)
    result = await agent._run_ch04_step3_proposal_batches(
        role={"provider": "deepseek", "model": "deepseek-v4-flash", "system_prompt": "role", "temperature": 0.5, "max_tokens": 4000},
        cfg={"chapter_id": "ch04"}, exercise={"step_id": "step-3"}, prior={},
        user_answers={"clarifications": [{"value": "甲", "answer": "一"}, {"value": "乙", "answer": "二"}]},
        chapter_md="", profile={}, preserve_output=None,
    )
    parsed = json.loads(result["raw"])

    assert sorted(batch_sizes) == [1, 1, 2]
    assert [item["value"] for item in parsed["conversions"]] == ["甲"]
    assert parsed["batch_warnings"] == ["乙"]


def test_ch04_step4_prompt_ranks_core_groups_and_uses_confirmed_members_as_evidence():
    from app.runtime.assembler import build_step_prompt

    cfg = {"chapter_id": "ch04", "chapter_title": "重要的事", "core_concepts": [], "guiding_questions": [], "step_context": {"references": []}}
    exercise = {
        "step_id": "step-4", "instruction": "金字塔", "user_action": "排序",
        "references": [{"from_exercise": "step-2", "fields": ["groups"]}, {"from_exercise": "step-3", "fields": ["conversions"]}],
        "input_schema": [], "output_fields": [
            {"name": "ranked", "type": "editable_list"},
            {"name": "support_links", "type": "list"},
            {"name": "final_purpose", "type": "json"},
            {"name": "gap_note", "type": "text"},
        ],
    }
    system, user = build_step_prompt(
        "You are a value coach.", cfg, exercise,
        {"step-2": {"output": {"groups": [
            {"umbrella": "联结", "keywords": ["想出名", "好奇心", "父母认可"]},
            {"umbrella": "自主", "keywords": ["自由"]},
        ]}},
         "step-3": {"output": {"conversions": [
             {"value": "想出名", "decision": "convert", "converted_to": "主动表达", "evidence_summary": "希望自己的想法被看见"},
             {"value": "好奇心", "type": "self", "decision": "keep", "evidence_summary": "愿意持续探索新事物"},
             {"value": "父母认可", "type": "other", "decision": "keep", "evidence_summary": "在意和家人的关系"},
             {"value": "自由", "type": "self", "decision": "keep", "evidence_summary": "希望自主安排生活"},
         ]}}},
        {},
    )

    context_line = user.split("[CH04 STEP-4 CONFIRMED VALUE CONTEXT]", 1)[1].splitlines()[1]
    context = json.loads(context_line)
    assert [item["value"] for item in context] == ["联结", "自主"]
    assert [item["value"] for item in context[0]["members"]] == ["主动表达", "好奇心", "父母认可"]
    assert context[0]["members"][0]["personal_basis"] == "希望自己的想法被看见"
    assert "rank every core group theme exactly once" in system
    assert "adjacent lower-to-higher support relationship" in system
    assert "Do not treat member values as pyramid levels" in system
    assert "original five answers or 30-question text" in system


@pytest.mark.asyncio
async def test_ch04_step4_api_retries_empty_ranking_and_preserves_upstream_steps(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    import app.config
    import app.db

    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with open(
        r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch04.json",
        "r",
        encoding="utf-8",
    ) as handle:
        chapter_config = json.load(handle)
    step2_output = {
        "groups": [
            {"umbrella": "安稳从容", "keywords": ["简单"], "locked": False},
            {"umbrella": "自我实现", "keywords": ["成长"], "locked": False},
        ]
    }
    step3_output = {
        "conversions": [
            {"group": "安稳从容", "value": "简单", "type": "self", "decision": "keep"},
            {"group": "自我实现", "value": "成长", "type": "self", "decision": "keep"},
        ]
    }
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active) VALUES ('ch04', 1, ?, 1)",
            (json.dumps(chapter_config, ensure_ascii=False),),
        )
        conn.execute(
            """INSERT INTO llm_roles
               (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES ('step4-role', 'career_counselor', 'test', 'role', 'deepseek', 'deepseek-chat', 0.5, 4000, 1)"""
        )
        for run_id, step_id, output in (
            ("step2", "step-2", step2_output),
            ("step3", "step-3", step3_output),
        ):
            conn.execute(
                """INSERT INTO step_runs
                   (id, chapter_id, step_id, user_answers, role_id, rendered_prompt,
                    llm_response, parsed_output, status, submitted_at)
                   VALUES (?, 'ch04', ?, '{}', '', '', 'ok', ?, 'submitted', datetime('now'))""",
                (run_id, step_id, json.dumps(output, ensure_ascii=False)),
            )

    responses = [
        {"ranked": [], "support_links": [], "final_purpose": {}, "gap_note": ""},
        {
            "ranked": [
                {"value": "安稳从容", "locked": False},
                {"value": "自我实现", "locked": False},
            ],
            "support_links": [{
                "from_value": "安稳从容",
                "to_value": "自我实现",
                "reason": "内在安稳减少彷徨，使人更能持续投入成长。",
            }],
            "final_purpose": {
                "value": "自我实现",
                "life_state": "持续成长并活出自己的可能性",
                "reason": "安稳从容是行动基础，而成长本身是最终想抵达的生活状态。",
            },
            "gap_note": "",
        },
    ]
    calls = []

    async def fake_call_llm(**kwargs):
        calls.append(kwargs)
        return json.dumps(responses[min(len(calls) - 1, 1)], ensure_ascii=False)

    import app.runtime.agent as agent_mod
    monkeypatch.setattr(agent_mod, "call_llm", fake_call_llm)
    import app.main as main_mod
    reload(main_mod)
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://test") as client:
        before_step2 = (await client.get("/api/chapters/ch04/steps/step-2")).json()["current_run"]["parsed_output"]
        before_step3 = (await client.get("/api/chapters/ch04/steps/step-3")).json()["current_run"]["parsed_output"]
        response = await client.post(
            "/api/chapters/ch04/steps/step-4/run",
            json={"user_answers": {}},
        )
        after_step2 = (await client.get("/api/chapters/ch04/steps/step-2")).json()["current_run"]["parsed_output"]
        after_step3 = (await client.get("/api/chapters/ch04/steps/step-3")).json()["current_run"]["parsed_output"]

    assert response.status_code == 200, response.text
    assert len(calls) == 2
    assert [item["value"] for item in response.json()["parsed_output"]["ranked"]] == ["安稳从容", "自我实现"]
    assert response.json()["parsed_output"]["final_purpose"]["value"] == "自我实现"
    assert before_step2 == after_step2
    assert before_step3 == after_step3


@pytest.mark.asyncio
async def test_ch04_step4_api_reports_failure_when_repair_is_still_invalid(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    monkeypatch.setenv("DISABLE_OPEN_QUESTIONS_EXTRACT", "1")
    import app.config
    import app.db

    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with open(
        r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch04.json",
        "r",
        encoding="utf-8",
    ) as handle:
        chapter_config = json.load(handle)
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active) VALUES ('ch04', 1, ?, 1)",
            (json.dumps(chapter_config, ensure_ascii=False),),
        )
        conn.execute(
            """INSERT INTO llm_roles
               (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES ('step4-role', 'career_counselor', 'test', 'role', 'deepseek', 'deepseek-chat', 0.5, 4000, 1)"""
        )
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt,
                llm_response, parsed_output, status, submitted_at)
               VALUES ('step2', 'ch04', 'step-2', '{}', '', '', 'ok', ?, 'submitted', datetime('now'))""",
            (json.dumps({"groups": [{"umbrella": "真实", "keywords": ["真诚"], "locked": False}]}, ensure_ascii=False),),
        )
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt,
                llm_response, parsed_output, status, submitted_at)
               VALUES ('step3', 'ch04', 'step-3', '{}', '', '', 'ok', ?, 'submitted', datetime('now'))""",
            (json.dumps({"conversions": [{"group": "真实", "value": "真诚", "type": "self", "decision": "keep"}]}, ensure_ascii=False),),
        )

    calls = []

    async def fake_call_llm(**kwargs):
        calls.append(kwargs)
        return json.dumps({"ranked": [], "support_links": [], "final_purpose": {}, "gap_note": ""})

    import app.runtime.agent as agent_mod
    monkeypatch.setattr(agent_mod, "call_llm", fake_call_llm)
    import app.main as main_mod
    reload(main_mod)
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://test") as client:
        response = await client.post(
            "/api/chapters/ch04/steps/step-4/run",
            json={"user_answers": {}},
        )
        current = (await client.get("/api/chapters/ch04/steps/step-4")).json()["current_run"]

    assert response.status_code == 502
    assert len(calls) == 2
    assert current["status"] == "failed"
    assert "ranked" in response.text


def test_ch04_step2_normalizes_legacy_values_without_losing_candidates(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    import app.config
    import app.db

    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with app.db.get_conn() as conn:
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status)
               VALUES ('step1', 'ch04', 'step-1', '{}', '', '', '', ?, 'submitted')""",
            (json.dumps({"top_values": [{"value": "热爱"}, {"value": "成长"}, {"value": "自主"}]}),),
        )

    from app.routers import steps

    normalized = steps._normalize_ch04_run_output(
        {
            "groups": [
                {"umbrella": "生机", "values": ["热爱", "成长", "模型虚构词"], "locked": False},
                {"umbrella": "自立", "keywords": ["自主", "热爱"], "locked": False},
            ],
            "ungrouped": ["不应持久化"],
        },
        "step-2",
        {"supplemental_keywords": [{"text": "创造"}]},
    )

    assert normalized == {
        "groups": [
            {"umbrella": "生机", "keywords": ["热爱", "成长"], "locked": False},
            {"umbrella": "自立", "keywords": ["自主"], "locked": False},
        ]
    }
    assert steps._validate_ch04_output(normalized, "step-2", {"supplemental_keywords": [{"text": "创造"}]}, require_complete=False) == []
    assert steps._validate_ch04_output(normalized, "step-2", {"supplemental_keywords": [{"text": "创造"}]}, require_complete=True) == ["all confirmed keywords must be assigned before submit: 创造"]

    locked_wins = steps._normalize_ch04_run_output(
        {
            "groups": [
                {"umbrella": "新建议", "keywords": ["热爱"], "locked": False},
                {"umbrella": "用户锁定", "keywords": ["热爱", "成长"], "locked": True},
            ]
        },
        "step-2",
        {"supplemental_keywords": []},
    )
    assert locked_wins["groups"] == [
        {"umbrella": "新建议", "keywords": [], "locked": False},
        {"umbrella": "用户锁定", "keywords": ["热爱", "成长"], "locked": True},
    ]


def test_ch04_step3_normalizes_every_confirmed_keyword_and_requires_confirmation(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    import app.config
    import app.db

    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with app.db.get_conn() as conn:
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status)
               VALUES ('step2', 'ch04', 'step-2', '{}', '', '', '', ?, 'submitted')""",
            (json.dumps({"groups": [{"umbrella": "联结", "keywords": ["认可", "好奇心"]}]}),),
        )

    from app.routers import steps

    normalized = steps._normalize_ch04_run_output(
        {"phase": "screening", "conversions": [{"keyword": "认可", "status": "other", "action": "clarify", "clarification": "你最在意被怎样认可？"}]},
        "step-3", {"clarifications": []},
    )
    assert [item["value"] for item in normalized["conversions"]] == ["认可", "好奇心"]
    assert normalized["conversions"][0]["question"] == "你最在意被怎样认可？"
    assert normalized["conversions"][1]["type"] == "uncertain"
    errors = steps._validate_ch04_output(normalized, "step-3", {}, require_complete=True)
    assert any("needs learner confirmation" in error for error in errors)

    confirmed = steps._normalize_ch04_run_output(
        {"phase": "proposal", "conversions": [
            {"value": "认可", "type": "other", "decision": "convert", "converted_to": "按自己的标准完成作品", "why_chain": ["想被理解", "仍可主动创造"]},
            {"value": "好奇心", "type": "self", "assessment": "keep", "decision": "keep"},
        ]},
        "step-3", {"clarifications": [{"value": "认可", "answer": "希望作品被真正理解"}]},
    )
    assert steps._validate_ch04_output(confirmed, "step-3", {}, require_complete=True) == []


def test_ch04_step3_proposal_merges_only_answered_items_into_saved_screening(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    import app.config
    import app.db

    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with app.db.get_conn() as conn:
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status)
               VALUES ('step2', 'ch04', 'step-2', '{}', '', '', '', ?, 'submitted')""",
            (json.dumps({"groups": [{"umbrella": "联结", "keywords": ["认可", "好奇心"]}]}),),
        )
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status)
               VALUES ('screening', 'ch04', 'step-3', '{}', '', '', '', ?, 'saved')""",
            (json.dumps({"conversions": [
                {"keyword": "认可", "status": "other", "action": "clarify", "clarification": "你期待怎样的认可？"},
                {"keyword": "好奇心", "status": "self", "action": "keep"},
            ]}),),
        )

    from app.routers import steps

    result = steps._normalize_ch04_run_output(
        {"conversions": [{"value": "认可", "type": "other", "assessment": "convert_candidate", "converted_to": "按自己的标准完成作品", "why_chain": ["希望创造被理解"]}]},
        "step-3", {"clarifications": [{"value": "认可", "answer": "希望作品被理解"}]},
    )

    assert result["phase"] == "proposal"
    assert [item["value"] for item in result["conversions"]] == ["认可", "好奇心"]
    assert result["conversions"][0]["converted_to"] == "按自己的标准完成作品"
    assert result["conversions"][1]["decision"] == "keep"


def test_failed_retry_keeps_a_saved_step_result(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    import app.config
    import app.db

    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with app.db.get_conn() as conn:
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status)
               VALUES ('saved-step', 'ch04', 'step-3', '{}', '', 'old prompt', 'old response', ?, 'saved')""",
            (json.dumps({"conversions": [{"value": "认可"}]}),),
        )

    from app.routers.steps import _mark_failed_run
    _mark_failed_run('saved-step', 'ch04', 'step-3', {"clarifications": []}, 'provider failed')
    with app.db.get_conn() as conn:
        row = conn.execute("SELECT status, parsed_output, error FROM step_runs WHERE id = 'saved-step'").fetchone()

    assert row["status"] == "saved"
    assert json.loads(row["parsed_output"])["conversions"][0]["value"] == "认可"
    assert row["error"] == "provider failed"


@pytest.mark.asyncio
async def test_ch04_step2_edit_persists_pool_and_submit_requires_complete_grouping(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    import app.config
    import app.db

    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with open(
        r"D:\AI_Project\What_Want\llm_prompt_design\config\chapters\chapter_config_ch04.json",
        "r",
        encoding="utf-8",
    ) as handle:
        chapter_config = json.load(handle)
    answers = {"supplemental_keywords": [{"text": "热爱"}, {"text": "成长"}, {"text": "创造"}], "excluded_top_values": []}
    with app.db.get_conn() as conn:
        conn.execute(
            "INSERT INTO chapter_configs (chapter_id, version, config_json, active) VALUES ('ch04', 1, ?, 1)",
            (json.dumps(chapter_config, ensure_ascii=False),),
        )
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status)
               VALUES ('step1', 'ch04', 'step-1', '{}', '', '', '', ?, 'submitted')""",
            (json.dumps({"top_values": [{"value": "热爱"}, {"value": "成长"}]}),),
        )
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status)
               VALUES ('step2', 'ch04', 'step-2', ?, 'psychologist', '', 'ok', ?, 'saved')""",
            (json.dumps(answers, ensure_ascii=False), json.dumps({"groups": []}, ensure_ascii=False)),
        )

    from httpx import ASGITransport, AsyncClient
    import app.main as main_mod

    reload(main_mod)
    async with AsyncClient(transport=ASGITransport(app=main_mod.app), base_url="http://test") as client:
        incomplete = await client.put(
            "/api/chapters/ch04/steps/step-2/output",
            json={
                "user_answers": answers,
                "parsed_output": {"groups": [{"umbrella": "生机", "values": ["热爱", "成长"], "locked": False}]},
            },
        )
        assert incomplete.status_code == 200, incomplete.text
        assert incomplete.json()["parsed_output"]["groups"][0]["keywords"] == ["热爱", "成长"]
        blocked = await client.post("/api/chapters/ch04/steps/step-2/submit")
        assert blocked.status_code == 409
        assert "创造" in blocked.text

        complete = await client.put(
            "/api/chapters/ch04/steps/step-2/output",
            json={
                "user_answers": answers,
                "parsed_output": {"groups": [{"umbrella": "生机", "keywords": ["热爱", "成长", "创造"], "locked": False}]},
            },
        )
        assert complete.status_code == 200, complete.text
        submitted = await client.post("/api/chapters/ch04/steps/step-2/submit")
        assert submitted.status_code == 200, submitted.text

    with app.db.get_conn() as conn:
        row = conn.execute("SELECT status, user_answers, parsed_output FROM step_runs WHERE id='step2'").fetchone()
    assert row["status"] == "submitted"
    assert json.loads(row["user_answers"])["supplemental_keywords"][-1]["text"] == "创造"
    assert json.loads(row["parsed_output"])["groups"][0]["keywords"] == ["热爱", "成长", "创造"]


def test_compaction_keeps_ch04_downstream_fields():
    from app.services.compaction import compact_profile

    profile = compact_profile(
        [{
            "values": ["真实"],
            "ranked": [{"value": "真实", "locked": True}],
            "work_purpose": "帮助别人厘清方向",
            "current_chapter": "ch04",
        }],
    )

    assert profile["values"] == ["真实"]
    assert profile["ranked"] == [{"value": "真实", "locked": True}]
    assert profile["work_purpose"] == "帮助别人厘清方向"


def test_mentor_context_contains_only_submitted_ch04_steps(tmp_path, monkeypatch):
    monkeypatch.setenv("WW_DB_PATH", str(tmp_path / "ww.db"))
    import app.config
    import app.db

    reload(app.config)
    reload(app.db)
    app.db.init_db()
    with app.db.get_conn() as conn:
        for step_id, answers, output in [
            ("step-1", {"q1": "尊敬诚实的人", "q2": "经历", "q3": "社会问题", "q4": "重视真实", "q5": "建议真实"}, {"top_values": ["真实"]}),
            ("step-2", {"supplemental_keywords": [{"text": "创造"}]}, {"groups": [{"umbrella": "真实", "keywords": ["诚实"]}]}),
            ("step-3", {}, {"conversions": [{"value": "认可", "type": "other"}]}),
            ("step-4", {}, {"ranked": [{"value": "真实"}]}),
            ("step-5", {"experiences": [{"experience": "帮助朋友"}]}, {"work_purpose": "帮助别人", "experience_map": []}),
        ]:
            conn.execute(
                """INSERT INTO step_runs
                   (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status)
                   VALUES (?, 'ch04', ?, ?, '', '', '', ?, 'submitted')""",
                (step_id, step_id, json.dumps(answers), json.dumps(output)),
            )
        conn.execute(
            """INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt, llm_response, parsed_output, status)
               VALUES ('unsubmitted', 'ch04', 'step-5', ?, '', '', '', ?, 'saved')""",
            (json.dumps({"experiences": [{"experience": "不要进入导师上下文"}]}), json.dumps({"work_purpose": "草稿"})),
        )

    from app.routers.chat import _load_submitted_chapter_context

    context = _load_submitted_chapter_context("ch04", "step-2")
    ids = [item["step_id"] for item in context["submitted_steps"]]
    assert ids == ["step-1", "step-2", "step-3", "step-4", "step-5"]
    assert context["current_step"]["output"]["groups"][0]["umbrella"] == "真实"
    assert "不要进入导师上下文" not in json.dumps(context, ensure_ascii=False)


@pytest.mark.asyncio
async def test_ch04_value_examples_endpoint_reads_the_100_value_list():
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/book/chapters/ch04/value-examples")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 100
    assert items[:3] == ["发现", "正确性", "达成"]
