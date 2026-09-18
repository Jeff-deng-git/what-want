"""Explicit cross-chapter producer/consumer requirements.

The handoff document defines ch07 as the first chapter whose step and mentor
must consume multiple prior chapter outputs. Keep this contract in one place so
the status endpoint and runtime gates cannot drift apart.
"""
from collections.abc import Mapping


CHAPTER_UPSTREAM_REQUIREMENTS = {
    "ch07": {
        "ch04": ("work_purpose", "values"),
        "ch05": ("talents",),
        "ch06": ("likes",),
    },
}


def get_upstream_requirements(chapter_id: str) -> dict[str, tuple[str, ...]]:
    """Return the declared producer chapter and profile fields for a chapter."""
    return dict(CHAPTER_UPSTREAM_REQUIREMENTS.get(chapter_id, {}))


def missing_profile_requirements(
    chapter_id: str,
    profile: Mapping | None,
) -> dict[str, list[str]]:
    """Return missing required profile fields grouped by producer chapter."""
    profile = profile or {}
    missing = {}
    for producer, fields in get_upstream_requirements(chapter_id).items():
        absent = [field for field in fields if profile.get(field) in (None, "", [], {})]
        if absent:
            missing[producer] = absent
    return missing


def get_upstream_context_status(chapter_id: str, user_id: str = "local") -> dict | None:
    """Return one readiness result shared by UI and all protected API actions."""
    requirements = get_upstream_requirements(chapter_id)
    if not requirements:
        return None
    from app.db import get_conn
    from app.runtime.config_loader import load_chapter_config, load_profile

    profile = load_profile(user_id)
    missing_profile = missing_profile_requirements(chapter_id, profile)
    upstream_status = {}
    for producer, fields in requirements.items():
        cfg = load_chapter_config(producer) or {}
        expected = [
            exercise.get("step_id")
            for exercise in cfg.get("exercises") or []
            if exercise.get("step_id")
        ]
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT step_id, status FROM step_runs WHERE chapter_id = ? AND stale = 0",
                (producer,),
            ).fetchall()
        submitted = list(dict.fromkeys(row["step_id"] for row in rows if row["status"] == "submitted"))
        upstream_status[producer] = {
            "is_submitted": bool(expected) and all(step_id in submitted for step_id in expected),
            "submitted_count": len(submitted),
            "total_steps": len(expected),
            "required_profile_fields": list(fields),
            "missing_profile_fields": missing_profile.get(producer, []),
        }
    return {
        "upstream": list(requirements),
        "ready": all(
            item["is_submitted"] and not item["missing_profile_fields"]
            for item in upstream_status.values()
        ),
        "upstream_status": upstream_status,
        "missing_profile_fields": missing_profile,
    }
