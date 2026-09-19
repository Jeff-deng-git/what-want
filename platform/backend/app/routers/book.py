"""M1: Book chapter API -- list chapters, get content, serve images, track reading state.

Phase A: chapters are discovered by scanning chapter_html/*.html + chapter_md/*.md
filename prefixes ("第一章-...", "序-序言", "问题清单"). The legacy styled HTML
under backend/book/chapters_md_styled/ remains as fallback for the original
ch4 demo if no matching chapter_html entry exists.
"""
import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from fastapi import APIRouter, HTTPException, Response

from app.config import BOOK_MD_DIR, CHAPTER_HTML_DIR, CHAPTER_MD_DIR_NEW
from app.db import get_conn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/book", tags=["book"])


# -------- Chapter discovery --------

# Filename -> (id, title, sort_key)
# Rules:
#   "序-序言.{html,md}"               -> ("preface",    "序言",                    0)
#   "第N章-标题.{html,md}"           -> (f"ch{N}",      f"第N章 标题",              N)
#   "问题清单.{html,md}"             -> ("questions",  "问题清单",                99)



def _strip_chapter_filename(stem: str) -> dict | None:
    """Parse a chapter filename stem -> {id, title, sort_key}.

    Accepts the cleaned names from chapter_html/ + chapter_md/ as well as the
    un-prefixed short names ("第一章-..."). Tolerates extra spaces and the
    original '如何找到想做的事_(八木仁平)_(...).cleaned -Final-' prefix.
    """
    # Strip the original PDF+mineru prefix if present
    s = re.sub(r"^如何找到想做的事_\(八木仁平\)_\(.*?\)_cleaned[ -]Final-?", "", stem).strip()
    # If still looks like the prefix, keep going (multiple variants)
    s = re.sub(r"^[-_]+", "", s)
    if not s:
        return None

    # preface
    if s.startswith("序-") or s == "序言":
        return {"id": "preface", "title": "序言", "sort_key": 0}

    # numbered chapters: "第N章-..."
    m = re.match(r"^第([一二三四五六七八九十百千]+|\d+)章[---\s]*(.*)$", s)
    if m:
        cn = m.group(1)
        rest = m.group(2).strip()
        num = _cn_num(cn)
        if num is None:
            return None
        # Restore quotes that were substituted to '_' during filename cleanup
        rest = rest.replace("_", "")
        title = f"第{cn}章 {rest}".strip() if rest else f"第{cn}章"
        return {"id": f"ch{num:02d}", "title": title, "sort_key": num}

    # question bank
    if s == "问题清单":
        return {"id": "questions", "title": "问题清单", "sort_key": 99}

    return None


def _cn_num(s: str) -> int | None:
    """Convert Chinese number (一-十百千) or Arabic to int. Limited to 1-99."""
    digits = {"零":0, "一":1, "二":2, "三":3, "四":4, "五":5, "六":6, "七":7, "八":8, "九":9}
    if s.isdigit():
        return int(s)
    if len(s) == 1:
        return digits.get(s)
    if len(s) == 2 and s[0] == "十":
        return 10 + digits.get(s[1], 0)
    return None


def _resolve_dir(env_value: str) -> Path:
    """Resolve CHAPTER_HTML_DIR / CHAPTER_MD_DIR_NEW against platform/ root by default.

    Relative paths walk up from backend/ to platform/; absolute paths are used as-is.
    book.py lives at platform/backend/app/routers/book.py, so 4 parent steps reach platform/.
    """
    p = Path(env_value)
    if p.is_absolute():
        return p
    return (Path(__file__).parent.parent.parent.parent / p).resolve()


# Canonical book framework -- the COMPLETE logical split every source book must
# follow. A clone user splits their book into exactly these files (see README
# "准备书籍原文"); the app scans chapter_md/ + chapter_html/ for the
# `source_filename` stem of each. Listed here so the framework is always visible
# even before any book text is placed (has_md/has_html are overlaid from disk).
_CANONICAL_FRAMEWORK: list[dict] = [
    {"id": "preface",  "title": "序言",   "sort_key": 0,  "source_filename": "序-序言"},
    {"id": "ch01",     "title": "第1章",  "sort_key": 1,  "source_filename": "第1章"},
    {"id": "ch02",     "title": "第2章",  "sort_key": 2,  "source_filename": "第2章"},
    {"id": "ch03",     "title": "第3章",  "sort_key": 3,  "source_filename": "第3章"},
    {"id": "ch04",     "title": "第4章",  "sort_key": 4,  "source_filename": "第4章"},
    {"id": "ch05",     "title": "第5章",  "sort_key": 5,  "source_filename": "第5章"},
    {"id": "ch06",     "title": "第6章",  "sort_key": 6,  "source_filename": "第6章"},
    {"id": "ch07",     "title": "第7章",  "sort_key": 7,  "source_filename": "第7章"},
    {"id": "ch08",     "title": "第8章",  "sort_key": 8,  "source_filename": "第8章"},
    {"id": "questions","title": "问题清单", "sort_key": 99, "source_filename": "问题清单"},
]


def _config_chapter_titles() -> dict[str, str]:
    """chapter_id -> chapter_title from active chapter_configs (DB)."""
    titles: dict[str, str] = {}
    with get_conn() as c:
        rows = c.execute(
            "SELECT chapter_id, config_json FROM chapter_configs WHERE active = 1"
        ).fetchall()
    for row in rows:
        try:
            cfg = json.loads(row["config_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        t = cfg.get("chapter_title")
        if t:
            titles[row["chapter_id"]] = t
    return titles


@lru_cache(maxsize=1)
def _scan_chapters() -> list[dict]:
    """Walk chapter_html + chapter_md dirs and produce the chapter list.

    Cached for the process lifetime; restart the server to re-scan after adding
    new files. Each chapter dict:
      {id, title, has_html, has_md, sort_key}

    Dedup is by chapter id (not by filename stem) because the two directories
    use slightly different naming conventions for the same logical chapter
    (e.g. HTML uses literal punctuation, MD uses underscores; the preface
    HTML appends "封面_版权_赞誉_序" while MD doesn't).
    """
    html_dir = _resolve_dir(CHAPTER_HTML_DIR)
    md_dir = _resolve_dir(CHAPTER_MD_DIR_NEW)
    by_id: dict[str, dict] = {}

    def _absorb(path: Path, kind: str):
        meta = _strip_chapter_filename(path.stem)
        if not meta:
            return
        entry = by_id.setdefault(meta["id"], {**meta, "has_html": False, "has_md": False})
        entry[kind] = True
        entry["sort_key"] = meta["sort_key"]

    if html_dir.exists():
        for f in sorted(html_dir.glob("*.html")):
            _absorb(f, "has_html")
    if md_dir.exists():
        for f in sorted(md_dir.glob("*.md")):
            _absorb(f, "has_md")

    chapters = list(by_id.values())
    chapters.sort(key=lambda c: c["sort_key"])
    return chapters




# -------- API endpoints --------

def _chapter_progress(chapter_id: str) -> dict:
    """{progress_pct, last_read_at, submitted_steps, total_steps} for a chapter.

    - If chapter has a step workflow (chapter_configs): progress = submitted/total.
    - Else: progress = None (frontend shows read/unread via scroll).
    """
    with get_conn() as c:
        cfg = c.execute(
            """SELECT config_json FROM chapter_configs
               WHERE chapter_id = ? AND active = 1 ORDER BY version DESC LIMIT 1""",
            (chapter_id,),
        ).fetchone()
        state = c.execute(
            "SELECT scroll_position, updated_at FROM reading_state WHERE chapter_id = ?",
            (chapter_id,),
        ).fetchone()
        submitted = total = None
        if cfg:
            try:
                config_json = json.loads(cfg["config_json"])
                steps = config_json.get("exercises") or config_json.get("steps", [])
                total = len(steps)
                if total:
                    submitted_rows = c.execute(
                        "SELECT DISTINCT step_id FROM step_runs "
                        "WHERE chapter_id = ? AND status = 'submitted' AND stale = 0",
                        (chapter_id,),
                    ).fetchall()
                    submitted_steps = {row["step_id"] for row in submitted_rows}
                    if chapter_id == "ch06":
                        profile_row = c.execute(
                            "SELECT profile_json FROM learner_profiles WHERE user_id = ?",
                            (os.getenv("DEFAULT_USER_ID", "local"),),
                        ).fetchone()
                        profile = {}
                        if profile_row:
                            try:
                                profile = json.loads(profile_row["profile_json"] or "{}")
                            except (json.JSONDecodeError, TypeError):
                                profile = {}
                        if not isinstance(profile.get("likes"), list) or not profile["likes"]:
                            submitted_steps.discard("step-2")
                    submitted = len(submitted_steps)
            except Exception as e:
                logger.warning("_chapter_progress: failed to parse config for chapter %s: %s", chapter_id, e)
                pass
    return {
        "progress_pct": round(submitted / total * 100) if total else None,
        "last_read_at": state["updated_at"] if state else None,
        "scroll_position": state["scroll_position"] if state else None,
        "submitted_steps": submitted,
        "total_steps": total,
    }


@router.get("/chapters")
def list_chapters():
    """Return the COMPLETE book framework (序 + 第1-8章 + 问题清单).

    The framework itself is always listed (from _CANONICAL_FRAMEWORK) so a clone
    user sees the full structure before placing any book text. has_md/has_html
    reflect what is actually present on disk; has_steps reflects whether the
    chapter has an active step workflow (chapter_configs). Chapter titles are
    taken from chapter_configs when available, else the canonical default.
    Chapter ids use the unified ch01..ch08 format (handoff v2.0 决策 4).
    """
    scanned = {c["id"]: c for c in _scan_chapters()}
    config_titles = _config_chapter_titles()
    config_ids = _chapters_with_configs()
    out = []
    for fw in _CANONICAL_FRAMEWORK:
        cid = fw["id"]
        sc = scanned.get(cid, {"has_html": False, "has_md": False})
        out.append({
            "id": cid,
            "title": config_titles.get(cid) or fw["title"],
            "has_html": bool(sc.get("has_html", False)),
            "has_md": bool(sc.get("has_md", False)),
            "has_steps": cid in config_ids,
            "sort_key": fw["sort_key"],
            **_chapter_progress(cid),
        })
    # defensive: include any scanned chapter not in the canonical framework
    framework_ids = {fw["id"] for fw in _CANONICAL_FRAMEWORK}
    for cid, sc in scanned.items():
        if cid not in framework_ids:
            out.append({
                "id": cid,
                "title": sc.get("title", cid),
                "has_html": bool(sc.get("has_html", False)),
                "has_md": bool(sc.get("has_md", False)),
                "has_steps": cid in config_ids,
                "sort_key": sc.get("sort_key", 50),
                **_chapter_progress(cid),
            })
    out.sort(key=lambda c: c["sort_key"])
    return out


def _chapters_with_configs() -> set[str]:
    """Set of chapter ids that have an active chapter_config (step workflow)."""
    with get_conn() as c:
        rows = c.execute(
            "SELECT DISTINCT chapter_id, config_json FROM chapter_configs WHERE active = 1"
        ).fetchall()
    ids = set()
    for row in rows:
        try:
            cfg = json.loads(row["config_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if cfg.get("page_type") == "flowchart":
            continue
        if cfg.get("exercises") or cfg.get("steps"):
            ids.add(row["chapter_id"])
    return ids


@router.get("/last-reading")
def last_reading():
    """Most recently read chapter (by reading_state.updated_at), for the continue card."""
    with get_conn() as c:
        row = c.execute(
            """SELECT chapter_id, scroll_position, updated_at FROM reading_state
               ORDER BY updated_at DESC, rowid DESC LIMIT 1"""
        ).fetchone()
    if not row:
        return None
    ch = next((x for x in list_chapters() if x["id"] == row["chapter_id"]), None)
    return {
        "chapter_id": row["chapter_id"],
        "title": ch["title"] if ch else None,
        "scroll_position": row["scroll_position"],
        "updated_at": row["updated_at"],
        "progress_pct": ch["progress_pct"] if ch else None,
    }


@router.get("/chapters/{chapter_id}")
def get_chapter(chapter_id: str):
    """章节元数据。Chapter ids use ch01..ch08 (handoff v2.0 决策 4).

    A chapter in the canonical framework is always resolvable (its metadata is
    returned even before the book text is placed); only truly unknown ids 404.
    """
    for ch in list_chapters():
        if ch["id"] == chapter_id:
            return {"id": ch["id"], "title": ch["title"],
                    "has_steps": ch["id"] in _chapters_with_configs()}
    raise HTTPException(404, f"Chapter {chapter_id} not found")


@router.get("/chapters/{chapter_id}/content")
def get_chapter_content(chapter_id: str):
    """返回章节内容（Phase A: 单页 HTML；旧 4 章走 styled 多页 fallback）。"""
    # 1. Validate chapter exists (framework-aware)
    valid_ids = {c["id"] for c in list_chapters()}
    if chapter_id not in valid_ids:
        raise HTTPException(404, f"Chapter {chapter_id} not found")

    # 2. Phase A primary path: read chapter_html/{stem}.html where stem maps to chapter_id
    target_id = chapter_id

    chapter = next((c for c in _scan_chapters() if c["id"] == target_id), None)
    if chapter and chapter["has_html"]:
        stem = next(
            (s for s, m in _build_stem_map().items() if m == target_id),
            None,
        )
        if stem:
            html_path = _resolve_dir(CHAPTER_HTML_DIR) / f"{stem}.html"
            if html_path.exists():
                content = html_path.read_text(encoding="utf-8")
                # cross-origin fix: rewrite relative image src to absolute API URL
                content = content.replace(
                    'src="images/',
                    f'src="/api/book-images/{target_id}/',
                )
                return {
                    "chapter_id": chapter_id,
                    "format": "html",
                    "pages": [content],
                    "page_count": 1,
                }

    # 3. Legacy fallback: chapters_md_styled/styled_p*.html (only ch4)
    styled_dir = Path(BOOK_MD_DIR + "_styled")
    if styled_dir.exists():
        html_files = sorted(
            styled_dir.glob("styled_p*.html"),
            key=lambda p: int(p.stem.replace("styled_p", "")),
        )
        if html_files:
            pages = []
            for f in html_files:
                content = f.read_text(encoding="utf-8")
                content = content.replace(
                    'src="images/',
                    f'src="/api/book-images/{chapter_id}/',
                )
                pages.append(content)
            return {
                "chapter_id": chapter_id,
                "format": "styled_html",
                "pages": pages,
                "page_count": len(pages),
            }

    raise HTTPException(404, f"Chapter {chapter_id} content not found")


@lru_cache(maxsize=1)
def _build_stem_map() -> dict[str, str]:
    """stem (filename without ext) -> new chapter id. Used to reverse-look-up
    the file path when serving content."""
    html_dir = _resolve_dir(CHAPTER_HTML_DIR)
    md_dir = _resolve_dir(CHAPTER_MD_DIR_NEW)
    stem_map: dict[str, str] = {}
    for d in (html_dir, md_dir):
        if not d.exists():
            continue
        for f in d.glob("*"):
            stem = f.stem
            meta = _strip_chapter_filename(stem)
            if meta:
                stem_map[stem] = meta["id"]
    return stem_map


def get_chapter_md(chapter_id: str) -> str | None:
    """Read the chapter's markdown source (chapter_md/). Shared by summary/chat.

    chapter_id uses the unified ch01..ch08 format (handoff v2.0 决策 4).
    Returns None if no MD file exists for the chapter.
    """
    new_id = chapter_id
    md_dir = _resolve_dir(CHAPTER_MD_DIR_NEW)
    for stem, pid in _build_stem_map().items():
        if pid == new_id:
            p = md_dir / f"{stem}.md"
            if p.exists():
                return p.read_text(encoding="utf-8")
    return None


@router.get("/chapters/{chapter_id}/state")
def get_reading_state(chapter_id: str):
    """阅读位置（M1 简版：仅 last_step_id 和 scroll_position）。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_step_id, scroll_position, updated_at FROM reading_state WHERE chapter_id = ?",
            (chapter_id,),
        ).fetchone()
    if not row:
        return {"chapter_id": chapter_id, "last_step_id": None, "scroll_position": 0}
    return dict(row)


@router.put("/chapters/{chapter_id}/state")
def update_reading_state(chapter_id: str, body: dict):
    """更新阅读位置。"""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO reading_state (chapter_id, last_step_id, scroll_position, updated_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(chapter_id) DO UPDATE SET
                 last_step_id = excluded.last_step_id,
                 scroll_position = excluded.scroll_position,
                 updated_at = excluded.updated_at""",
            (chapter_id, body.get("last_step_id"), body.get("scroll_position", 0)),
        )
    return {"ok": True}

@router.get("/chapters/{chapter_id}/status")
def get_chapter_status(chapter_id: str):
    """Get learner progress for a chapter (M5.1).

    Returns:
      - chapter_id: str
      - is_submitted: bool (all declared steps in this chapter are submitted)
      - submitted_steps: list[str] (step_ids that have been submitted)
      - total_steps: int (declared exercises count)
      - submitted_count: int
      - lock_state: dict | None (upstream gating info, only for ch07 today)

    lock_state for ch07:
      - upstream: list[str] (upstream chapter_ids: ch03, ch04)
      - ready: bool (all upstream chapters are fully submitted)
      - upstream_status: dict[ch_id, {is_submitted, submitted_count, total_steps}]
    """
    from app.runtime.config_loader import load_chapter_config
    cfg = load_chapter_config(chapter_id) or {}
    expected = [ex.get("step_id") for ex in cfg.get("exercises") or [] if ex.get("step_id")]
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT step_id, status FROM step_runs WHERE chapter_id = ? AND stale = 0",
            (chapter_id,),
        ).fetchall()
        profile = {}
        if chapter_id == "ch06":
            profile_row = conn.execute(
                "SELECT profile_json FROM learner_profiles WHERE user_id = ?",
                (os.getenv("DEFAULT_USER_ID", "local"),),
            ).fetchone()
            if profile_row:
                try:
                    profile = json.loads(profile_row["profile_json"] or "{}")
                except (json.JSONDecodeError, TypeError):
                    profile = {}
    submitted = list(dict.fromkeys(r["step_id"] for r in rows if r["status"] == "submitted"))
    if chapter_id == "ch06" and (not isinstance(profile.get("likes"), list) or not profile["likes"]):
        submitted = [step_id for step_id in submitted if step_id != "step-2"]
    is_submitted = bool(expected) and all(s in submitted for s in expected)
    from app.runtime.context_requirements import get_upstream_context_status
    lock_state = get_upstream_context_status(
        chapter_id, os.getenv("DEFAULT_USER_ID", "local")
    )
    return {
        "chapter_id": chapter_id,
        "is_submitted": is_submitted,
        "submitted_steps": submitted,
        "submitted_count": len(submitted),
        "total_steps": len(expected),
        "lock_state": lock_state,
    }


def _flowchart_config(chapter_id: str):
    from app.runtime.config_loader import load_chapter_config
    cfg = load_chapter_config(chapter_id) or {}
    if cfg.get("page_type") != "flowchart":
        return None
    return cfg


def _flowchart_decision_points(cfg):
    points = []
    for stage in (cfg.get("flowchart") or {}).get("stages") or []:
        for point in stage.get("decision_points") or []:
            if point.get("id"):
                points.append(point)
    return points


def _flowchart_current_point(cfg, states):
    points = _flowchart_decision_points(cfg)
    if not points:
        return None
    by_id = {row["decision_point_id"]: row for row in states}
    current = points[0]["id"]
    seen = set()
    while current and current not in seen:
        seen.add(current)
        row = by_id.get(current)
        if not row or not row.get("selected_branch"):
            break
        point = next((p for p in points if p["id"] == current), None)
        branch = next((b for b in (point.get("branches") or []) if b.get("label") == row["selected_branch"]), None)
        nxt = (branch or {}).get("next")
        if nxt and nxt != current:
            current = nxt
        else:
            break
    return current


def _flowchart_upstream_summary():
    from app.runtime.config_loader import load_chapter_config, load_profile
    profile = load_profile(os.getenv("DEFAULT_USER_ID", "local")) or {}
    summary = {}
    for chapter_id, fields in (
        ("ch04", ("work_purpose", "values")),
        ("ch05", ("talents",)),
        ("ch06", ("likes",)),
        ("ch07", ("ideal_works",)),
    ):
        cfg = load_chapter_config(chapter_id) or {}
        total = len(cfg.get("exercises") or [])
        with get_conn() as conn:
            submitted = conn.execute(
                "SELECT COUNT(DISTINCT step_id) AS n FROM step_runs WHERE chapter_id = ? AND status = 'submitted' AND stale = 0",
                (chapter_id,),
            ).fetchone()["n"]
            stale_dirty = conn.execute(
                "SELECT COUNT(*) AS n FROM step_runs WHERE chapter_id = ? AND status = 'submitted' AND stale = 1",
                (chapter_id,),
            ).fetchone()["n"] > 0
        missing = [field for field in fields if profile.get(field) in (None, "", [], {})]
        summary[chapter_id] = {
            "completed": bool(total) and submitted >= total and not missing,
            "missing_fields": missing,
            "submitted_steps": submitted,
            "total_steps": total,
            "stale_dirty": bool(stale_dirty),
        }
    return summary


@router.get("/chapters/{chapter_id}/flowchart-state")
def get_flowchart_state(chapter_id: str):
    cfg = _flowchart_config(chapter_id)
    if not cfg:
        raise HTTPException(404, "not a flowchart chapter")
    user_id = os.getenv("DEFAULT_USER_ID", "local")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT decision_point_id, selected_branch, comment_text, updated_at FROM flowchart_state WHERE user_id = ? AND chapter_id = ?",
            (user_id, chapter_id),
        ).fetchall()
    states = [dict(row) for row in rows]
    return {
        "chapter_id": chapter_id,
        "current_point_id": _flowchart_current_point(cfg, states),
        "states": states,
        "upstream": _flowchart_upstream_summary(),
    }


@router.put("/chapters/{chapter_id}/flowchart-state")
def save_flowchart_state(chapter_id: str, body: dict):
    cfg = _flowchart_config(chapter_id)
    if not cfg:
        raise HTTPException(404, "not a flowchart chapter")
    dp_id = str(body.get("decision_point_id") or "").strip()
    point = next((p for p in _flowchart_decision_points(cfg) if p["id"] == dp_id), None)
    if not point:
        raise HTTPException(422, "unknown decision_point_id")
    selected = body.get("selected_branch")
    if selected is not None:
        labels = [branch.get("label") for branch in point.get("branches") or []]
        if selected not in labels:
            raise HTTPException(422, "unknown branch label")
    comment = body.get("comment_text")
    if comment is not None:
        comment = str(comment)
    user_id = os.getenv("DEFAULT_USER_ID", "local")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO flowchart_state (user_id, chapter_id, decision_point_id, selected_branch, comment_text, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(user_id, chapter_id, decision_point_id) DO UPDATE SET
                 selected_branch = excluded.selected_branch,
                 comment_text = excluded.comment_text,
                 updated_at = excluded.updated_at""",
            (user_id, chapter_id, dp_id, selected, comment),
        )
    return {"ok": True, "decision_point_id": dp_id}

