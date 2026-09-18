"""Read a PDF, find non-black colored text spans per page, output as JSON.

Outputs `{page_idx_str: [phrase, ...]}` for pages with at least one
non-black span. Also supports an `--add` mode for merging manually-
specified `custom_phrases` into an existing sidecar JSON (used for cases
where the PDF's color metadata is incomplete — some "blue" text has
color=0 in pymupdf's dict output).

CLI:
  Mode 1 (extract):  python extract_pdf_emphasis.py <pdf> <out.json>
  Mode 2 (add custom):
        python extract_pdf_emphasis.py --add <sidecar.json> <phrase>...
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List


# Adjacent same-color span collector — flushes when color changes or non-empty line break.
def _extract_phrases_from_page(page) -> List[str]:
    import pymupdf  # local import so the file is lazy-importable
    text_dict = page.get_text("dict")
    phrases: List[str] = []
    current_color = None
    current_buf: List[str] = []
    for block in text_dict.get("blocks", []):
        if block.get("type", 0) != 0:
            _flush()
            continue
        for line in block.get("lines", []):
            line_had_text = False
            for span in line.get("spans", []):
                color = span.get("color", 0)
                text = span.get("text", "")
                if not text:
                    continue
                line_had_text = True
                if color == 0:
                    _flush()
                    current_color = None
                elif color == current_color:
                    current_buf.append(text)
                else:
                    _flush()
                    current_color = color
                    current_buf = [text]
            if line_had_text:
                _flush()
                current_color = None
        _flush()
        current_color = None
    _flush()
    return phrases

    def _flush() -> None:
        nonlocal current_color, current_buf
        if current_buf:
            joined = "".join(current_buf).strip()
            # Skip very short or noise phrases (length < 2 chars, or single punctuation)
            if len(joined) >= 2 and not joined.isspace():
                phrases.append(joined)
        current_buf = []
        current_color = None


def extract_emphasis(pdf_path: Path) -> Dict[str, List[str]]:
    """Walk all pages. Return {page_idx_str: [phrase, ...]} sorted by page."""
    import pymupdf
    result: Dict[str, List[str]] = {}
    doc = pymupdf.open(str(pdf_path))
    try:
        for page_idx, page in enumerate(doc):
            phrases = _extract_phrases_from_page(page)
            if phrases:
                result[str(page_idx)] = phrases
    finally:
        doc.close()
    return result


def add_custom_phrases(sidecar_path: Path, phrases: List[str]) -> Dict[str, List[str]]:
    """Merge `custom_phrases` into an existing sidecar JSON.

    Loads the sidecar if present, dedupes new phrases against existing,
    writes back with the special key `custom_phrases`. Returns the merged data.
    """
    data: Dict[str, List[str]] = {}
    if sidecar_path.exists():
        try:
            data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    existing = set(data.get("custom_phrases", []))
    new = [p for p in phrases if isinstance(p, str) and p.strip() and p not in existing]
    if not new:
        return data
    data["custom_phrases"] = list(existing) + new
    sidecar_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python extract_pdf_emphasis.py <pdf> <output.json>", file=sys.stderr)
        return 2
    pdf_path = Path(sys.argv[1]).resolve()
    out_path = Path(sys.argv[2]).resolve()
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 2

    result = extract_emphasis(pdf_path)
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    page_count = len(result)
    phrase_count = sum(len(v) for v in result.values())
    print(
        f"OK: {phrase_count} phrases across {page_count} pages → {out_path}"
    )
    # Print first 10 sample phrases for sanity check
    samples = []
    for p, phrases in result.items():
        samples.extend([(p, ph) for ph in phrases])
    if samples:
        print("=== sample phrases (first 10) ===")
        for page, phrase in samples[:10]:
            print(f"  page {page}: {phrase!r}")
    return 0


if __name__ == "__main__":
    # Mode 1: extract   python extract_pdf_emphasis.py <pdf> <out.json>
    # Mode 2: add custom  python extract_pdf_emphasis.py --add <sidecar.json> <phrase>...
    if len(sys.argv) >= 2 and sys.argv[1] == "--add":
        if len(sys.argv) < 4:
            print(
                "Usage: extract_pdf_emphasis.py --add <sidecar.json> "
                "<phrase> [<phrase> ...]",
                file=sys.stderr,
            )
            sys.exit(2)
        sidecar = Path(sys.argv[2]).resolve()
        new_phrases = sys.argv[3:]
        add_custom_phrases(sidecar, new_phrases)
        print(f"OK: added {len(new_phrases)} phrase(s) to {sidecar}")
        sys.exit(0)
    sys.exit(main())
