"""One-shot seed: load all 8 chapter_configs from JSON into chapter_configs table.

Run once after backend restart:
    python seed_all_chapters.py
"""
import json
import os
import sys
from pathlib import Path

# Resolve relative to this file: <repo>/platform/backend/seed_all_chapters.py
#   parents[0]=backend  parents[1]=platform  parents[2]=<repo root>
# Override with WW_CHAPTERS_ROOT if your chapter configs live elsewhere.
CHAPTERS_ROOT = os.getenv(
    'WW_CHAPTERS_ROOT',
    str(Path(__file__).resolve().parents[2] / 'llm_prompt_design' / 'config' / 'chapters'),
)
CHAPTERS = ['ch01', 'ch02', 'ch03', 'ch04', 'ch05', 'ch06', 'ch07', 'ch08']


def main():
    from app.db import init_db, get_conn
    init_db()
    with get_conn() as conn:
        for ch in CHAPTERS:
            path = os.path.join(CHAPTERS_ROOT, 'chapter_config_' + ch + '.json')
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            existing = conn.execute(
                'SELECT chapter_id, version FROM chapter_configs WHERE chapter_id = ? AND active = 1',
                (ch,),
            ).fetchone()
            if existing:
                print(ch + ' already seeded, skipping')
                continue
            conn.execute(
                'INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at) VALUES (?, ?, ?, 1, datetime(' + chr(0x27) + 'now' + chr(0x27) + '))',
                (ch, 1, json.dumps(cfg, ensure_ascii=False)),
            )
            print(ch + ' seeded (' + str(len(cfg.get('exercises') or [])) + ' exercises)')


if __name__ == '__main__':
    main()
