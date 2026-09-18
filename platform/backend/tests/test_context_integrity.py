'''Cross-step and cross-chapter context integrity contracts.'''

import json
from pathlib import Path

import pytest

from app.runtime.assembler import (
    ContextIntegrityError,
    build_mentor_prompt,
    build_step_prompt,
    validate_step_references,
)
from app.runtime.context_requirements import get_upstream_requirements


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / 'llm_prompt_design' / 'config' / 'chapters'
CHAPTER_IDS = [f'ch{index:02d}' for index in range(1, 9)]
FEW_SHOT_CORRUPTION_MARKERS = ('??', '\ufffd')


def _config(chapter_id):
    return json.loads((CONFIG_DIR / f'chapter_config_{chapter_id}.json').read_text(encoding='utf-8'))


def test_config_declares_all_context_edges():
    expected_mentor_refs = {
        'ch02': ['misconceptions_cleared', 'external_voices'],
        'ch03': ['misconceptions_cleared', 'external_voices'],
        'ch05': ['work_purpose'],
        'ch06': ['talents', 'likes'],
        'ch07': ['talents', 'likes', 'work_purpose', 'values'],
        'ch08': ['values', 'work_purpose', 'talents', 'likes', 'ideal_works'],
    }
    for chapter_id, expected in expected_mentor_refs.items():
        assert _config(chapter_id)['mentor_hooks']['references'] == expected

    assert _config('ch03')['step_context']['references'] == []
    assert _config('ch03')['ui_context']['references'] == ['external_voices']

    ch04 = _config('ch04')['exercises']
    assert ch04[1]['references'] == [{'from_exercise': 'step-1', 'fields': ['top_values']}]
    assert ch04[2]['references'] == [
        {'from_exercise': 'step-1', 'fields': ['top_values']},
        {'from_exercise': 'step-2', 'fields': ['groups']},
    ]
    assert ch04[3]['references'] == [
        {'from_exercise': 'step-2', 'fields': ['groups']},
        {'from_exercise': 'step-3', 'fields': ['conversions']},
    ]
    assert ch04[4]['references'] == [{'from_exercise': 'step-4', 'fields': ['ranked']}]
    assert get_upstream_requirements('ch07') == {
        'ch04': ('work_purpose', 'values'),
        'ch05': ('talents',),
        'ch06': ('likes',),
    }


def test_ch01_output_contract_requires_book_grounded_commentary():
    cfg = _config('ch01')
    exercise = cfg['exercises'][0]
    field_names = [field['name'] for field in exercise['output_fields']]
    assert field_names == ['misconceptions_cleared', 'external_voices', 'commentary']
    checklist = exercise['input_schema'][0]
    assert [item['label'] for item in checklist['items']] == [
        '必须是能坚持一生的事',
        '找到想做的事时会有命中注定的感觉',
        '必须是对别人有益的事',
        '必须多行动才能找到',
        '想做的事不能成为工作',
    ]
    assert [item['right'] for item in checklist['items']] == [
        '做“现在最想做的事”就可以了',
        '即使找到了想做的事，一开始也只是处在感兴趣的阶段',
        '为自己而活也是在帮助别人',
        '了解自己才能找到想做的事',
        '想做的事在自己心中，实现手段在社会中',
    ]
    template = cfg['output_template']
    assert '基于本章正文' in template
    assert '每一个编号分别建立一段解释' in template
    assert '不得只复述用户输入' in template
    assert '不是本章摘要' in template
    assert 'external_voices 原话' in template


def test_ch03_declares_three_circle_input_and_profile_output_contract():
    cfg = _config('ch03')
    exercise = cfg['exercises'][0]
    assert [field['name'] for field in exercise['input_schema']] == [
        'importance', 'talents', 'likes'
    ]
    assert all(field['type'] == 'list_of_items' for field in exercise['input_schema'])
    assert all(field['min_items'] == 3 and field['max_items'] == 5 for field in exercise['input_schema'])
    assert [field['name'] for field in exercise['output_fields']] == [
        'commentary', 'importance', 'talents', 'likes', 'intersection'
    ]
    assert exercise['output_fields'][0]['type'] == 'markdown'
    assert exercise['output_fields'][-1]['type'] == 'text'
    assert exercise['output_fields'][-1]['readonly'] is True
    assert cfg['mentor_hooks']['references'] == ['misconceptions_cleared', 'external_voices']


def test_ch04_output_contract_matches_prd():
    cfg = _config('ch04')
    step3 = next(ex for ex in cfg['exercises'] if ex['step_id'] == 'step-3')
    step5 = next(ex for ex in cfg['exercises'] if ex['step_id'] == 'step-5')
    assert 'type:self|other|uncertain' in step3['output']
    assert 'decision:pending|keep|convert' in step3['output']
    assert [field['name'] for field in step5['output_fields']] == [
        'work_purpose', 'reasoning', 'experience_map'
    ]
    assert step5['output_fields'][1]['type'] == 'markdown'
    frontend = (PROJECT_ROOT / 'platform' / 'frontend' / 'index.html').read_text(encoding='utf-8')
    for marker in ('converted_to', 'why_chain', 'experience_map'):
        assert marker in frontend

def test_ch03_step_prompt_does_not_include_prior_profile():
    cfg = _config('ch03')
    exercise = cfg['exercises'][0]
    system, user = build_step_prompt(
        'reflection coach',
        cfg,
        exercise,
        {},
        {'likes': [{'text': '心理学'}], 'talents': [{'text': '共情'}], 'importance': [{'text': '帮助别人'}]},
        profile={'misconceptions_cleared': ['2. 找到想做的事时会有命中注定的感觉'], 'external_voices': {'2': '别人的声音'}},
    )
    assert '[CH03 ANALYSIS CONTRACT]' in system
    assert '[learner cross-chapter profile]' not in system
    assert '命中注定' not in system
    assert '别人的声音' not in system
    assert '心理学' in user


def test_step_prompt_falls_back_to_mentor_refs_when_step_context_is_missing():
    cfg = _config('ch03')
    cfg.pop('step_context', None)
    exercise = cfg['exercises'][0]
    system, _ = build_step_prompt(
        'reflection coach',
        cfg,
        exercise,
        {},
        {'likes': [{'text': '心理学'}], 'talents': [{'text': '共情'}], 'importance': [{'text': '帮助别人'}]},
        profile={'external_voices': {'2': '兼容旧章节的声音'}},
    )
    assert '[learner cross-chapter profile]' in system
    assert '兼容旧章节的声音' in system


def test_step_prompt_binds_commentary_to_user_answers():
    cfg = _config('ch01')
    exercise = cfg['exercises'][0]
    system, user = build_step_prompt(
        'career counselor',
        cfg,
        exercise,
        {},
        {
            'misconceptions': {
                'checked_ids': ['1'],
                'external_voices': {'1': '家人说选错行就完了'},
            }
        },
    )
    assert '[CH01 COMMENTARY CONTRACT]' in system
    assert '[CH01 SELECTED MISCONCEPTION EVIDENCE]' in system
    assert '家人说选错行就完了' in system
    assert 'Do not write a generic chapter summary.' not in system
    assert '家人说选错行就完了' in user


def test_mentor_prompt_always_includes_profile_even_without_hook_references():
    profile = {
        'misconceptions_cleared': ['1｜唯一正确的事'],
        'external_voices': {'1': '家人说选错行就完了'},
        'current_chapter': 'ch01',
    }
    system, _ = build_mentor_prompt('mentor role', profile, {'references': []}, [], '我想聊聊')
    assert '[learner profile]' in system
    assert 'external_voices' in system
    assert '家人说选错行就完了' in system


def test_mentor_prompt_includes_submitted_step_context():
    step_context = {
        'step_id': 'step-1',
        'output': {'commentary': '书中解释了这个误区', 'misconceptions_cleared': ['1']},
    }
    system, _ = build_mentor_prompt('mentor role', {}, {'references': []}, [], '继续说', step_context=step_context)
    assert '[current submitted step context]' in system
    assert '书中解释了这个误区' in system


def test_mentor_prompt_uses_chapter_knowledge_without_quote_style():
    system, _ = build_mentor_prompt(
        'mentor role',
        {},
        {'references': []},
        [],
        '我担心选错方向',
        chapter_context={
            'title': '阻碍找到想做的事的5种误区',
            'core_concepts': ['先从现在最想试的小事开始'],
            'guiding_questions': ['你最担心的成本是什么？'],
        },
    )
    assert '[chapter understanding]' in system
    assert '先从现在最想试的小事开始' in system
    assert 'do not quote them verbatim' in system
    assert '不把用户上一句话中的每个抽象词拆成新的问题' in system


def test_ch01_mentor_prompt_has_focus_and_convergence_rules():
    cfg = _config('ch01')
    profile = {
        'misconceptions_cleared': ['1. 唯一正确的事', '2. 必须靠直觉', '3. 必须从喜欢开始'],
        'external_voices': {'1': '男怕入错行', '2': '跟着感觉走', '3': '兴趣是最好的老师'},
    }
    chapter_context = {
        'title': cfg['chapter_title'],
        'core_concepts': cfg['core_concepts'],
        'guiding_questions': cfg['guiding_questions'],
        'misconception_items': cfg['exercises'][0]['input_schema'][0]['items'],
    }
    system, _ = build_mentor_prompt(
        'mentor role',
        profile,
        {'focus': '解构误区', 'references': []},
        ['用户：那第二个呢？', '刘老师：先回应第一个误区。'],
        '我想知道第二个误区应该怎么做',
        step_context={'output': {'misconceptions_cleared': profile['misconceptions_cleared'], 'external_voices': profile['external_voices']}},
        chapter_context=chapter_context,
    )
    assert '[mentor convergence state]' in system
    assert 'active_focus_id' in system
    assert 'active_external_voice' in system
    assert 'active_chapter_principle' in system
    assert '同一焦点最多连续追问两轮' in system
    assert '必须先给出一个具体、低成本、可观察的行动' in system


def test_ch01_few_shots_are_not_corrupted():
    cfg = _config('ch01')
    examples = cfg['exercises'][0]['few_shot_examples'] + cfg['few_shot_examples']
    serialized = json.dumps(examples, ensure_ascii=False)
    assert '??' not in serialized
    assert '必须是对别人有益的事' in serialized
    assert '为自己而活也是在帮助别人' in serialized


def _iter_few_shot_strings(value, path=(), inside_few_shot=False):
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = (*path, str(key))
            yield from _iter_few_shot_strings(
                item,
                next_path,
                inside_few_shot or str(key).startswith('few_shot'),
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_few_shot_strings(item, (*path, str(index)), inside_few_shot)
    elif inside_few_shot and isinstance(value, str):
        yield '.'.join(path), value


def test_all_chapter_few_shots_are_not_corrupted():
    corrupted = []
    for chapter_id in CHAPTER_IDS:
        for path, text in _iter_few_shot_strings(_config(chapter_id)):
            for marker in FEW_SHOT_CORRUPTION_MARKERS:
                if marker in text:
                    corrupted.append((chapter_id, path, marker, text))
    assert not corrupted, f'corrupted few-shot text: {corrupted}'


def test_frontend_hides_step_chat_until_llm_output_exists():
    frontend = (PROJECT_ROOT / 'platform' / 'frontend' / 'index.html').read_text(encoding='utf-8')
    assert 'run?.parsed_output && !isSubmitted' in frontend
    assert "isCh01MisconceptionStep && parsed.commentary" in frontend


def test_frontend_restores_failed_step_answers_for_editing():
    frontend = (PROJECT_ROOT / 'platform' / 'frontend' / 'index.html').read_text(encoding='utf-8')
    load_runs = frontend.split('async function loadCurrentRuns', 1)[1].split('function renderStepNav', 1)[0]
    assert "currentRunByStep[step.step_id] = run;" in load_runs
    assert "currentRunByStep[step.step_id] = null;" not in load_runs
    assert '\u4e0a\u6b21\u8fd0\u884c\u5931\u8d25\uff0c\u5df2\u6062\u590d\u6700\u8fd1\u4e00\u6b21\u8f93\u5165\u3002\u4f60\u53ef\u4ee5\u4fee\u6539\u540e\u91cd\u65b0\u8fd0\u884c\u3002' in frontend


def test_frontend_has_ch03_live_venn_hook():
    frontend = (PROJECT_ROOT / 'platform' / 'frontend' / 'index.html').read_text(encoding='utf-8')
    assert 'renderCh03Venn' in frontend
    assert 'updateCh03Venn' in frontend
    assert 'data-ch03-overlap' in frontend


def test_frontend_does_not_retry_chat_post():
    frontend = (PROJECT_ROOT / 'platform' / 'frontend' / 'index.html').read_text(encoding='utf-8')
    send_call = frontend.split('/api/chapters/${chapterId}/chat/send', 1)[1].split('async function clearChat', 1)[0]
    assert 'retry: 0' in send_call
    assert 'timeout: 180000' in send_call


def test_frontend_allows_long_llm_runs_without_retrying_post():
    frontend = (PROJECT_ROOT / 'platform' / 'frontend' / 'index.html').read_text(encoding='utf-8')
    run_call = frontend.split('/api/chapters/${chapterId}/steps/${stepId}/run', 1)[1].split('async function submitStep', 1)[0]
    assert 'timeout: 180000' in run_call
    assert 'retry: 0' in run_call
    assert "if (chapterId === 'ch02') ch02StageByStep[stepId] = 2;" in run_call


def test_missing_step_reference_is_an_explicit_integrity_error():
    exercise = {'references': [{'from_exercise': 'step-1', 'fields': ['top_values']}]}
    errors = validate_step_references(exercise, {})
    assert errors == ['step-1 has no submitted output']


@pytest.mark.asyncio
async def test_compaction_merges_prior_profile_with_new_chapter(client):
    from app.db import get_conn
    from app.routers.steps import _maybe_compact

    config = {
        'chapter_id': 'ch02',
        'exercises': [
            {
                'step_id': 'step-1',
                'output_fields': [{'name': 'internal_external_ratio', 'type': 'json'}],
            }
        ],
    }
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO chapter_configs (chapter_id, version, config_json, active) VALUES (?, ?, ?, 1)',
            ('ch02', 1, json.dumps(config, ensure_ascii=False)),
        )
        conn.execute(
            'INSERT INTO learner_profiles (user_id, profile_json) VALUES (?, ?)',
            ('local', json.dumps({'misconceptions_cleared': ['1'], 'external_voices': {'1': '父亲'}})),
        )
        conn.execute(
            '''INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt,
                llm_response, parsed_output, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'submitted')''',
            ('run-1', 'ch02', 'step-1', '{}', 'career_counselor', '', '{}',
             json.dumps({'internal_external_ratio': {'internal': 70, 'external': 30}})),
        )

    profile = _maybe_compact('ch02')
    assert profile['misconceptions_cleared'] == ['1']
    assert profile['external_voices'] == {'1': '父亲'}
    assert profile['internal_external_ratio']['internal'] == 70


@pytest.mark.asyncio
async def test_chat_bridge_sends_real_submitted_step_context(client, monkeypatch):
    from app.db import get_conn
    from app.runtime import agent as agent_mod

    cfg = _config('ch01')
    with get_conn() as conn:
        conn.execute(
            '''INSERT INTO llm_roles
               (id, name, description, system_prompt, provider, model, temperature, max_tokens, enabled)
               VALUES (?, 'mentor', '', 'You are a mentor.', 'deepseek', 'deepseek-chat', 0.5, 600, 1)''',
            ('mentor-role',),
        )
        conn.execute(
            'INSERT INTO chapter_configs (chapter_id, version, config_json, active) VALUES (?, ?, ?, 1)',
            ('ch01', 1, json.dumps(cfg, ensure_ascii=False)),
        )
        conn.execute(
            'INSERT INTO learner_profiles (user_id, profile_json) VALUES (?, ?)',
            ('local', json.dumps({'external_voices': {'1': '父亲'}})),
        )
        conn.execute(
            '''INSERT INTO step_runs
               (id, chapter_id, step_id, user_answers, role_id, rendered_prompt,
                llm_response, parsed_output, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'submitted')''',
            ('submitted-1', 'ch01', 'step-1', '{}', 'career_counselor', '', '{}',
             json.dumps({'commentary': '来自本章正文的分析', 'misconceptions_cleared': ['1']})),
        )

    captured = {}

    async def fake_call(*, system, user, **kwargs):
        captured['system'] = system
        captured['user'] = user
        return '收到，我们继续。'

    monkeypatch.setattr(agent_mod, 'call_llm', fake_call)
    response = await client.post(
        '/api/chapters/ch01/chat/send',
        json={'content': '我想继续聊这个误区', 'step_id': 'step-1'},
    )
    assert response.status_code == 200, response.text
    assert '来自本章正文的分析' in captured['system']
    assert '父亲' in captured['system']
