#!/usr/bin/env python3
"""Build static JSON data for GitHub Pages deployment from chapter_md sources.

Usage:    python tools/build_static_data.py
Output:   data/chapters.json (read by the static frontend shim)
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAPTER_MD_DIR = ROOT / "chapter_md"
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Canonical book framework (matches platform/backend/app/routers/book.py)
CANONICAL = [
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

CN_DIGITS = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9
}


def _cn_num(s: str):
    if s.isdigit():
        return int(s)
    if len(s) == 1:
        return CN_DIGITS.get(s)
    if len(s) == 2 and s[0] == "十":
        return 10 + CN_DIGITS.get(s[1], 0)
    return None


def _strip_filename(stem: str):
    """Parse a chapter_md filename stem -> {id, title, sort_key}."""
    s = re.sub(r"^如何找到想做的事_\(八木仁平\)_\(.*?\)_cleaned[ -]Final-?", "", stem).strip()
    s = re.sub(r"^[-_]+", "", s)
    if not s:
        return None

    if s.startswith("序-") or s == "序言":
        return {"id": "preface", "title": "序言", "sort_key": 0}

    m = re.match(r"^第([一二三四五六七八九十百千]+|\d+)章[-\s]*(.*)$", s)
    if m:
        cn = m.group(1)
        rest = m.group(2).strip().replace("_", "")
        num = _cn_num(cn)
        if num is None:
            return None
        title = f"第{cn}章 {rest}".strip() if rest else f"第{cn}章"
        return {"id": f"ch{num:02d}", "title": title, "sort_key": num}

    if s == "问题清单":
        return {"id": "questions", "title": "问题清单", "sort_key": 99}

    return None


def main():
    scanned = {}
    if CHAPTER_MD_DIR.exists():
        for f in sorted(CHAPTER_MD_DIR.glob("*.md")):
            meta = _strip_filename(f.stem)
            if not meta:
                continue
            entry = scanned.setdefault(
                meta["id"],
                {**meta, "has_md": False, "markdown": ""}
            )
            entry["has_md"] = True
            entry["markdown"] = f.read_text(encoding="utf-8")

    chapters = []
    contents = {}
    for fw in CANONICAL:
        cid = fw["id"]
        sc = scanned.get(cid, {})
        has_md = bool(sc.get("has_md", False))
        chapters.append({
            "id": cid,
            "title": sc.get("title") or fw["title"],
            "has_html": has_md,   # treat as readable in static mode
            "has_md": has_md,
            "has_steps": False,   # interactive steps need a backend
            "sort_key": fw["sort_key"],
            "progress_pct": None,
            "last_read_at": None,
            "scroll_position": None,
            "submitted_steps": None,
            "total_steps": None,
        })
        if has_md:
            contents[cid] = {
                "chapter_id": cid,
                "format": "markdown",
                "markdown": sc.get("markdown", ""),
            }

    out = {"chapters": chapters, "contents": contents}
    out_path = DATA_DIR / "chapters.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({len(chapters)} chapters, {len(contents)} with content)")


if __name__ == "__main__":
    main()
