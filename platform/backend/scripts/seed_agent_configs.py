"""Seed agent_configs (ADR-001) with mentor / summary scaffolds.

The agent_configs table (db.py schema) is the storage for global role scaffolds
per ADR-001. This script loads scaffold JSON files from
  llm_prompt_design/config/<role>/<role>_config.json
and UPSERTs each into agent_configs (PK: name).

Per design-side ref — 2 (agent_configs decision landed):
  - llm_roles   → provider/model + short identity system_prompt
  - agent_configs → full scaffold (persona, rules, examples, hooks, budget)

Run once after backend restart:
    cd platform/backend
    python scripts/seed_agent_configs.py

Idempotent: re-running overwrites the same name config_json.
"""
import json
import os
import sys

PROJECT_ROOT = r"D:\AI_Project\What_Want"
LLM_CONFIG_ROOT = os.path.join(PROJECT_ROOT, "llm_prompt_design", "config")

AGENT_CONFIG_FILES = [
    ("mentor", os.path.join(LLM_CONFIG_ROOT, "mentor", "mentor_config.json")),
    ("summary", os.path.join(LLM_CONFIG_ROOT, "agents", "summary_config.json")),
]


def main():
    sys.path.insert(0, PROJECT_ROOT)
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "platform", "backend"))
    from app.db import init_db, get_conn  # noqa: E402

    init_db()
    with get_conn() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(agent_configs)").fetchall()]
        if not cols:
            print("ERROR: agent_configs table missing. Run app.db.init_db() to create it.")
            sys.exit(2)
        if "name" not in cols or "config_json" not in cols:
            print("ERROR: agent_configs schema unexpected. Got columns: " + str(cols))
            sys.exit(2)

        for name, path in AGENT_CONFIG_FILES:
            if not os.path.exists(path):
                print("SKIP  " + name + " (file missing: " + path + ")")
                continue
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            payload = json.dumps(cfg, ensure_ascii=False)
            existing = conn.execute(
                "SELECT name FROM agent_configs WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE agent_configs SET config_json = ?, updated_at = datetime('now') WHERE name = ?",
                    (payload, name),
                )
                print("updated:", name, "(" + str(len(payload)) + " bytes)")
                continue
            conn.execute(
                "INSERT INTO agent_configs (name, config_json, updated_at) VALUES (?, ?, datetime('now'))",
                (name, payload),
            )
            print("seeded:", name, "(" + str(len(payload)) + " bytes)")


if __name__ == "__main__":
    main()
