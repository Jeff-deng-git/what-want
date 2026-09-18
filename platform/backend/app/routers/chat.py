"""Mentor chat -- multi-turn, per-chapter history persisted. Phase C / M3.3.

DB: chapter_chat(id, chapter_id, role, content, created_at)
The mentor is "刘老师" (career-planning mentor), grounded in the chapter's MD.

M3.3 (handoff Q10): chat routes through agent.run_mentor, which loads the
"mentor" llm_role and assembles the prompt via build_mentor_prompt.
Legacy hardcoded path is preserved as _send_message_legacy and gated by
USE_AGENT_CHAT env var (default 1 = new path).
"""
import json
import logging
import os
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_conn
from app.runtime.assembler import ContextIntegrityError
from app.services.llm_client import LLMTimeoutError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chapters/{chapter_id}/chat", tags=["chat"])

HISTORY_LIMIT = 10
USE_AGENT_CHAT = os.getenv("USE_AGENT_CHAT", "1") != "0"


class SendIn(BaseModel):
    content: str
    step_id: str | None = None


def _history(chapter_id: str, limit: int = HISTORY_LIMIT) -> list[dict]:
    with get_conn() as c:
        rows = c.execute(
            """SELECT id, role, content, created_at FROM chapter_chat
               WHERE chapter_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?""",
            (chapter_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def _append(chapter_id: str, role: str, content: str) -> dict:
    msg_id = str(uuid.uuid4())
    with get_conn() as c:
        c.execute(
            """INSERT INTO chapter_chat (id, chapter_id, role, content, created_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (msg_id, chapter_id, role, content),
        )
        row = c.execute(
            "SELECT id, role, content, created_at FROM chapter_chat WHERE id = ?",
            (msg_id,),
        ).fetchone()
    return dict(row)


def _history_to_lines(history: list[dict]) -> list[str]:
    """Convert chat rows to the plain-text history lines build_mentor_prompt expects."""
    out = []
    for m in history:
        who = "\u5218\u8001\u5e08" if m["role"] == "mentor" else "\u7528\u6237"
        out.append(who + "\uff1a" + m["content"])
    return out


@router.get("")
def get_history(chapter_id: str):
    """All messages for this chapter, oldest first."""
    with get_conn() as c:
        rows = c.execute(
            """SELECT id, role, content, created_at FROM chapter_chat
               WHERE chapter_id = ? ORDER BY created_at ASC, rowid ASC""",
            (chapter_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/send")
async def send_message(chapter_id: str, body: SendIn):
    """Send user message, get mentor reply, persist both."""
    content = body.content.strip()
    if not content:
        raise HTTPException(400, "content is empty")
    if USE_AGENT_CHAT:
        return await _send_message_v2(chapter_id, content, body.step_id)
    return await _send_message_legacy(chapter_id, content)


def _load_step_context(chapter_id: str, step_id: str | None):
    if not step_id:
        return None
    with get_conn() as c:
        row = c.execute(
            """SELECT step_id, parsed_output FROM step_runs
               WHERE chapter_id = ? AND step_id = ? AND status = 'submitted' AND stale = 0
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            (chapter_id, step_id),
        ).fetchone()
    if not row or not row["parsed_output"]:
        return None
    try:
        output = json.loads(row["parsed_output"])
    except (json.JSONDecodeError, TypeError):
        return None
    return {"step_id": row["step_id"], "output": output}


def _load_submitted_chapter_context(chapter_id: str, focus_step_id: str | None = None):
    """Load a compact, submitted-only context slice for the chapter mentor."""
    with get_conn() as c:
        rows = c.execute(
            """SELECT step_id, user_answers, parsed_output
               FROM step_runs
               WHERE chapter_id = ? AND status = 'submitted' AND stale = 0
               ORDER BY submitted_at ASC, created_at ASC, rowid ASC""",
            (chapter_id,),
        ).fetchall()

    by_step = {}
    for row in rows:
        try:
            answers = json.loads(row["user_answers"] or "{}")
        except (json.JSONDecodeError, TypeError):
            answers = {}
        try:
            output = json.loads(row["parsed_output"] or "{}")
        except (json.JSONDecodeError, TypeError):
            output = {}
        by_step[row["step_id"]] = {"answers": answers, "output": output}

    selected = []
    for step_id in ("step-1", "step-2", "step-3", "step-4", "step-5"):
        item = by_step.get(step_id)
        if not item:
            continue
        answers = item["answers"] if isinstance(item["answers"], dict) else {}
        output = item["output"] if isinstance(item["output"], dict) else {}
        if chapter_id == "ch05" and step_id == "step-1":
            selected.append({
                "step_id": step_id,
                "answers": {key: answers.get(key, "") for key in ("q1", "q2", "q3", "q4", "q5")},
                "output": {"commentary": output.get("commentary", ""), "talents": output.get("talents", [])},
            })
        elif chapter_id == "ch05" and step_id == "step-2":
            selected.append({
                "step_id": step_id,
                "answers": {"reference_strengths": answers.get("reference_strengths", [])},
                "output": {"talents": output.get("talents", []), "user_manual": output.get("user_manual", "")},
            })
        elif chapter_id == "ch06" and step_id == "step-1":
            selected.append({
                "step_id": step_id,
                "answers": {key: answers.get(key, "") for key in ("q1", "q2", "q3", "q4", "q5")},
                "output": {"commentary": output.get("commentary", ""), "likes": output.get("likes", [])},
            })
        elif chapter_id == "ch06" and step_id == "step-2":
            selected.append({
                "step_id": step_id,
                "answers": {
                    "reference_talents": answers.get("reference_talents", []),
                    "passion_seeds": answers.get("passion_seeds", []),
                },
                "output": {"commentary": output.get("commentary", ""), "likes": output.get("likes", [])},
            })
        elif chapter_id == "ch07" and step_id == "step-1":
            selected.append({
                "step_id": step_id,
                "answers": {},
                "output": {"commentary": output.get("commentary", ""), "ideal_works": output.get("ideal_works", [])},
            })
        elif chapter_id == "ch07" and step_id == "step-2":
            selected.append({
                "step_id": step_id,
                "answers": {},
                "output": {
                    "commentary": output.get("commentary", ""),
                    "ideal_works": output.get("ideal_works", []),
                    "next_action": output.get("next_action", ""),
                },
            })
        elif step_id == "step-1":
            selected.append({
                "step_id": step_id,
                "answers": {key: answers.get(key, "") for key in ("q1", "q2", "q3", "q4", "q5")},
                "output": {"top_values": output.get("top_values", [])},
            })
        elif step_id == "step-2":
            selected.append({
                "step_id": step_id,
                "answers": {"supplemental_keywords": answers.get("supplemental_keywords", [])},
                "output": {"groups": output.get("groups", [])},
            })
        elif step_id == "step-3":
            selected.append({
                "step_id": step_id,
                "output": {"conversions": output.get("conversions", [])},
            })
        elif step_id == "step-4":
            selected.append({
                "step_id": step_id,
                "output": {"ranked": output.get("ranked", [])},
            })
        elif step_id == "step-5":
            selected.append({
                "step_id": step_id,
                "answers": {"experiences": answers.get("experiences", [])},
                "output": {
                    "work_purpose": output.get("work_purpose", ""),
                    "experience_map": output.get("experience_map", []),
                },
            })

    current = next((item for item in selected if item["step_id"] == focus_step_id), None)
    return {
        "chapter_id": chapter_id,
        "submitted_steps": selected,
        "current_step": current,
        "output": current.get("output", {}) if current else {},
    }


async def _send_message_v2(chapter_id: str, content: str, step_id: str | None = None):
    """M3.3 path: route through agent.run_mentor (DB-backed role)."""
    from app.routers.book import get_chapter_md
    from app.runtime.agent import run_mentor
    if get_chapter_md(chapter_id) is None:
        raise HTTPException(404, f"No markdown source for chapter {chapter_id}")
    history = _history(chapter_id)
    history_lines = _history_to_lines(history)
    user_id = os.getenv("DEFAULT_USER_ID", "local")
    step_context = (
        _load_submitted_chapter_context(chapter_id, step_id)
        if chapter_id in {"ch04", "ch05", "ch06", "ch07"}
        else _load_step_context(chapter_id, step_id)
    )
    try:
        reply = await run_mentor(
            chapter_id=chapter_id,
            user_id=user_id,
            user_msg=content,
            history=history_lines,
            step_context=step_context,
        )
    except ContextIntegrityError as e:
        logger.warning("mentor context incomplete for %s: %s", chapter_id, e)
        raise HTTPException(409, "Mentor context incomplete: " + str(e))
    except LLMTimeoutError as e:
        logger.error("agent.run_mentor timed out for %s: %s", chapter_id, e)
        raise HTTPException(504, "mentor unavailable: " + str(e))
    except RuntimeError as e:
        logger.exception("agent.run_mentor failed for %s", chapter_id)
        raise HTTPException(500, "mentor unavailable: " + str(e))
    reply = (reply or "").strip()
    if not reply:
        raise HTTPException(500, "mentor returned empty reply")
    # Persist atomically after LLM success.
    user_id_msg = str(uuid.uuid4())
    mentor_id = str(uuid.uuid4())
    with get_conn() as c:
        c.execute(
            """INSERT INTO chapter_chat (id, chapter_id, role, content, created_at)
               VALUES (?, ?, 'user', ?, datetime('now'))""",
            (user_id_msg, chapter_id, content),
        )
        c.execute(
            """INSERT INTO chapter_chat (id, chapter_id, role, content, created_at)
               VALUES (?, ?, 'mentor', ?, datetime('now'))""",
            (mentor_id, chapter_id, reply),
        )
        user_msg = dict(c.execute(
            "SELECT id, role, content, created_at FROM chapter_chat WHERE id = ?",
            (user_id_msg,),
        ).fetchone())
        mentor_msg = dict(c.execute(
            "SELECT id, role, content, created_at FROM chapter_chat WHERE id = ?",
            (mentor_id,),
        ).fetchone())
    return {"user": user_msg, "mentor": mentor_msg}


async def _send_message_legacy(chapter_id: str, content: str):
    """Pre-M3.3 path: hardcoded "刘老师" system + direct deepseek call.

    Preserved as rollback per handoff Q10. Disable by setting USE_AGENT_CHAT=0.
    """
    from app.routers.book import get_chapter_md
    from app.services.llm_client import call_llm

    md = get_chapter_md(chapter_id)
    if md is None:
        raise HTTPException(404, f"No markdown source for chapter {chapter_id}")
    system = (
        "\u4f60\u662f\u201c\u5218\u8001\u5e08\u201d\uff0c\u4e00\u4f4d\u8d44\u6df1\u7684\u804c\u4e1a\u89c4\u5212\u5bfc\u5e08\uff0c"
        "\u6b63\u5728\u548c\u7528\u6237\u5171\u8bfb\u300a\u5982\u4f55\u627e\u5230\u60f3\u505a\u7684\u4e8b\u300b\u7684\u672c\u7ae0\u5185\u5bb9\u3002\n"
        "\u89c4\u5219\uff1a\n"
        "- \u53ea\u57fa\u4e8e\u672c\u7ae0\u5185\u5bb9\u5c55\u5f00\uff0c\u4e0d\u7f16\u9020\u672c\u7ae0\u6ca1\u6709\u7684\u89c2\u70b9\n"
        "- \u987a\u7740\u7528\u6237\u8bf4\u7684\u8bdd\u6df1\u5165\uff0c\u7528\u63d0\u95ee\u5f15\u5bfc\u7528\u6237\u81ea\u5df1\u601d\u8003\uff0c\u4e0d\u8981\u76f4\u63a5\u7ed9\u7ed3\u8bba\n"
        "- \u4e00\u6b21\u53ea\u805a\u7126\u4e00\u4e2a\u70b9\uff0c\u9010\u6e10\u6df1\u5165\u4e00\u6b65\u4e00\u6b65\u6316\n"
        "- \u5f15\u7528\u7528\u6237\u7684\u539f\u8bdd\uff0c\u6307\u51fa\u5176\u4e2d\u8574\u542b\u7684\u4ef7\u503c\u89c2\u6216\u601d\u7ef4\u7ebf\u7d22\n"
        "- \u56de\u590d\u63a7\u5236\u5728 150 \u5b57\u4ee5\u5185\n\n"
        "\u672c\u7ae0\u5185\u5bb9\uff08\u4ec5\u4f5c\u80cc\u666f\u53c2\u8003\uff09\uff1a\n"
        + md[:12000]
    )
    history_lines = []
    for m in _history(chapter_id):
        who = "\u5218\u8001\u5e08" if m["role"] == "mentor" else "\u7528\u6237"
        history_lines.append(who + "\uff1a" + m["content"])
    history_text = "\n".join(history_lines)
    user_prompt = (
        "\u4ee5\u4e0b\u662f\u6700\u8fd1\u5bf9\u8bdd\uff1a\n" + history_text + "\n\n"
        "\u7528\u6237\u6700\u65b0\u8bf4\uff1a" + content + "\n\n"
        "\u8bf7\u4ee5\u5218\u8001\u5e08\u7684\u8eab\u4efd\u56de\u590d\u3002"
    )
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "DEEPSEEK_API_KEY not set")
    reply = await call_llm(
        provider="deepseek",
        model="deepseek-v4-flash",
        api_key=api_key,
        system=system,
        user=user_prompt,
        temperature=0.7,
        max_tokens=600,
        json_mode=False,
    )
    user_id = str(uuid.uuid4())
    mentor_id = str(uuid.uuid4())
    with get_conn() as c:
        c.execute(
            """INSERT INTO chapter_chat (id, chapter_id, role, content, created_at)
               VALUES (?, ?, 'user', ?, datetime('now'))""",
            (user_id, chapter_id, content),
        )
        c.execute(
            """INSERT INTO chapter_chat (id, chapter_id, role, content, created_at)
               VALUES (?, ?, 'mentor', ?, datetime('now'))""",
            (mentor_id, chapter_id, reply.strip()),
        )
        user_msg = dict(c.execute(
            "SELECT id, role, content, created_at FROM chapter_chat WHERE id = ?",
            (user_id,),
        ).fetchone())
        mentor_msg = dict(c.execute(
            "SELECT id, role, content, created_at FROM chapter_chat WHERE id = ?",
            (mentor_id,),
        ).fetchone())
    return {"user": user_msg, "mentor": mentor_msg}


@router.delete("")
def clear_history(chapter_id: str):
    """Clear this chapter's chat history."""
    with get_conn() as c:
        c.execute("DELETE FROM chapter_chat WHERE chapter_id = ?", (chapter_id,))
    return {"ok": True, "chapter_id": chapter_id}
