"""Seed llm_roles with the two roles used by chapter_config step_role_id.

Per handoff S2 (decision Q3): career_counselor + psychologist are the two
per-step roles. mentor/summary are separate (see seed_agent_configs).
Chapters use these names verbatim in exercises[].step_role_id.

Idempotent: skips rows whose name already exists.
"""
import sys
import uuid

sys.path.insert(0, r"D:\AI_Project\What_Want\platformackend")
from app.db import get_conn

ROLES = [
    {
        "name": "psychologist",
        "description": "Self-reflection coach. Reads user answers, surfaces contradictions, mirrors back. Used for inventory / reflection steps (ch02, ch03, ch04 step1-3, ch06).",
        "system_prompt": "You are a reflective self-cognition coach. Help users see their own answers without judgment. Use Socratic questions. Reference the book background (What Want by Yagi Jinpei). Respond in Chinese when the user writes Chinese.",
        "temperature": 0.5,
        "max_tokens": 1500,
    },
    {
        "name": "career_counselor",
        "description": "Career counselor. Synthesizes user answers into actionable career moves. Used for synthesis / decision steps (ch01, ch04 step4-5, ch05, ch07, ch08).",
        "system_prompt": "You are a career counselor grounded in the What Want (Yagi Jinpei) methodology. Help users synthesize values + talents + likes into concrete next steps. Be concise. Respond in Chinese when the user writes Chinese.",
        "temperature": 0.5,
        "max_tokens": 1500,
    },
]


def main():
    provider = "deepseek"
    model = "deepseek-chat"
    with get_conn() as conn:
        for role in ROLES:
            existing = conn.execute(
                "SELECT id FROM llm_roles WHERE name = ?", (role["name"],)
            ).fetchone()
            if existing:
                print("skip:", role["name"])
                continue
            conn.execute(
                """INSERT INTO llm_roles
                   (id, name, description, system_prompt, provider, model,
                    temperature, max_tokens, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (str(uuid.uuid4()), role["name"], role["description"],
                 role["system_prompt"], provider, model,
                 role["temperature"], role["max_tokens"]),
            )
            print("seeded:", role["name"])


if __name__ == "__main__":
    main()
