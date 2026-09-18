"""mineru-cleanup CLI: orchestrates stages 1-5 on a MinerU workdir.

Usage:
    python scripts/run.py <workdir> [--dry-run] [--disable RULE_ID ...]
                                       [--ignore-gates] [--verbose] [--list-rules]

Outputs (in <workdir>):
    {stem}.cleaned.md          (NOT written on --dry-run or when hard gates fail)
    {stem}.cleanup-report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure scripts/ is on sys.path so stage_* modules can be imported
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _types import DEFAULT_CONFIG, Context, Warning  # noqa: E402
import stage_01_structure  # noqa: E402
import stage_02_typography  # noqa: E402
import stage_03_blocks  # noqa: E402
import stage_04_ocr  # noqa: E402
import stage_05_verify  # noqa: E402


# --- File discovery ------------------------------------------------------


def find_md_file(workdir: Path) -> Path:
    """Find the .md file in the workdir. Excludes .cleaned.md outputs."""
    candidates = sorted(
        p for p in workdir.glob("*.md")
        if not p.name.endswith(".cleaned.md")
    )
    if not candidates:
        raise FileNotFoundError(f"No .md found in {workdir}")
    if len(candidates) > 1:
        # Prefer the one with sidecar
        for c in candidates:
            stem = c.stem
            if any((workdir / f"{stem}{s}").exists() for s in
                   ("_content_list.json", "_content_list_v2.json", "_middle.json")):
                return c
        raise FileNotFoundError(
            f"Multiple .md files in {workdir} and none has a sidecar: "
            f"{[c.name for c in candidates]}"
        )
    return candidates[0]


# --- Config loader -------------------------------------------------------


def load_config(workdir: Path, verbose: bool) -> dict:
    """Load per-book config from <workdir>/mineru-cleanup.json if present; merge with defaults."""
    cfg = dict(DEFAULT_CONFIG)
    cfg_path = workdir / "mineru-cleanup.json"
    if cfg_path.exists():
        try:
            with cfg_path.open("r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            for k, v in user_cfg.items():
                if k == "identifier_rules":
                    # Merge user identifier_rules with defaults (user entries override by id)
                    existing = {r.get("id"): r for r in cfg.get("identifier_rules", [])}
                    for r in v:
                        existing[r.get("id", f"ocr.identifier.{r.get('prefix', 'unknown').lower()}")] = r
                    cfg["identifier_rules"] = list(existing.values())
                else:
                    cfg[k] = v
        except (json.JSONDecodeError, OSError) as e:
            print(f"WARNING: failed to load {cfg_path}: {e}", file=sys.stderr)
    cfg["_verbose"] = verbose
    return cfg


# --- Orchestration -------------------------------------------------------


def list_rules() -> None:
    """Print all available rules with id / scope / confidence / description."""
    rules = []
    for stage in (stage_02_typography, stage_03_blocks, stage_04_ocr):
        for r in stage.RULES if hasattr(stage, "RULES") else []:
            rules.append(r)
        if hasattr(stage, "_build_rules"):
            for r in stage._build_rules(DEFAULT_CONFIG):
                rules.append(r)
    # De-dupe by id
    seen = {}
    for r in rules:
        seen[r["id"]] = r
    print(f"{'ID':<40} {'SCOPE':<10} {'CONFIDENCE':<10} DESCRIPTION")
    print("-" * 100)
    for r in sorted(seen.values(), key=lambda x: x["id"]):
        print(f"{r['id']:<40} {r.get('scope', ''):<10} {r.get('confidence', ''):<10} ")


def run(args: argparse.Namespace) -> int:
    """Run the cleanup pipeline. Returns exit code (0 ok, 1 hard-failure, 2 user error)."""
    workdir = Path(args.workdir).resolve()
    if not workdir.is_dir():
        print(f"ERROR: {workdir} is not a directory", file=sys.stderr)
        return 2

    cfg = load_config(workdir, args.verbose)
    if args.disable:
        cfg["disabled_rules"] = list(set(cfg.get("disabled_rules", []) + list(args.disable)))

    # Optional: extract color emphasis from source PDF (writes sidecar JSON to workdir).
    # Used by md_to_html.py in Step 3 to wrap blue-text phrases with <span class="pdf-emphasis">.
    # Default off — does not affect cleaned.md / HTML output unless --with-pdf-emphasis is also set.
    if args.pdf_source:
        from pathlib import Path as _P
        pdf_path = _P(args.pdf_source).resolve()
        if not pdf_path.exists():
            print(f"WARNING: --pdf-source not found: {pdf_path}", file=sys.stderr)
        else:
            try:
                import extract_pdf_emphasis as _epe
                emphasis_data = _epe.extract_emphasis(pdf_path)
                emphasis_path = workdir / "mineru-emphasis.json"
                emphasis_path.write_text(
                    __import__("json").dumps(emphasis_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                total = sum(len(v) for v in emphasis_data.values())
                print(f"  pdf-emphasis: {total} phrases across {len(emphasis_data)} pages → {emphasis_path.name}")
            except Exception as e:
                print(f"WARNING: pdf emphasis extraction failed: {e}", file=sys.stderr)

    md_path = find_md_file(workdir)
    original_text = md_path.read_text(encoding="utf-8")
    stem = md_path.stem

    warnings_list: list = []

    # Stage 1
    sentinel_text, regions, blocks, page_metrics = stage_01_structure.apply(
        original_text, warnings_list, cfg, md_path
    )

    ctx = Context(
        page_idx=0,
        blocks=blocks,
        config=cfg,
        warnings=warnings_list,
        protected_regions=regions,
    )

    # Stage 2
    text_after_2, changes_2 = stage_02_typography.apply(sentinel_text, ctx, cfg)
    # Stage 3
    text_after_3, changes_3 = stage_03_blocks.apply(text_after_2, ctx, cfg)
    # Stage 4
    text_after_4, changes_4 = stage_04_ocr.apply(text_after_3, ctx, cfg)

    all_changes = changes_2 + changes_3 + changes_4
    ledger = all_changes

    # Stage 5
    cleaned, report, gate_passed, hard_failures = stage_05_verify.apply(
        cleaned_with_sentinels=text_after_4,
        regions=regions,
        original_text=original_text,
        ledger=ledger,
        cfg=cfg,
        workdir=workdir,
        ignore_gates=args.ignore_gates,
        dry_run=args.dry_run,
        page_metrics=page_metrics,
        blocks=blocks,
    )

    # Merge warnings from all stages into report
    report["warnings"] = [
        {
            "rule_id": w.rule_id,
            "error_type": w.error_type,
            "error_message_first_line": w.error_message_first_line,
            "trace": w.trace if args.verbose else None,
        }
        for w in warnings_list
    ]

    # Write report (always)
    report_path = workdir / f"{stem}.cleanup-report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Write cleaned.md
    cleaned_path = workdir / f"{stem}.cleaned.md"
    if args.dry_run:
        print(f"DRY-RUN: report written to {report_path}; no .cleaned.md written")
    elif cleaned is None:
        print(f"GATES FAILED: {len(hard_failures)} hard failures; report at {report_path}")
        for hf in hard_failures:
            print(f"  - {hf}")
        return 1
    else:
        # Atomic write: write to temp + replace
        tmp_path = workdir / f"{stem}.cleaned.md.tmp"
        tmp_path.write_text(cleaned, encoding="utf-8")
        os.replace(tmp_path, cleaned_path)
        print(f"OK: cleaned.md written to {cleaned_path}; report at {report_path}")
        print(f"  metrics: {report['metrics']}")

    return 0


# --- CLI -----------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(
        prog="mineru-cleanup",
        description="Clean MinerU PDF→MD output (Layer 2 + Layer 3 fixes).",
    )
    p.add_argument("workdir", nargs="?", help="Path to MinerU workdir containing .md + optional sidecar JSONs")
    p.add_argument("--dry-run", action="store_true", help="Write only report; no .cleaned.md")
    p.add_argument("--disable", action="append", default=[], help="Disable rule by id (repeatable)")
    p.add_argument("--ignore-gates", action="store_true", help="Write .cleaned.md even when hard gates fail")
    p.add_argument("--with-html", action="store_true",
                   help="Auto-generate self-contained HTML (images base64 inlined) after cleanup; "
                        "use this for visual comparison vs original PDF")
    p.add_argument("--pdf-source", help="Path to original PDF for color emphasis extraction (writes sidecar JSON to workdir; "
                                        "requires --with-html in Step 3 to actually wrap phrases)")
    p.add_argument("--verbose", action="store_true", help="Include full tracebacks in report warnings")
    p.add_argument("--list-rules", action="store_true", help="List all available rules and exit")
    args = p.parse_args()

    if args.list_rules:
        list_rules()
        return 0
    if not args.workdir:
        p.error("workdir is required (or use --list-rules)")
    rc = run(args)

    # Auto-render HTML if requested and cleanup succeeded
    if rc == 0 and args.with_html:
        try:
            import md_to_html  # noqa: F401 — script-style module
            from pathlib import Path
            for md in sorted(Path(args.workdir).glob("*.cleaned.md")):
                out = md_to_html.md_to_self_contained_html(md)
                size_kb = out.stat().st_size / 1024
                print(f"  html: {out.name} ({size_kb:.1f} KB)")
        except Exception as e:
            print(f"WARNING: HTML render failed: {e}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())