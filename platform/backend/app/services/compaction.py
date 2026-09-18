"""Compact submitted step outputs into the cross-chapter learner profile."""
from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from typing import Any

logger = logging.getLogger(__name__)

PROFILE_FIELDS = (
    "misconceptions_cleared",
    "external_voices",
    "internal_external_ratio",
    "reclaim_item",
    "likes",
    "talents",
    "importance",
    "work_purpose",
    "values",
    "ranked",
    "intersection",
    "success_statement",
    "ideal_works",
    "formula",
    "current_chapter",
    "open_questions",
    "milestones",
)
PROFILE_FIELD_ALIASES = {
    "top_values": "values",
}

STRUCTURED_FIELDS = frozenset({
    "values", "work_purpose", "talents", "likes", "importance",
    "intersection", "ranked", "success_statement", "formula",
    "ideal_works",
    "misconceptions_cleared", "milestones",
})
MANDATORY_DOWNSTREAM_FIELDS = frozenset({
    "likes", "talents", "importance", "values", "ranked", "work_purpose", "intersection",
    "ideal_works",
})
MAX_PROFILE_TOKENS = 800
OPEN_QUESTIONS_MAX = 3
OPEN_QUESTIONS_LLM_TIMEOUT_S = 8.0


def _normalise_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _normalise_value(item) for key, item in value.items()}
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalise_value(item) for item in value]
    return str(value)


def _normalise_profile_field(field: str, value: Any) -> Any:
    normalized = _normalise_value(value)
    if field == "talents" and isinstance(normalized, list):
        cleaned = []
        for item in normalized:
            if isinstance(item, Mapping):
                cleaned.append({key: value for key, value in item.items() if key != "locked"})
            else:
                cleaned.append(item)
        return cleaned
    return normalized


def _flatten_outputs(outputs: Iterable[Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for output in outputs:
        if not isinstance(output, Mapping):
            continue
        for field in PROFILE_FIELDS:
            if field in output and output[field] not in (None, "", [], {}):
                merged[field] = _normalise_profile_field(field, output[field])
        for source, target in PROFILE_FIELD_ALIASES.items():
            if source in output and output[source] not in (None, "", [], {}):
                merged[target] = _normalise_value(output[source])
    return merged


def _trim_to_budget(profile: dict[str, Any], max_tokens: int) -> dict[str, Any]:
    """Keep JSON compact; token estimate is intentionally conservative."""
    if max_tokens <= 0:
        return {}
    result = dict(profile)
    while result:
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        if len(encoded) <= max_tokens * 4:
            return result
        removable = next(
            (
                field for field in PROFILE_FIELDS
                if field in result
                and field not in STRUCTURED_FIELDS
                and field not in MANDATORY_DOWNSTREAM_FIELDS
            ),
            None,
        )
        if removable is None:
            removable = next(
                (field for field in PROFILE_FIELDS if field in result and field not in MANDATORY_DOWNSTREAM_FIELDS),
                None,
            )
        if removable is None:
            removable = next(iter(result))
        result.pop(removable)
    return {}


def compact_profile(outputs: Iterable[Any], *, current_chapter: str | None = None,
                    max_tokens: int = MAX_PROFILE_TOKENS,
                    open_questions: list[str] | None = None) -> dict[str, Any]:
    """Build a tolerant profile from submitted parsed outputs.

    Empty or malformed outputs are ignored. ``open_questions`` is set from the
    caller-supplied list (Q8: cheap LLM extraction happens out-of-band, callers
    pre-extract and pass in). Without a list we default to empty.
    """
    profile = _flatten_outputs(outputs)
    if current_chapter:
        profile["current_chapter"] = current_chapter
    if open_questions is not None:
        profile["open_questions"] = list(open_questions)[:OPEN_QUESTIONS_MAX]
    else:
        profile.setdefault("open_questions", [])
    return _trim_to_budget(profile, max_tokens)


def serialize_profile(profile: Mapping[str, Any], *, max_tokens: int = MAX_PROFILE_TOKENS) -> str:
    """Serialize a profile using the same budget guard as compaction."""
    compacted = _trim_to_budget(dict(profile), max_tokens)
    return json.dumps(compacted, ensure_ascii=False, separators=(",", ":"))


async def extract_open_questions(outputs: Iterable[Any], profile: Mapping[str, Any] | None,
                                 *, user_id: str = "local",
                                 chapter_id: str | None = None,
                                 llm_callable: Any | None = None,
                                 max_questions: int = OPEN_QUESTIONS_MAX) -> list[str]:
    """Cheap LLM extraction of unresolved questions (handoff Q8).

    Uses career_counselor role by default (with fallback to summary). The
    extraction is non-blocking by contract: any LLM failure logs a warning and
    returns []. Output is a list of short question strings, capped at
    max_questions. The result is persisted back into learner_profiles.
    """
    # Build a compact prompt payload from outputs + profile (skip empty).
    outputs_list = [o for o in (outputs or []) if isinstance(o, Mapping)]
    profile_excerpt = {k: profile.get(k) for k in PROFILE_FIELDS if profile and profile.get(k)} if profile else {}
    if not outputs_list and not profile_excerpt:
        return []
    payload = json.dumps({"outputs": outputs_list, "profile": profile_excerpt}, ensure_ascii=False, separators=(",", ":"))
    if len(payload) > 6000:
        payload = payload[:6000]
    system = (
        "You are a reflection coach. From the chapter outputs and existing "
        "learner profile, surface up to 3 unresolved questions the learner "
        "has not yet clarified. Each question must be a short Chinese "
        "sentence ending with a question mark. Output strict JSON: "
        '{"open_questions": ["q1", "q2", "q3"]}. No other text.'
    )
    user = "Inputs (JSON):\n" + payload
    if llm_callable is None:
        try:
            from app.runtime.config_loader import load_role
            from app.services.llm_client import call_llm
        except Exception as e:
            logger.warning("Q8: skipping extraction -- LLM client unavailable: %s", e)
            return []
        role = load_role("career_counselor") or load_role("summary")
        if not role:
            logger.warning("Q8: skipping extraction -- no LLM role found")
            return []
        try:
            raw = await call_llm(
                provider=role["provider"],
                model=role["model"],
                api_key=__import__("os").getenv("DEEPSEEK_API_KEY", ""),
                system=system,
                user=user,
                temperature=role.get("temperature", 0.5),
                max_tokens=role.get("max_tokens", 600),
                json_mode=True,
                timeout=OPEN_QUESTIONS_LLM_TIMEOUT_S,
            )
        except Exception as e:
            logger.warning("Q8: LLM call failed for %s/%s: %s", user_id, chapter_id, e)
            return []
    else:
        try:
            raw = await llm_callable(system=system, user=user)
        except Exception as e:
            logger.warning("Q8: injected llm_callable failed: %s", e)
            return []
    try:
        parsed = json.loads(raw)
        questions = parsed.get("open_questions") if isinstance(parsed, Mapping) else None
    except json.JSONDecodeError:
        logger.warning("Q8: LLM returned non-JSON, ignoring")
        return []
    if not isinstance(questions, list):
        return []
    out = []
    for q in questions:
        if isinstance(q, str) and q.strip():
            out.append(q.strip())
        if len(out) >= max_questions:
            break
    return out


async def extract_and_persist_open_questions(user_id: str, chapter_id: str,
                                             outputs: Iterable[Any] | None = None) -> list[str]:
    """Convenience: extract questions and persist into learner_profiles.

    Returns the new questions (also written to DB). Safe to call concurrently;
    uses save_profile (upsert) so existing fields are preserved by the caller
    pre-loading the profile.
    """
    from app.runtime.config_loader import load_profile, save_profile
    profile = load_profile(user_id) or {}
    new_qs = await extract_open_questions(outputs or [], profile, user_id=user_id, chapter_id=chapter_id)
    if not new_qs:
        return []
    merged = list(profile.get("open_questions") or [])
    for q in new_qs:
        if q not in merged:
            merged.append(q)
    profile["open_questions"] = merged[:OPEN_QUESTIONS_MAX * 2]
    save_profile(user_id, profile)
    logger.info("Q8: extracted %d open questions for %s/%s", len(new_qs), user_id, chapter_id)
    return new_qs
