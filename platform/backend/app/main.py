"""What Want FastAPI main."""
import logging
import re
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_ORIGIN
from app.db import init_db
from app.routers.book import router as book_router
from app.routers.book_images import router as book_images_router
from app.routers.notes import router as notes_router
from app.routers.roles import router as roles_router
from app.routers.steps import router as steps_router
from app.routers.summary import router as summary_router
from app.routers.chat import router as chat_router
from app.routers.questions import router as questions_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="What Want", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:3011", "http://127.0.0.1:3011"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@book_router.get("/chapters/{chapter_id}/value-examples")
def get_value_examples(chapter_id: str):
    """Return the value examples used by ch04's supplemental keyword drawer."""
    if chapter_id != "ch04":
        return {"chapter_id": chapter_id, "items": []}
    source = Path(__file__).resolve().parents[3] / "chapter_md" / "问题清单.md"
    if not source.exists():
        return {"chapter_id": chapter_id, "items": []}
    text = source.read_text(encoding="utf-8")
    marker = "## 重要的事（价值观）100例清单"
    section = text.split(marker, 1)[1] if marker in text else ""
    section = re.split(r"\n##\s+", section, maxsplit=1)[0]
    items = []
    for line in section.splitlines():
        match = re.match(r"\|\s*\d+\s*\|\s*([^|]+?)\s*\|", line)
        if match:
            items.append(match.group(1).strip())
    return {"chapter_id": chapter_id, "items": items}



# Chapter config shortcut (top-level, not under /steps/{step_id})
@book_router.get("/chapters/{chapter_id}/config")
def get_chapter_full_config(chapter_id: str):
    """获取章节的完整 step 配置（前端用于初始化）。"""
    from app.db import get_conn
    import json
    with get_conn() as conn:
        row = conn.execute(
            "SELECT config_json FROM chapter_configs WHERE chapter_id = ? AND active = 1 ORDER BY version DESC LIMIT 1",
            (chapter_id,),
        ).fetchone()
    if not row:
        return {"chapter_id": chapter_id, "steps": []}
    cfg = json.loads(row["config_json"])
    # Convert new exercises[] format to legacy steps[] for frontend (M5.2 patch).
    if cfg.get("exercises") and not cfg.get("steps"):
        steps = []
        for ex in cfg["exercises"]:
            sid = ex.get("step_id") or ex.get("name", "")
            role_id = ex.get("step_role_id", "")
            output_fields = ex.get("output_fields", []) or []
            schema_type = "structured" if output_fields else "markdown"
            steps.append({
                "step_id": sid,
                "title": ex.get("name", sid),
                "instruction": ex.get("instruction", ""),
                "user_action": ex.get("user_action", ""),
                "worksheet": ex.get("worksheet", ""),
                "output_fields": output_fields,
                "llm_op": {"role_id": role_id, "output_schema": {"type": schema_type, "fields": output_fields}},
                "user_input": {"questions": [{"id": sid + "-q1", "text": ex.get("instruction", "")}]},
                "input_schema": ex.get("input_schema") or cfg.get("input_schema", []),
                "references": ex.get("references", []),
            })
        cfg["steps"] = steps
    return cfg


@book_router.post("/chapters/{chapter_id}/config")
def save_chapter_full_config(chapter_id: str, config: dict):
    """保存章节配置为新版本，并将其设为当前 active 版本。"""
    from app.db import get_conn
    import json

    config_json = config.get("config_json", config)
    if isinstance(config_json, str):
        config_json = json.loads(config_json)
    if not isinstance(config_json, dict):
        raise ValueError("config_json must be an object")

    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM chapter_configs WHERE chapter_id = ?",
            (chapter_id,),
        ).fetchone()
        next_version = int(row["version"] or 0) + 1
        conn.execute(
            "UPDATE chapter_configs SET active = 0 WHERE chapter_id = ?",
            (chapter_id,),
        )
        conn.execute(
            """INSERT INTO chapter_configs (chapter_id, version, config_json, active, created_at)
               VALUES (?, ?, ?, 1, datetime('now'))""",
            (chapter_id, next_version, json.dumps(config_json, ensure_ascii=False)),
        )
    return {"ok": True, "chapter_id": chapter_id, "version": next_version}


app.include_router(book_router)
app.include_router(book_images_router)
app.include_router(notes_router)
app.include_router(roles_router)
app.include_router(steps_router)
app.include_router(summary_router)
app.include_router(chat_router)
app.include_router(questions_router)

@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return {"name": "What Want backend", "status": "ok"}


@app.get("/api/health")
def health():
    return {"ok": True}
