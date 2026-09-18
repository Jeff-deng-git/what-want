"""DB vs JSON chapter_config consistency check.

Ref doc: llm_prompt_design/docs/重构开放问题_设计侧确认.md 附2:
  "DB vs JSON 一致性脚本: 建议新增脚本对比 8 章 DB config_json 与
   config/chapters/*.json，报警漂移（防 ch04 类问题复发）".

Reads the active config_json for each chapter from chapter_configs and compares
against the canonical JSON in config/chapters/. Exit code 0 if clean, 1 if any
drift, 2 if pre-flight (missing files / DB unreachable).

Usage:
    python scripts/check_config_consistency.py
    python scripts/check_config_consistency.py --chapter ch04   # single chapter
    python scripts/check_config_consistency.py --json-only      # just dump drift report
"""
import argparse
import json
import os
import sys


PROJECT_ROOT = r"D:\AI_Project\What_Want"
CHAPTER_JSON_DIR = os.path.join(PROJECT_ROOT, "llm_prompt_design", "config", "chapters")
CHAPTERS = ["ch01", "ch02", "ch03", "ch04", "ch05", "ch06", "ch07", "ch08"]


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize(cfg):
    """Strip noise that legitimately differs between file and DB (e.g. active
    flags injected by the seed). Returns a dict ready for deep-compare."""
    out = dict(cfg)
    for k in ("active", "version", "created_at"):
        out.pop(k, None)
    return out


def check_one(chapter_id):
    """Compare one chapter's DB active row vs JSON file. Returns a drift report.

    Returns: {
      'chapter_id': str,
      'present_in_db': bool,
      'present_in_file': bool,
      'drift_keys': [str],   # top-level keys with different values
      'missing_db_keys': [str],
      'missing_file_keys': [str],
      'exercises_count_diff': (int|None, int|None),  # (file, db)
    }
    """
    file_path = os.path.join(CHAPTER_JSON_DIR, "chapter_config_" + chapter_id + ".json")
    file_present = os.path.exists(file_path)
    file_cfg = _load_json(file_path) if file_present else None

    db_cfg = None
    db_present = False
    try:
        sys.path.insert(0, PROJECT_ROOT)
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "platform", "backend"))
        import importlib
        import app.config  # noqa: E402
        import app.db  # noqa: E402
        importlib.reload(app.config)
        importlib.reload(app.db)
        from app.db import get_conn  # noqa: E402
        with get_conn() as conn:
            row = conn.execute(
                "SELECT config_json FROM chapter_configs "
                "WHERE chapter_id = ? AND active = 1 "
                "ORDER BY version DESC LIMIT 1",
                (chapter_id,),
            ).fetchone()
        if row:
            db_present = True
            db_cfg = json.loads(row["config_json"])
    except Exception as e:
        return {
            "chapter_id": chapter_id,
            "error": "db_query_failed: " + str(e),
            "present_in_db": False,
            "present_in_file": file_present,
            "drift_keys": [],
            "missing_db_keys": [],
            "missing_file_keys": [],
            "exercises_count_diff": None,
        }

    if not file_present or not db_present:
        return {
            "chapter_id": chapter_id,
            "present_in_db": db_present,
            "present_in_file": file_present,
            "drift_keys": [],
            "missing_db_keys": [],
            "missing_file_keys": [],
            "exercises_count_diff": None,
        }

    file_n = _normalize(file_cfg)
    db_n = _normalize(db_cfg)
    file_keys = set(file_n.keys())
    db_keys = set(db_n.keys())
    drift = []
    for k in file_keys & db_keys:
        if file_n[k] != db_n[k]:
            drift.append(k)

    file_ex = (file_n.get("exercises") or [])
    db_ex = (db_n.get("exercises") or [])
    return {
        "chapter_id": chapter_id,
        "present_in_db": True,
        "present_in_file": True,
        "drift_keys": sorted(drift),
        "missing_db_keys": sorted(file_keys - db_keys),
        "missing_file_keys": sorted(db_keys - file_keys),
        "exercises_count_diff": (len(file_ex), len(db_ex)),
    }


def main():
    parser = argparse.ArgumentParser(description="DB vs JSON chapter_config consistency check")
    parser.add_argument("--chapter", help="only check one chapter (e.g. ch04)")
    parser.add_argument("--json-only", action="store_true", help="print report as JSON and exit")
    args = parser.parse_args()

    targets = [args.chapter] if args.chapter else CHAPTERS
    reports = []
    for ch in targets:
        reports.append(check_one(ch))

    if args.json_only:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return 0

    has_drift = False
    has_missing = False
    has_error = False
    for r in reports:
        if r.get("error"):
            has_error = True
            print("[ERR] " + r["chapter_id"] + "  " + r["error"])
            continue
        if not r["present_in_db"] and not r["present_in_file"]:
            has_missing = True
            print("[MISS] " + r["chapter_id"] + "  neither file nor DB row present")
            continue
        if not r["present_in_db"]:
            has_missing = True
            print("[DB-MISS] " + r["chapter_id"] + "  file present, DB row missing (run seed_all_chapters.py)")
            continue
        if not r["present_in_file"]:
            has_missing = True
            print("[FILE-MISS] " + r["chapter_id"] + "  DB row present, file missing")
            continue
        if r["drift_keys"]:
            has_drift = True
            extras = ""
            if r["missing_db_keys"]:
                extras += "  missing_in_db=" + ",".join(r["missing_db_keys"])
            if r["missing_file_keys"]:
                extras += "  missing_in_file=" + ",".join(r["missing_file_keys"])
            print("[DRIFT] " + r["chapter_id"] + "  drift=" + ",".join(r["drift_keys"]) + extras)
            fc, dc = r["exercises_count_diff"]
            print("        exercises_count: file=" + str(fc) + " db=" + str(dc))
        else:
            fc, dc = r["exercises_count_diff"]
            print("[OK] " + r["chapter_id"] + "  exercises=" + str(fc) + " (file=db)")

    if has_error:
        print("\nResult: ERROR (DB unreachable or schema mismatch)")
        return 2
    if has_missing or has_drift:
        print("\nResult: DRIFT or MISSING detected. Fix source of truth and re-seed.")
        return 1
    print("\nResult: CLEAN. DB active rows match canonical JSON files for all chapters.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

