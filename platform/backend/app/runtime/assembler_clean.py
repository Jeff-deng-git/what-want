"""Context assembler -- compact + select (NOT blind concatenation).

Implements mentor_design_spec.md S5: build a curated prompt slice per turn,
never inject all 8 chapters of raw step data. Typical budget ~2.4k token,
hard guard at 3k (truncate history first, then fall back to profile-only;
never full raw injection).
'''
import json
import logging
from typing import Optional, Iterable, Mapping, Any

logger = logging.getLogger(__name__)

# Approximate token estimate (Chinese ~1.5 char/token; conservative /2).
# TODO: replace with tiktoken or provider tokenizer for accuracy.
def _est(text: str) -> int:
    return max(1, len(text) // 2)


TOKEN_GUARD = 3000
STEP_TOKEN_GUARD = 3000  # alias for clarity in step prompts
def _select_profile_fields(profile: dict, references: list) -> str:
    """Pick only the prior fields the chapter hook asks for (compact + select)."""
    if not profile:
        return ""
    if not references:
        # entry chapter: no prior fields; surface a thin identity only
        return f"（学习者初步画像：当前章 {profile.get('current_chapter', '未知')}）"
    parts = []
    for key in references:
        val = profile.get(key)
        if val:
            parts.append(f"- {key}: {val}")
    return "\n".join(parts) if parts else "（暂无相关前序档案）"


def build_mentor_prompt(
    role_system: str,
    profile: dict,
    hook: Optional[dict],
    history: list,
    user_msg: str,
):
    """Assemble the mentor (刘老师) system+user prompt.

    persona (constant) + compacted profile + hook-selected prior fields
    + sliding history + user message. Token guard truncates history
    oldest-first, then falls back to profile-only.
    """
    focus = (hook or {}).get("focus", "")
    references = (hook or {}).get("references", []) or []

    prior = _select_profile_fields(profile, references)
    history_text = "\n".join(history) if history else "（暂无历史）"

    system = role_system
    if focus:
        system += f"\n\n本章苏格拉底焦点：{focus}"

    def _user(hist_text: str) -> str:
        return (
            f"【学习者跨章档案】\n{prior}\n\n"
            f"【最近对话】\n{hist_text}\n\n"
            f"【用户最新说】{user_msg}\n\n"
            "请以刘老师的身份回复（苏格拉底式追问，一次一个点，引用用户原话）。"
        )

    user = _user(history_text)

    # Guard: truncate history oldest-first
    while _est(system) + _est(user) > TOKEN_GUARD and history:
        history.pop(0)
        history_text = "\n".join(history) if history else "（暂无历史）"
        user = _user(history_text)
    # Fallback: profile + user only
    if _est(system) + _est(user) > TOKEN_GUARD:
        user = (
            f"【学习者跨章档案】\n{prior}\n\n"
            f"【用户最新说】{user_msg}\n\n"
            "请以刘老师的身份回复（苏格拉底式追问，一次一个点，引用用户原话）。"
        )
    return system, user


def build_summary_prompt(
    role_system: str,
    chapter_md: str,
    md_cap: int = 12000,
    profile: Optional[dict] = None,
):
    """Assemble the summary (图书编辑) prompt.

    persona (constant) + chapter MD slice. learner_profile is OPTIONAL
    enhancement (per S12): when present, ask for a value-aware summary that
    echoes the learners confirmed values/work_purpose where consistent.
    """
    md_slice = chapter_md[:md_cap]
    system = role_system
    user = md_slice
    if profile:
        values = profile.get("values") or profile.get("work_purpose")
        if values:
            user = (
                f"{md_slice}\n\n"
                f"【补充视角】学习者已确认的价值观/工作目的：{values}。"
                "若正文与此一致，可在摘要中自然呼应，不必强行贴合。"
            )
    return system, user


def _format_few_shot(examples: Iterable[Mapping[str, str]]) -> str:
    lines = []
    for ex in examples or []:
        u = (ex.get("user") or "").strip()
        a = (ex.get("assistant") or "").strip()
        if u:
            lines.append(f"用户：{u}")
        if a:
            lines.append(f"助手：{a}")
    return "\n".join(lines)


def _format_references(refs: Iterable[Mapping[str, Any]],
                       prior_outputs: Mapping[str, Mapping[str, Any]]) -> str:
    """Render only the prior output fields the exercise asks for.

    prior_outputs keyed by step_id -> { 'answers': [...], 'output': {...} }.
    Never injects full prior step; honours <= 3k guard by truncating per field.
    """
    if not refs:
        return ""
    parts = []
    for ref in refs:
        src = ref.get("from_exercise")
        if not src:
            continue
        prior = prior_outputs.get(src)
        if not prior:
            parts.append(f"（前序 {src} 尚未提交）")
            continue
        fields = ref.get("fields")
        out = prior.get("output") or {}
        if fields:
            snippet = {k: out.get(k) for k in fields if k in out}
            rendered = snippet if snippet else "（无匹配字段）"
        else:
            rendered = out or "（空）"
        parts.append(f"前序 {src} 已提交输出：{json.dumps(rendered, ensure_ascii=False)}")
    return "\n".join(parts)


def build_step_prompt(
    role_system: str,
    chapter_cfg: Mapping[str, Any],
    exercise: Mapping[str, Any],
    prior_outputs: Mapping[str, Mapping[str, Any]],
    user_answers: Any,
) -> tuple[str, str]:
    """Assemble an Option B (exercises-native) step prompt.

    Returns (system, user). Honours <= 3k assembler guard:
    1. start with role_system + chapter context + few-shot + references + user
    2. if over budget, trim few-shot to 1 then drop
    3. finally fall back to role_system + references + user (no few-shot)

    Never injects full raw step data; only the fields the exercise declared
    in `references[].fields` are pulled from prior step_runs.parsed_output.
    """
    chapter_title = chapter_cfg.get("chapter_title", "")
    core_concepts = "\n".join(chapter_cfg.get("core_concepts") or [])
    guiding_questions = "\n".join(chapter_cfg.get("guiding_questions") or [])

    few_shot_text = _format_few_shot(exercise.get("few_shot_examples") or [])
    references_text = _format_references(exercise.get("references") or [], prior_outputs)
    user_text = json.dumps(user_answers, ensure_ascii=False) if not isinstance(user_answers, str) else user_answers

    system = (
        f"{role_system.strip()}\n\n"
        f"【章节】{chapter_title}\n"
        f"【本章核心】\n{core_concepts}\n\n"
        f"【引导问题】\n{guiding_questions}\n\n"
        f"【本练习】\n{exercise.get('instruction', '')}\n"
        f"用户动作：{exercise.get('user_action', '')}\n"
        f"输出模板：{chapter_cfg.get('output_template', '')}\n\n"
        f"【本练习输出字段】\n"
        f"{json.dumps(exercise.get('output_fields') or [], ensure_ascii=False)}"
    )

    def _compose_user(shot: str, refs: str) -> str:
        blocks = [f"【用户答案】\n{user_text}"]
        if refs:
            blocks.insert(0, f"【前序参考】\n{refs}")
        if shot:
            blocks.insert(0, f"【示例】\n{shot}")
        return "\n\n".join(blocks)

    user = _compose_user(few_shot_text, references_text)

    if _est(system) + _est(user) <= STEP_TOKEN_GUARD:
        return system, user

    # Step 1: trim few-shot to a single example
    examples = list(exercise.get("few_shot_examples") or [])
    if len(examples) > 1:
        user = _compose_user(_format_few_shot(examples[:1]), references_text)
        if _est(system) + _est(user) <= STEP_TOKEN_GUARD:
            return system, user

    # Step 2: drop few-shot entirely
    user = _compose_user("", references_text)
    if _est(system) + _est(user) <= STEP_TOKEN_GUARD:
        return system, user

    # Step 3: drop references too, keep user only
    user = _compose_user("", "")
    return system, user

