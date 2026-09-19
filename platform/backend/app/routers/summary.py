"""AI chapter summary -- generate, cache, regenerate. Phase C / M3.3.

DB: chapter_summaries(chapter_id PK, summary_json, updated_at)
Source of truth for content: chapter_md/{stem}.md (no base64 images).

M3.3 (handoff Q10): regenerate routes through agent.run_summary, which loads
the "summary" llm_role and uses build_summary_prompt. The hardcoded SUMMARY_SYSTEM
constant is preserved inside _regenerate_legacy and gated by USE_AGENT_SUMMARY
env var (default 1 = new path).
"""
import json
import logging
import os

from fastapi import APIRouter, HTTPException

from app.db import get_conn

logger = logging.getLogger(__name__)

# NOTE: 不使用带路径参数的 prefix + 空相对路径路由的组合（FastAPI/Starlette 在运行时
# 会让同级字面量子路由如 /regenerate 错误地 404）。改为每条路由写全路径，URL 契约不变。
router = APIRouter(tags=["summary"])

USE_AGENT_SUMMARY = os.getenv("USE_AGENT_SUMMARY", "1") != "0"
SUMMARY_MD_CAP = 12000


def _read_cached(chapter_id: str) -> dict | None:
    with get_conn() as c:
        row = c.execute(
            "SELECT summary_json, updated_at FROM chapter_summaries WHERE chapter_id = ?",
            (chapter_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "chapter_id": chapter_id,
        "summary": json.loads(row["summary_json"]),
        "updated_at": row["updated_at"],
    }


def _upsert(chapter_id: str, parsed: dict):
    with get_conn() as c:
        c.execute(
            """INSERT INTO chapter_summaries (chapter_id, summary_json, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(chapter_id) DO UPDATE SET
                 summary_json = excluded.summary_json,
                 updated_at = excluded.updated_at""",
            (chapter_id, json.dumps(parsed, ensure_ascii=False)),
        )


@router.get("/api/chapters/{chapter_id}/summary")
def get_summary(chapter_id: str):
    """Return cached summary, or {summary: null} if not generated yet."""
    cached = _read_cached(chapter_id)
    if cached:
        return cached
    return {"chapter_id": chapter_id, "summary": None, "updated_at": None}


@router.post("/api/chapters/{chapter_id}/summary/regenerate")
async def regenerate_summary(chapter_id: str):
    """Force LLM to (re)generate the chapter summary, overwrite cache."""
    if USE_AGENT_SUMMARY:
        return await _regenerate_v2(chapter_id)
    return await _regenerate_legacy(chapter_id)


async def _regenerate_v2(chapter_id: str):
    """M3.3 path: route through agent.run_summary (DB-backed role)."""
    from app.routers.book import get_chapter_md
    from app.runtime.agent import run_summary

    md = get_chapter_md(chapter_id)
    if md is None:
        raise HTTPException(404, f"No markdown source for chapter {chapter_id}")
    user_id = os.getenv("DEFAULT_USER_ID", "local")
    try:
        parsed = await run_summary(
            chapter_id=chapter_id,
            chapter_md=md,
            user_id=user_id,
        )
    except RuntimeError as e:
        logger.exception("agent.run_summary failed for %s", chapter_id)
        raise HTTPException(500, "summary unavailable: " + str(e))
    except json.JSONDecodeError as e:
        logger.error("summary parse failed for %s: %s", chapter_id, str(e))
        raise HTTPException(500, f"Summary parse failed: {e}")
    _upsert(chapter_id, parsed)
    return _read_cached(chapter_id)


async def _regenerate_legacy(chapter_id: str):
    """Pre-M3.3 path: hardcoded SUMMARY_SYSTEM + direct deepseek call.

    Preserved as rollback per handoff Q10. Disable with USE_AGENT_SUMMARY=0.
    """
    from app.routers.book import get_chapter_md
    from app.services.llm_client import call_llm

    md = get_chapter_md(chapter_id)
    if md is None:
        raise HTTPException(404, f"No markdown source for chapter {chapter_id}")
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "DEEPSEEK_API_KEY not set")
    SUMMARY_SYSTEM = (
        "\u4f60\u662f\u4e00\u4f4d\u8d44\u6df1\u56fe\u4e66\u7f16\u8f91\uff0c\u64c5\u957f\u7528\u7b80\u6d01\u7ed3\u6784\u5316\u65b9\u5f0f\u6982\u62ec\u4e00\u672c\u4e66\u7684\u7ae0\u8282\u3002\n"
        "\u8bf7\u57fa\u4e8e\u7ed9\u5b9a\u7684\u7ae0\u8282\u5168\u6587\uff0c\u8f93\u51fa\u4e25\u683c\u7684 JSON\uff0c\u4e0d\u8981\u6709\u4efb\u4f55\u989d\u5916\u6587\u5b57\uff1a\n"
        '{\u0022summary\u0022: \u0022350\u5b57\u4ee5\u5185\u7684\u5b8c\u6574\u6458\u8981\u0022, '
        '\u0022core_concepts\u0022: [{\u0022name\u0022: \u0022\u6982\u5ff5\u540d(<=8\u5b57)\u0022, '
        '\u0022explanation\u0022: \u0022<=80\u5b57\u89e3\u91ca\u0022}], '
        '\u0022key_process\u0022: [\u00223-6\u4e2a\u5173\u952e\u6d41\u7a0b/\u6b65\u9aa4\uff0c\u6bcf\u6b65\u4e0d\u8d85\u8fc715\u5b57\u0022]}\n'
        "\u8981\u6c42\uff1a\n"
        "1. summary 350\u5b57\u4ee5\u5185\uff0c\u8986\u76d6\u7ae0\u8282\u4e3b\u65e8\uff1b\n"
        "2. core_concepts \u7ed9\u51fa 3-5 \u4e2a\uff0c\u6bcf\u4e2a name <=8\u5b57\u3001explanation <=80\u5b57\uff1b\n"
        "   \u89e3\u91ca\u4f18\u5148\u63d0\u70bc\u7ae0\u8282\u539f\u6587\uff0c\u82e5\u539f\u6587\u4e00\u53e5\u8bdd\u8bb2\u5f97\u6e05\u5c31\u76f4\u63a5\u5f15\u7528\uff08<=30\u5b57\u5185\uff09\uff0c\n"
        "   \u539f\u6587\u6709\u591a\u5904\u6216\u8f83\u957f\u5219\u63d0\u70bc\u8981\u70b9\uff1b\n"
        "3. key_process \u662f\u7ae0\u8282\u7ed9\u51fa\u7684\u53ef\u6267\u884c\u6b65\u9aa4\uff08\u82e5\u7ae0\u8282\u65e0\u6d41\u7a0b\u6027\u5185\u5bb9\uff0c\u7ed9\u7a7a\u6570\u7ec4\uff09\u3002"
    )
    raw = await call_llm(
        provider="deepseek",
        model="deepseek-flash",
        api_key=api_key,
        system=SUMMARY_SYSTEM,
        user=md[:SUMMARY_MD_CAP],
        json_mode=True,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("summary parse failed for %s: %s", chapter_id, raw[:200])
        raise HTTPException(500, f"Summary parse failed: {e}")
    _upsert(chapter_id, parsed)
    return _read_cached(chapter_id)