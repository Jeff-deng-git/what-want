"""Config loader -- single source for runtime config (DB-backed).

Replaces hardcoded prompts in chat.py / summary.py / step_runner.py with
DB-driven config (llm_roles + chapter_configs + learner_profiles).

IMPORTANT: this module is the *runtime* reader. The JSON files under
llm_prompt_design/config/ are design sources consumed by seed scripts, NOT
read directly here. At runtime, config lives in DB tables:
  - llm_roles(name, system_prompt, provider, model, temperature, max_tokens, enabled)
  - chapter_configs(chapter_id, version, config_json, active)  # mentor_hooks here
  - learner_profiles(user_id, profile_json, updated_at)        # cross-chapter (TODO #11)

Design authority: llm_prompt_design/docs/mentor_design_spec.md S12.
"""
import json
import logging
from typing import Optional

from app.db import get_conn

logger = logging.getLogger(__name__)


def load_role(role_name: str) -> Optional[dict]:
    """Load an agent role (e.g. 'mentor', 'summary', 'psychologist') from llm_roles."""
    with get_conn() as c:
        row = c.execute(
            "SELECT * FROM llm_roles WHERE name = ? AND enabled = 1",
            (role_name,),
        ).fetchone()
    return dict(row) if row else None


def load_chapter_config(chapter_id: str) -> Optional[dict]:
    """Load the active chapter task config. mentor_hooks live here."""
    with get_conn() as c:
        row = c.execute(
            "SELECT config_json FROM chapter_configs "
            "WHERE chapter_id = ? AND active = 1 ORDER BY version DESC LIMIT 1",
            (chapter_id,),
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["config_json"])
    except (json.JSONDecodeError, TypeError):
        logger.error("chapter_config parse failed for %s", chapter_id)
        return None


def load_profile(user_id: str) -> dict:
    """Load the cross-chapter compacted learner profile.

    Returns {} if the table does not exist yet (pre-migration) or is empty --
    callers (assembler) must tolerate an empty profile gracefully.
    """
    try:
        with get_conn() as c:
            row = c.execute(
                "SELECT profile_json FROM learner_profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()
    except Exception as e:  # learner_profiles not created yet (see compaction task #11)
        logger.debug("learner_profiles unavailable: %s", e)
        return {}
    if not row:
        return {}
    try:
        return json.loads(row["profile_json"])
    except (json.JSONDecodeError, TypeError):
        return {}


def save_profile(user_id: str, profile: dict) -> None:
    """Upsert the compacted learner profile (called by the compaction job).

    Requires learner_profiles PK(user_id) -- create the table before invoking
    (see mentor_design_spec.md S9 / compaction task #11).
    """
    with get_conn() as c:
        c.execute(
            """INSERT INTO learner_profiles (user_id, profile_json, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET
                 profile_json = excluded.profile_json,
                 updated_at = excluded.updated_at""",
            (user_id, json.dumps(profile, ensure_ascii=False)),
        )

