"""Parse 问题清单.md into the `questions` table. Phase C.

Usage: python3 seed_questions.py
Idempotent: clears the `questions` table, then re-inserts.

Source format (chapter_md/问题清单.md):
  ## 问题清单
  30个问题，找到自己重要的事（价值观）     <- section header + category
  N. 主问题                                <- question (OCR-mangled numbers)
  子问句...
  ...
  30个问题，找到自己擅长的事（才能）       <- next category
  ...
  30个问题，找到自己喜欢的事（热情）

We track a running category from "N个问题，找到自己X的事" lines. Question numbers
are OCR-mangled, so q_order is a sequential counter, not the OCR digit.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")

from app.db import get_conn, init_db

QUESTIONS_MD = Path(__file__).parent.parent.parent / "chapter_md" / "问题清单.md"

# A question start: line begins with optional digits then a dot then space
QUESTION_START = re.compile(r"^\d*\.\s*\S")
# Section/category header: "N个问题，找到自己重要的事（价值观）"
CATEGORY_HEADER = re.compile(r"个问题，找到自己(.+?)的事")
# Skip: headings, images, decorative
SKIP = re.compile(r"^#{1,3} |^!|^>|^[-=*_]{3,}$")


def _category_for(line: str) -> str | None:
    m = CATEGORY_HEADER.search(line)
    if not m:
        return None
    return {"重要": "价值观", "擅长": "才能", "喜欢": "热情"}.get(m.group(1), m.group(1))


def parse_questions(text: str) -> list[dict]:
    questions = []
    current = None
    category = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # markdown table rows (3×100 例清单) — filter out, they are not sub-questions
        if line.startswith("|"):
            # a table row after a question means the question bank ended; close current
            if current:
                questions.append(current)
                current = None
            continue
        # section header also carries category
        cat = _category_for(line)
        if cat:
            # close the previous category's open question before switching
            if current:
                questions.append(current)
                current = None
            category = cat
            continue
        if SKIP.match(line):
            continue
        if QUESTION_START.match(line):
            main = re.sub(r"^\d*\.\s*", "", line).strip()
            if current:
                questions.append(current)
            current = {"q_order": len(questions) + 1, "question": main,
                       "sub_questions": [], "category": category}
        else:
            if current is not None:
                current["sub_questions"].append(line)

    if current:
        questions.append(current)
    return questions


def seed():
    init_db()
    if not QUESTIONS_MD.exists():
        print(f"ERROR: {QUESTIONS_MD} not found")
        sys.exit(1)
    text = QUESTIONS_MD.read_text(encoding="utf-8")
    questions = parse_questions(text)

    with get_conn() as c:
        c.execute("DELETE FROM questions")
        for q in questions:
            c.execute(
                """INSERT INTO questions (q_order, question, sub_questions, category, created_at)
                   VALUES (?, ?, ?, ?, datetime('now'))""",
                (q["q_order"], q["question"],
                 json.dumps(q["sub_questions"], ensure_ascii=False), q["category"]),
            )

    print(f"Imported {len(questions)} questions")
    from collections import Counter
    by_cat = Counter(q["category"] for q in questions)
    for c, n in by_cat.items():
        print(f"  {c}: {n} 题")


if __name__ == "__main__":
    seed()
