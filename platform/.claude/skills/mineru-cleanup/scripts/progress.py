"""Scan the skill's output directory and report which PDF pages have been converted.

Usage:
    python scripts/progress.py [path-to-output-dir]

Default: scans the skill's own output/ directory.

Detects converted page ranges from directory naming patterns:
  - ch1-3-pages-30-80  -> chapter heading + pages 30..80
  - pages-100-200       -> pages 100..200
  - any dir containing "_content_list_v2.json" -> 1-page run (optional -e flag)

Combines overlapping/adjacent ranges. Prints:
  - Total PDF page count (from largest sidecar or arg)
  - Coverage map (which pages converted vs which remain)
  - Per-run summary (mtime, output files, image count, report warnings)
  - Suggested MinerU command for next unconverted run

Pure stdlib. No external deps.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path


# Pattern: optional "<chapter-prefix>-pages-<START>-<END>"
# e.g. "ch1-3-pages-30-80" or "pages-100-200" or "test-30-50"
_PAGES_RE = re.compile(r"(?:pages|full-book)-(\d+)-(\d+)$")
_OUTPUT_ROOT_HINT = "output"


def find_runs(output_dir: Path) -> list:
    """Find all conversion runs under output_dir. Each run is a dict
    with: dir, start, end, mtime, sidecar_paths, cleanup_path, html_path."""
    runs = []
    if not output_dir.exists():
        return runs
    for child in sorted(output_dir.iterdir()):
        if not child.is_dir():
            continue
        # Look for the page-range suffix
        m = _PAGES_RE.search(child.name)
        if not m:
            continue
        start = int(m.group(1))
        end = int(m.group(2))
        if start >= end:
            continue
        # Find sidecar files anywhere inside
        sidecars = list(child.rglob("*.content_list_v2.json"))
        # Count MD / cleaned / html files
        md_files = list(child.rglob("*.md"))
        cleaned_files = list(child.rglob("*.cleaned.md"))
        html_files = list(child.rglob("*.html"))
        report_files = list(child.rglob("*.cleanup-report.json"))
        mtime = datetime.fromtimestamp(child.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        runs.append({
            "dir": child,
            "name": child.name,
            "start": start,
            "end": end,
            "pages": end - start + 1,
            "mtime": mtime,
            "md_files": len(md_files),
            "cleaned_files": len(cleaned_files),
            "html_files": len(html_files),
            "report_files": len(report_files),
            "images": len(list(child.rglob("images/*.jpg"))) + len(list(child.rglob("images/*.png"))),
            "warnings": _read_warnings(report_files),
        })
    return runs


def _read_warnings(report_files: list) -> int:
    if not report_files:
        return 0
    try:
        data = json.loads(report_files[0].read_text(encoding="utf-8"))
        return len(data.get("warnings", []))
    except (OSError, ValueError):
        return 0


def merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sort and merge overlapping/adjacent ranges."""
    if not ranges:
        return []
    sorted_ranges = sorted(ranges)
    merged = [sorted_ranges[0]]
    for s, e in sorted_ranges[1:]:
        if s <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def complement(merged: list[tuple[int, int]], total: int) -> list[tuple[int, int]]:
    """Return the gaps between merged ranges and [1..total]."""
    if total <= 0 or not merged:
        return [(1, total)] if total > 0 else []
    gaps = []
    covered_up_to = 0
    for s, e in merged:
        if s > covered_up_to + 1:
            gaps.append((covered_up_to + 1, s - 1))
        covered_up_to = max(covered_up_to, e)
    if covered_up_to < total:
        gaps.append((covered_up_to + 1, total))
    return gaps


def detect_total_pages(output_dir: Path) -> int:
    """Try to find total PDF pages. Heuristic:
    1. Use the largest sidecar's pdf_info (all runs' sidecars should have same count for same PDF)
    2. Fallback to max(end) across runs (understates total if PDF not fully covered)
    """
    runs = find_runs(output_dir)
    if not runs:
        return 0
    pdf_info_counts: list[int] = []
    for run in runs:
        for middle_path in run["dir"].rglob("*middle.json"):
            try:
                data = json.loads(middle_path.read_text(encoding="utf-8"))
                pdf_info = data.get("pdf_info") or []
                if pdf_info and isinstance(pdf_info, list):
                    pdf_info_counts.append(len(pdf_info))
            except (OSError, ValueError):
                continue
    if pdf_info_counts:
        return max(pdf_info_counts)
    # Fallback: use max(end) — but this is clearly inaccurate for a partially-covered PDF
    return max(r["end"] for r in runs)


def progress_bar(covered_pct: float, width: int = 50) -> str:
    filled = int(covered_pct * width / 100)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {covered_pct:.0f}%"


def main(argv: list) -> int:
    # Parse CLI: optional --total-pages N, optional positional path
    total_pages_arg = None
    positional = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--total-pages" and i + 1 < len(argv):
            total_pages_arg = int(argv[i + 1])
            i += 2
        else:
            positional.append(arg)
            i += 1

    if positional and positional[0]:
        output_dir = Path(positional[0]).resolve()
    else:
        cwd_output = Path.cwd() / "output"
        skill_dir = Path(__file__).resolve().parent.parent
        skill_output = skill_dir / "output"
        for candidate in [cwd_output, skill_output]:
            if candidate.exists():
                output_dir = candidate.resolve()
                break
        else:
            output_dir = cwd_output.resolve()

    if not output_dir.exists():
        print(f"ERROR: {output_dir} does not exist", file=sys.stderr)
        return 1

    runs = find_runs(output_dir)
    if not runs:
        print(f"No conversion runs found in {output_dir}")
        print("(directory names must match pattern *pages-<start>-<end>)")
        return 1

    total_pages = total_pages_arg or detect_total_pages(output_dir)
    covered = sorted([(r["start"], r["end"]) for r in runs])
    merged = merge_ranges(covered)
    gaps = complement(merged, total_pages)
    covered_count = sum(e - s + 1 for s, e in merged)

    print(f"=== mineru-cleanup progress: {output_dir.name} ===")
    if total_pages_arg:
        print(f"PDF total pages: {total_pages} (user-specified)")
    else:
        print(f"PDF total pages: {total_pages} (auto-detected from sidecar)")
    print(f"Covered: {covered_count}/{total_pages} pages "
          f"({100*covered_count/total_pages:.1f}%)")
    print(f"Progress: {progress_bar(100*covered_count/total_pages)}")
    print()

    print("=== Converted runs ===")
    for r in runs:
        print(f"  [{r['mtime']}] {r['name']}")
        print(f"      pages {r['start']}-{r['end']} ({r['pages']} pages)")
        print(f"      files: md={r['md_files']} cleaned={r['cleaned_files']} "
              f"html={r['html_files']} images={r['images']} warnings={r['warnings']}")
    print()

    if gaps:
        print("=== Unconverted gaps ===")
        for s, e in gaps:
            count = e - s + 1
            print(f"  pages {s}-{e} ({count} pages)")
        print()
        print("=== Suggested MinerU command for next gap ===")
        next_s, next_e = gaps[0]
        count = next_e - next_s + 1
        # Estimate time: pipeline backend ~1.5s/page on CPU
        est_min = max(1, count * 1.5 / 60)
        print(f"  # {count} pages, est ~{est_min:.1f} min")
        print(f'  mineru -p "<PDF_PATH>" -o "{output_dir}/pages-{next_s}-{next_e}" \\')
        print(f'    -b pipeline -m auto -s {next_s} -e {next_e} -l ch')
        print()
        print(f"  # After MinerU finishes, run cleanup on the same dir:")
        print(f'  python scripts/run.py "{output_dir}/pages-{next_s}-{next_e}/auto" --with-html')
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
