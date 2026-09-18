"""Question bank -- browse + answer (answers stored in book_notes). Phase C."""
import json
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_conn

router = APIRouter(prefix="/api/questions", tags=["questions"])


class AnswerIn(BaseModel):
    answer: str


def _row_to_dict(row):
    d = dict(row)
    if isinstance(d.get("sub_questions"), str):
        try:
            d["sub_questions"] = json.loads(d["sub_questions"])
        except json.JSONDecodeError:
            d["sub_questions"] = []
    return d


@router.get("")
def list_questions(category: str | None = None):
    """All questions, optionally filtered by category (价值观/才能/热情)."""
    with get_conn() as c:
        if category:
            rows = c.execute(
                "SELECT * FROM questions WHERE category = ? ORDER BY q_order",
                (category,),
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM questions ORDER BY category, q_order").fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/{q_order}")
def get_question(q_order: int):
    with get_conn() as c:
        row = c.execute(
            "SELECT * FROM questions WHERE q_order = ?", (q_order,)
        ).fetchone()
    if not row:
        raise HTTPException(404, f"Question {q_order} not found")
    return _row_to_dict(row)


@router.get("/{q_order}/answer")
def get_answer(q_order: int):
    """Return any saved answer for this question (stored in book_notes)."""
    with get_conn() as c:
        rows = c.execute(
            """SELECT content, updated_at FROM book_notes
               WHERE chapter_id = 'questions' AND note_type = 'standalone'
                 AND source_anchor = ? ORDER BY updated_at DESC LIMIT 1""",
            (str(q_order),),
        ).fetchall()
    if not rows:
        return {"q_order": q_order, "answer": None}
    return {"q_order": q_order, "answer": rows[0]["content"], "updated_at": rows[0]["updated_at"]}


@router.post("/{q_order}/answer")
def save_answer(q_order: int, body: AnswerIn):
    """Upsert the user's answer for a question.

    PONYTAIL: answers live in book_notes (chapter_id='questions', source_anchor=order),
    reusing the existing notes table instead of a new one.
    """
    with get_conn() as c:
        q = c.execute("SELECT question FROM questions WHERE q_order = ?", (q_order,)).fetchone()
        if not q:
            raise HTTPException(404, f"Question {q_order} not found")
        existing = c.execute(
            """SELECT id FROM book_notes
               WHERE chapter_id = 'questions' AND note_type = 'standalone'
                 AND source_anchor = ?""",
            (str(q_order),),
        ).fetchone()
        if existing:
            c.execute(
                """UPDATE book_notes SET content = ?, tags = ?, updated_at = datetime('now')
                   WHERE id = ?""",
                (body.answer, json.dumps(["qa"]), existing["id"]),
            )
            return {"ok": True, "q_order": q_order, "updated": True}
        else:
            note_id = str(uuid.uuid4())
            c.execute(
                """INSERT INTO book_notes
                   (id, chapter_id, note_type, source_text, source_anchor,
                    content, tags, created_at, updated_at)
                   VALUES (?, 'questions', 'standalone', ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (note_id, q["question"], str(q_order), body.answer, json.dumps(["qa"])),
            )
            return {"ok": True, "q_order": q_order, "updated": False}
