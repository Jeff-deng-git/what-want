"""Unified Agent runtime -- single dispatcher for step / mentor / summary."""
import asyncio
import json
import logging
import os
from typing import Optional

from app.runtime.config_loader import load_role, load_chapter_config, load_profile
from app.runtime.assembler import (
    build_mentor_prompt,
    build_summary_prompt,
    build_step_prompt,
    requires_json_output,
    ContextIntegrityError,
    validate_step_references,
)
from app.runtime.context_requirements import missing_profile_requirements
from app.services.llm_client import LLMEmptyResponseError, call_llm

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 12
SUMMARY_MD_CAP = 12000
DEFAULT_USER_ID = "local"
MENTOR_COMPACTION_K = 20  # handoff Q7: every K mentor turns force a profile refresh
STEP_LLM_TIMEOUT_SECONDS = 120.0
MENTOR_LLM_TIMEOUT_SECONDS = 120.0

def _api_key():
    return os.getenv("DEEPSEEK_API_KEY", "")

def _mentor_turn_count():
    """Return the global mentor turn count (rows where role='mentor')."""
    from app.db import get_conn
    with get_conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS c FROM chapter_chat WHERE role = 'mentor'"
        ).fetchone()
    return row["c"]


def _mentor_should_compact():
    """True when the next mentor call would cross a K boundary (handoff Q7).

    We trigger when the existing mentor-row count is a positive multiple of K.
    Chat routers insert the new mentor row AFTER agent.run_mentor returns, so
    a count of exactly K means "20 mentor turns have already happened; refresh
    the profile before processing turn 21".
    """
    total = _mentor_turn_count()
    return total > 0 and total % MENTOR_COMPACTION_K == 0


def _force_mentor_compaction(user_id, chapter_id):
    """Force a profile refresh at the mentor K-turn milestone (handoff Q7 + Q8).

    Loads the existing profile, updates current_chapter, re-runs the
    compact_profile budget guard, then schedules a fire-and-forget LLM
    extraction of open_questions (Q8). The background task uses
    asyncio.create_task so the caller is not blocked on LLM latency.
    """
    import asyncio
    from app.services.compaction import compact_profile
    from app.runtime.config_loader import load_profile, save_profile
    existing = load_profile(user_id) or {}
    existing["current_chapter"] = chapter_id
    existing.setdefault("open_questions", [])
    refreshed = compact_profile([existing], current_chapter=chapter_id)
    save_profile(user_id, refreshed)
    logger.info(
        "mentor-triggered compaction for user=%s chapter=%s count=%d",
        user_id, chapter_id, _mentor_turn_count(),
    )
    # Q8: fire-and-forget open_questions extraction (non-blocking)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    from app.services.compaction import extract_and_persist_open_questions
    loop.create_task(extract_and_persist_open_questions(user_id, chapter_id))

async def run_mentor(chapter_id, user_id, user_msg, history=None, step_context=None):
    # handoff Q7: every MENTOR_COMPACTION_K mentor turns, force a profile refresh so
    # subsequent prompts see the learner's latest cross-chapter state.
    if _mentor_should_compact():
        _force_mentor_compaction(user_id, chapter_id)
    role = load_role("mentor") or load_role("career_counselor")
    if not role:
        raise RuntimeError("mentor role not found in llm_roles")
    cfg = load_chapter_config(chapter_id) or {}
    hook = cfg.get("mentor_hooks")
    profile = load_profile(user_id)
    from app.runtime.context_requirements import get_upstream_context_status
    readiness = get_upstream_context_status(chapter_id, user_id)
    if readiness and not readiness["ready"]:
        missing = "; ".join(
            producer + ": " + ", ".join(fields)
            for producer, fields in readiness["missing_profile_fields"].items()
        )
        detail = "required upstream context incomplete"
        if missing:
            detail += ": " + missing
        raise ContextIntegrityError(detail)
    chapter_context = {
        "title": cfg.get("chapter_title", ""),
        "core_concepts": cfg.get("core_concepts") or [],
        "guiding_questions": cfg.get("guiding_questions") or [],
    }
    misconception_items = []
    for exercise in cfg.get('exercises') or []:
        for field in exercise.get('input_schema') or []:
            if field.get('type') == 'checklist':
                misconception_items.extend(field.get('items') or [])
    chapter_context['misconception_items'] = misconception_items
    system, user = build_mentor_prompt(
        role["system_prompt"], profile, hook, list(history or []), user_msg,
        step_context=step_context,
        chapter_context=chapter_context,
    )
    mentor_max_tokens = max(int(role.get("max_tokens") or 600), 4000)
    return await call_llm(
        provider=role["provider"],
        model=role["model"],
        api_key=_api_key(),
        system=system,
        user=user,
        temperature=role.get("temperature", 0.7),
        max_tokens=mentor_max_tokens,
        json_mode=False,
        timeout=MENTOR_LLM_TIMEOUT_SECONDS,
        max_retries=0,
        reasoning_retry=False,
    )

async def run_summary(chapter_id, chapter_md, user_id=None):
    role = load_role("summary")
    if not role:
        raise RuntimeError("summary role not found in llm_roles")
    profile = load_profile(user_id) if user_id else None
    system, user = build_summary_prompt(role["system_prompt"], chapter_md, SUMMARY_MD_CAP, profile)
    raw = await call_llm(
        provider=role["provider"],
        model=role["model"],
        api_key=_api_key(),
        system=system,
        user=user,
        temperature=role.get("temperature", 0.7),
        max_tokens=role.get("max_tokens", 2000),
        json_mode=True,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("summary parse failed for %s: %s", chapter_id, raw[:200])
        raise

def _load_prior_outputs(chapter_id, exercise):
    """Load the latest submitted output for every configured source step."""
    refs = exercise.get("references") or []
    src_ids = []
    for ref in refs:
        source = ref.get("from_exercise")
        if source and source not in src_ids:
            src_ids.append(source)
    if not src_ids:
        return {}
    from app.db import get_conn
    result = {}
    with get_conn() as c:
        for source in src_ids:
            row = c.execute(
                """SELECT step_id, parsed_output FROM step_runs
                   WHERE chapter_id = ? AND status = 'submitted' AND stale = 0 AND step_id = ?
                   ORDER BY created_at DESC, rowid DESC LIMIT 1""",
                (chapter_id, source),
            ).fetchone()
            if not row:
                continue
            try:
                parsed = json.loads(row["parsed_output"]) if row["parsed_output"] else {}
            except (json.JSONDecodeError, TypeError):
                parsed = {}
            result[row["step_id"]] = {"answers": [], "output": parsed}
    return result


def _load_chapter_md(chapter_id):
    """Best-effort read of the chapter MD file. Returns "" on miss.

    Delegates to routers.book.get_chapter_md (single source of truth); safe
    to import here because routers/book.py has no runtime dependency.
    """
    try:
        from app.routers.book import get_chapter_md
        return get_chapter_md(chapter_id) or ""
    except Exception:
        return ""


CH04_STEP3_BATCH_SIZE = 3
CH04_STEP3_BATCH_CONCURRENCY = 3


def _step3_answered_clarifications(user_answers):
    if not isinstance(user_answers, dict):
        return []
    clarifications = user_answers.get("clarifications")
    if not isinstance(clarifications, list):
        return []
    result, seen = [], set()
    for item in clarifications:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value") or "").strip()
        answer = str(item.get("answer") or "").strip()
        key = " ".join(value.split()).casefold()
        if not value or not answer or key in seen:
            continue
        seen.add(key)
        result.append({"value": value, "answer": answer})
    return result


def _step3_batch_conversions(raw, expected):
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    raw_items = parsed.get("conversions") if isinstance(parsed, dict) else []
    if not isinstance(raw_items, list):
        return []
    expected_keys = {" ".join(item["value"].split()).casefold() for item in expected}
    result, seen = [], set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value") or item.get("keyword") or "").strip()
        key = " ".join(value.split()).casefold()
        if key not in expected_keys or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


async def _run_ch04_step3_proposal_batches(*, role, cfg, exercise, prior,
                                            user_answers, chapter_md, profile,
                                            preserve_output):
    """Run clarified values in small high-thinking batches and merge results.

    Each provider call keeps DeepSeek thinking explicitly enabled. A batch that
    still exhausts both the configured 4k completion budget and the existing 6k
    retry is split into single-value calls. A value that also fails alone is
    reported in batch_warnings while successful proposals remain usable.
    """
    clarifications = _step3_answered_clarifications(user_answers)
    batches = [
        clarifications[index:index + CH04_STEP3_BATCH_SIZE]
        for index in range(0, len(clarifications), CH04_STEP3_BATCH_SIZE)
    ]
    semaphore = asyncio.Semaphore(CH04_STEP3_BATCH_CONCURRENCY)
    traces = []

    async def invoke(batch):
        batch_answers = {"clarifications": batch}
        system, user = build_step_prompt(
            role["system_prompt"], cfg, exercise, prior, batch_answers,
            chapter_md=chapter_md, profile=profile,
            preserve_output=preserve_output,
        )
        traces.append((system, user))
        async with semaphore:
            raw = await call_llm(
                provider=role["provider"],
                model=role["model"],
                api_key=_api_key(),
                system=system,
                user=user,
                temperature=role.get("temperature", 0.7),
                max_tokens=role.get("max_tokens", 2000),
                json_mode=True,
                timeout=STEP_LLM_TIMEOUT_SECONDS,
                max_retries=0,
                reasoning_retry=len(batch) > 1,
                thinking_mode="enabled",
            )
        return _step3_batch_conversions(raw, batch)

    async def analyse(batch):
        try:
            conversions = await invoke(batch)
        except LLMEmptyResponseError:
            conversions = []
        returned_keys = {
            " ".join(str(item.get("value") or item.get("keyword") or "").split()).casefold()
            for item in conversions
        }
        missing = [
            item for item in batch
            if " ".join(item["value"].split()).casefold() not in returned_keys
        ]
        if not missing:
            return conversions, []
        if len(batch) == 1:
            return conversions, [batch[0]["value"]]
        fallback_results = await asyncio.gather(*(analyse([item]) for item in missing))
        warnings = []
        for fallback_conversions, fallback_warnings in fallback_results:
            conversions.extend(fallback_conversions)
            warnings.extend(fallback_warnings)
        return conversions, warnings

    results = await asyncio.gather(*(analyse(batch) for batch in batches))
    by_value, warning_values = {}, []
    for conversions, warnings in results:
        for item in conversions:
            key = " ".join(str(item.get("value") or item.get("keyword") or "").split()).casefold()
            if key and key not in by_value:
                by_value[key] = item
        warning_values.extend(warnings)
    ordered = []
    for clarification in clarifications:
        key = " ".join(clarification["value"].split()).casefold()
        if key in by_value:
            ordered.append(by_value[key])
    warning_keys, warnings = set(), []
    for value in warning_values:
        key = " ".join(value.split()).casefold()
        if key and key not in by_value and key not in warning_keys:
            warning_keys.add(key)
            warnings.append(value)
    raw = json.dumps({
        "phase": "proposal",
        "conversions": ordered,
        "batch_warnings": warnings,
    }, ensure_ascii=False)
    first_system = traces[0][0] if traces else ""
    batched_users = "\n\n".join(
        "[proposal batch " + str(index + 1) + "]\n" + user
        for index, (_, user) in enumerate(traces)
    )
    return {"raw": raw, "system_prompt": first_system, "user_prompt": batched_users}


async def run_step(chapter_id, step_id, user_answers, user_id=None,
                   return_details=False, preserve_output=None, repair_feedback=None):
    """Step agent (Option B exercises-native, no jinja2).

    Loads chapter_config -> exercise -> role by step_role_id (with fallback),
    assembles prompt via build_step_prompt (compact + select, 3k token guard),
    and calls LLM. Returns the raw text response; persistence is left to the
    caller (router or service) so we keep this layer pure.
    """
    cfg = load_chapter_config(chapter_id)
    if not cfg:
        raise RuntimeError("chapter config not found: " + str(chapter_id))
    exercise = None
    for ex in cfg.get("exercises") or []:
        if ex.get("step_id") == step_id or ex.get("name") == step_id:
            exercise = ex
            break
    if not exercise:
        raise RuntimeError("step not found: " + str(step_id) + " in " + str(chapter_id))
    step_role_id = exercise.get("step_role_id")
    if not step_role_id:
        step_role_id = "career_counselor"
    role = load_role(step_role_id)
    if not role:
        raise RuntimeError("step role not found: " + str(step_role_id))
    user_id = user_id or DEFAULT_USER_ID
    profile = load_profile(user_id)
    missing_profile = missing_profile_requirements(chapter_id, profile)
    if missing_profile:
        details = "; ".join(
            producer + ": " + ", ".join(fields)
            for producer, fields in missing_profile.items()
        )
        raise ContextIntegrityError("required upstream profile fields missing: " + details)
    prior = _load_prior_outputs(chapter_id, exercise)
    reference_errors = validate_step_references(exercise, prior)
    if reference_errors:
        raise ContextIntegrityError("; ".join(reference_errors))
    chapter_md = _load_chapter_md(chapter_id)
    if chapter_id == "ch04" and step_id == "step-3" and _step3_answered_clarifications(user_answers):
        result = await _run_ch04_step3_proposal_batches(
            role=role, cfg=cfg, exercise=exercise, prior=prior,
            user_answers=user_answers, chapter_md=chapter_md, profile=profile,
            preserve_output=preserve_output,
        )
        return result if return_details else result["raw"]
    system, user = build_step_prompt(
        role["system_prompt"], cfg, exercise, prior, user_answers,
        chapter_md=chapter_md, profile=profile,
        preserve_output=preserve_output,
    )
    if repair_feedback:
        user += (
            "\n\n[STRUCTURED OUTPUT REPAIR]\n"
            "The previous draft failed the application contract: " + str(repair_feedback)
            + "\nReturn one corrected JSON object only. Preserve the book-aligned method and do not omit required fields."
        )
    has_structured = requires_json_output(exercise)
    is_ch04_step4 = chapter_id == "ch04" and step_id == "step-4"
    raw = await call_llm(
        provider=role["provider"],
        model=role["model"],
        api_key=_api_key(),
        system=system,
        user=user,
        temperature=role.get("temperature", 0.7),
        max_tokens=max(role.get("max_tokens", 2000), 6000) if is_ch04_step4 else role.get("max_tokens", 2000),
        json_mode=has_structured,
        timeout=STEP_LLM_TIMEOUT_SECONDS,
        max_retries=0,
        reasoning_retry=not is_ch04_step4,
        thinking_mode="enabled" if is_ch04_step4 else None,
    )
    if return_details:
        return {"raw": raw, "system_prompt": system, "user_prompt": user}
    return raw
