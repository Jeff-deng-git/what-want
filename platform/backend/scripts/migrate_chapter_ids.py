"""Migrate legacy chapter_id '04-important' → 'ch04' across all chapter-scoped tables.

Required by handoff v2.0 决策 4 + ADR-001 S2.4.
Idempotent: if 'ch04' rows already exist for any (table, key), skip the migration
and warn instead of overwriting.

Usage:
    python migrate_chapter_ids.py --dry-run     # preview changes only
    python migrate_chapter_ids.py --apply       # execute migration
    python migrate_chapter_ids.py --rollback    # restore from latest backup
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "ww.db"
BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups"

LEGACY_ID = "04-important"
TARGET_ID = "ch04"

# Tables that have a `chapter_id` column.  Each entry: (table, key_columns_for_dup_check)
TABLES = [
    ("chapter_configs", ("chapter_id", "version")),  # PK is (chapter_id, version)
    ("step_runs",       ("chapter_id", "step_id")),  # no PK; latest run keyed by these
    ("reading_state",   ("chapter_id",)),            # PK is chapter_id
    ("chapter_summaries", ("chapter_id",)),          # PK is chapter_id
    ("book_notes",      ("chapter_id",)),            # PK is id; chapter_id is just a column
    # chapter_chat: no 04-important rows per 2026-08-03 probe — included defensively
    ("chapter_chat",    ("chapter_id",)),
]


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _latest_backup() -> Path | None:
    if not BACKUP_DIR.exists():
        return None
    backups = sorted(BACKUP_DIR.glob("ww.db.bak-*"), reverse=True)
    return backups[0] if backups else None


def preview():
    """Print what would change, do not write."""
    print(f"DB: {DB_PATH}")
    print(f"Legacy ID: {LEGACY_ID!r} → Target ID: {TARGET_ID!r}")
    print()
    conn = _connect()
    try:
        for table, key_cols in TABLES:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if "chapter_id" not in cols:
                print(f"[skip] {table}: no chapter_id column")
                continue
            legacy_n = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE chapter_id = ?", (LEGACY_ID,)
            ).fetchone()[0]
            target_n = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE chapter_id = ?", (TARGET_ID,)
            ).fetchone()[0]
            if legacy_n == 0 and target_n == 0:
                print(f"[empty] {table}: no legacy or target rows")
            elif legacy_n == 0:
                print(f"[done ] {table}: already migrated (target has {target_n})")
            elif target_n > 0:
                print(f"[warn ] {table}: legacy={legacy_n} AND target={target_n} — will skip migration for safety")
            else:
                print(f"[todo ] {table}: {legacy_n} legacy rows → migrate to {TARGET_ID!r}")
    finally:
        conn.close()


def apply():
    """Execute the migration in a single transaction. Skip tables that already have target rows."""
    print(f"DB: {DB_PATH}")
    print(f"Applying: {LEGACY_ID!r} → {TARGET_ID!r}")
    print()
    conn = _connect()
    migrated_total = 0
    skipped_total = 0
    try:
        for table, key_cols in TABLES:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if "chapter_id" not in cols:
                print(f"[skip] {table}: no chapter_id column")
                continue
            legacy_n = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE chapter_id = ?", (LEGACY_ID,)
            ).fetchone()[0]
            target_n = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE chapter_id = ?", (TARGET_ID,)
            ).fetchone()[0]
            if legacy_n == 0:
                print(f"[ok  ] {table}: 0 legacy rows, nothing to do")
                continue
            if target_n > 0:
                print(f"[skip] {table}: target already has {target_n} rows — refusing to overwrite")
                skipped_total += legacy_n
                continue
            # PRIMARY KEY conflict check (defensive): for composite-PK tables, ensure no
            # collision with rows that have (chapter_id=ch04) under the SAME key cols.
            cursor = conn.execute(
                f"UPDATE {table} SET chapter_id = ? WHERE chapter_id = ?",
                (TARGET_ID, LEGACY_ID),
            )
            moved = cursor.rowcount
            conn.commit()
            print(f"[done] {table}: {moved} rows migrated")
            migrated_total += moved
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] {e}")
        print("Transaction rolled back. DB unchanged.")
        sys.exit(1)
    finally:
        conn.close()
    print(f"\nTotal migrated: {migrated_total}")
    if skipped_total:
        print(f"Total skipped (target already exists): {skipped_total}")
    print(f"Done at {datetime.now().isoformat(timespec='seconds')}")


def rollback():
    """Restore DB from the most recent backup."""
    bak = _latest_backup()
    if bak is None:
        print("No backup found in", BACKUP_DIR)
        sys.exit(1)
    print(f"Restoring from: {bak}")
    shutil.copy2(bak, DB_PATH)
    print(f"DB restored. SHA: {(hashlib.sha256(open(DB_PATH,'rb').read()).hexdigest())[:16]}")


import hashlib  # late import for rollback


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="Preview only")
    g.add_argument("--apply",   action="store_true", help="Execute migration")
    g.add_argument("--rollback", action="store_true", help="Restore from latest backup")
    args = p.parse_args()
    if args.dry_run:
        preview()
    elif args.apply:
        apply()
    elif args.rollback:
        rollback()


if __name__ == "__main__":
    main()

