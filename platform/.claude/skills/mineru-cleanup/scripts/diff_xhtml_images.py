"""Generate a diff report comparing XHTML image inventory vs our PDF-extracted images.

Strategy:
- XHTML side: scan <img> tags, group by chapter (file name) + label if nearby
- Our MD side: scan ![](path) followed by figure label
- Match by figure label
- Compare image dimensions (XHTML usually has the full figure, PDF may have cropped)
- Output: xhtml-image-diff.md with status (✓ size match / ⚠ partial candidate / ? unknown)

Usage:
  python diff_xhtml_images.py <xhtml_dir> <our_workdir>
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False


_IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"')
_MD_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_LABEL_RE = re.compile(r"(图|表)\s*(\d+)\s*[-–]\s*(\d+)")


def scan_xhtml(xhtml_dir: Path) -> dict:
    """Return {label_str: [(chapter, img_path, img_size_or_None), ...]}"""
    out = defaultdict(list)
    for f in sorted(xhtml_dir.glob("*.xhtml")):
        text = f.read_text(encoding="utf-8")
        chapter = f.stem
        for m in _IMG_RE.finditer(text):
            img_ref = m.group(1)
            # Get surrounding context (200 chars after) to find label
            ctx = text[m.end():m.end() + 300]
            label_m = _LABEL_RE.search(ctx)
            label = f"{label_m.group(1)}{label_m.group(2)}-{label_m.group(3)}" if label_m else None
            out[label].append((chapter, img_ref, _get_size(img_ref, xhtml_dir)))
    return out


def scan_our_md(workdir: Path) -> dict:
    """Return {label_str: [(md_file, img_ref, size_or_None), ...]}"""
    out = defaultdict(list)
    for f in workdir.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        for m in _MD_IMG_RE.finditer(text):
            img_ref = m.group(1)
            # Get label after image
            ctx = text[m.end():m.end() + 200]
            label_m = _LABEL_RE.search(ctx)
            label = f"{label_m.group(1)}{label_m.group(2)}-{label_m.group(3)}" if label_m else None
            if label:
                # local file path
                local_path = workdir / img_ref
                size = _get_size(str(local_path), None)
                out[label].append((f.name, img_ref, size))
    return out


def _get_size(path: str, base: Path | None) -> tuple | None:
    """Return (width, height) or None. Tries local file; for URLs, derives filename."""
    if not HAVE_PIL:
        return None
    try:
        # For URL like https://.../UUID.jpg, extract UUID.jpg
        p = Path(path)
        if not p.is_absolute() and base:
            p = base / p
        if not p.exists() and "/" in path:
            fname = path.split("/")[-1]
            p = base / fname if base else Path(fname)
            if not p.exists():
                # EPUB layout: XHTML/Images/UUID.jpg
                p = base / "Images" / fname if base else Path(fname)
        if p.exists():
            with Image.open(p) as im:
                return im.size
    except Exception:
        pass
    return None


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python diff_xhtml_images.py <xhtml_dir> <our_workdir>", file=sys.stderr)
        return 2
    xhtml_dir = Path(sys.argv[1]).resolve()
    workdir = Path(sys.argv[2]).resolve()

    xh = scan_xhtml(xhtml_dir)
    md = scan_our_md(workdir)

    all_labels = sorted(l for l in (set(xh) | set(md)) if l)
    lines = [
        "# XHTML Image Diff Report",
        "",
        f"- XHTML source: `{xhtml_dir}`",
        f"- Our workdir:   `{workdir}`",
        f"- XHTML images by label:  **{len(xh)}**",
        f"- Our MD images by label: **{len(md)}**",
        "",
        "| Figure | XHTML chapter | Our MD file | XHTML size | Our size | Status |",
        "|---|---|---|---|---|---|",
    ]
    only_xh, only_md, partial, match = [], [], [], []
    for label in all_labels:
        if not label:
            continue
        xh_entries = xh.get(label, [])
        md_entries = md.get(label, [])
        xh_chap = xh_entries[0][0] if xh_entries else "—"
        md_file = md_entries[0][0] if md_entries else "—"
        xh_size = xh_entries[0][2] if xh_entries else None
        md_size = md_entries[0][2] if md_entries else None
        if xh_size and md_size:
            ratio = (xh_size[0] * xh_size[1]) / max(1, md_size[0] * md_size[1])
            if ratio > 1.2:
                status = f"⚠ XHTML {ratio:.1f}× bigger (partial?)"
                partial.append((label, xh_chap, md_file, xh_size, md_size, ratio))
            else:
                status = "✓ size match"
                match.append(label)
        elif xh_entries and not md_entries:
            status = "? only in XHTML"
            only_xh.append(label)
        elif md_entries and not xh_entries:
            status = "? only in our MD"
            only_md.append(label)
        else:
            status = "?"
        xh_s = f"{xh_size[0]}×{xh_size[1]}" if xh_size else "?"
        md_s = f"{md_size[0]}×{md_size[1]}" if md_size else "?"
        lines.append(f"| {label} | {xh_chap} | {md_file} | {xh_s} | {md_s} | {status} |")

    lines.extend([
        "",
        f"## Summary",
        f"- ✓ size match: **{len(match)}**",
        f"- ⚠ XHTML bigger (partial candidates): **{len(partial)}**",
        f"- ? only in XHTML: **{len(only_xh)}**",
        f"- ? only in our MD: **{len(only_md)}**",
        "",
        "## Partial candidates (XHTML bigger — likely missing PDF content)",
    ])
    for label, xh_chap, md_file, xh_size, md_size, ratio in partial:
        lines.append(f"- **{label}** — XHTML {xh_size[0]}×{xh_size[1]} vs PDF {md_size[0]}×{md_size[1]} ({ratio:.1f}×). "
                     f"Look at XHTML file `{xh_chap}` to find full image, copy to `images/` dir, update MD ref.")
    out = workdir / "xhtml-image-diff.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: report written to {out}")
    print(f"  ✓ {len(match)}  ⚠ {len(partial)}  ? {len(only_xh) + len(only_md)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
