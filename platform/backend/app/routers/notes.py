"""Notes API -- 支持选中文字笔记 + 独立面板笔记两种类型。"""
import json
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.db import get_conn

router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteIn(BaseModel):
    chapter_id: str
    note_type: str  # 'selection' | 'standalone'
    content: str
    source_text: Optional[str] = None
    source_anchor: Optional[str] = None
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    tags: list[str] = []


class NoteUpdate(BaseModel):
    content: Optional[str] = None
    tags: Optional[list[str]] = None


@router.get("")
def list_notes(chapter_id: str, note_type: Optional[str] = None):
    with get_conn() as conn:
        if note_type:
            rows = conn.execute(
                "SELECT * FROM book_notes WHERE chapter_id = ? AND note_type = ? ORDER BY created_at DESC",
                (chapter_id, note_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM book_notes WHERE chapter_id = ? ORDER BY created_at DESC",
                (chapter_id,),
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


@router.post("")
def create_note(body: NoteIn):
    if body.note_type not in ("selection", "standalone"):
        raise HTTPException(400, "note_type must be 'selection' or 'standalone'")

    note_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO book_notes
               (id, chapter_id, note_type, source_text, source_anchor,
                context_before, context_after, content, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (note_id, body.chapter_id, body.note_type,
             body.source_text, body.source_anchor,
             body.context_before, body.context_after,
             body.content, json.dumps(body.tags)),
        )
    return {"id": note_id, "ok": True}


@router.put("/{note_id}")
def update_note(note_id: str, body: NoteUpdate):
    updates = []
    params = []
    if body.content is not None:
        updates.append("content = ?")
        params.append(body.content)
    if body.tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(body.tags))
    if not updates:
        raise HTTPException(400, "Nothing to update")
    updates.append("updated_at = datetime('now')")
    params.append(note_id)

    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE book_notes SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        if cur.rowcount == 0:
            raise HTTPException(404, f"Note {note_id} not found")
    return {"ok": True}


@router.delete("/{note_id}")
def delete_note(note_id: str):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM book_notes WHERE id = ?", (note_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, f"Note {note_id} not found")
    return {"ok": True}


def _row_to_dict(row):
    d = dict(row)
    if "tags" in d and isinstance(d["tags"], str):
        try:
            d["tags"] = json.loads(d["tags"])
        except json.JSONDecodeError:
            d["tags"] = []
    return d
