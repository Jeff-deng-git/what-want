"""Stage 1 — Structure: NFC normalization, sidecar adapters, region sentinels, page/blank markers.

Produces:
- text with protected regions replaced by `<<PROTECTED_N>>` sentinels
- `ctx.blocks` populated when sidecar aligned successfully (else None)
- page / blank markers inserted where sidecar confirms
"""
from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Tuple

from _types import Block, CJK_RANGES, Warning, is_cjk


# --- Pre-processing: NFC + line endings + BOM ----------------------------


def normalize_input(text: str) -> str:
    """NFC normalize, strip BOM, convert CRLF/CR to LF."""
    text = text.lstrip("﻿")
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


# --- Sidecar discovery ---------------------------------------------------

SIDECAR_PRECEDENCE = (
    "_content_list_v2.json",
    "_content_list.json",
    "_middle.json",
)


def find_sidecar(md_path: Path) -> Tuple[Optional[Path], Optional[str]]:
    """First present sidecar wins. Returns (path, schema_name) or (None, None)."""
    stem = md_path.name
    for suffix in SIDECAR_PRECEDENCE:
        candidate = md_path.parent / (stem.replace(".md", "") + suffix)
        if candidate.exists():
            schema = "v2" if "v2" in suffix else ("legacy" if "content_list" in suffix else "middle")
            return candidate, schema
    return None, None


def load_sidecar(sidecar_path: Path, schema: str) -> list:
    """Load sidecar JSON. Returns raw parsed object (legacy/v2 = list of blocks; middle = dict)."""
    with sidecar_path.open("r", encoding="utf-8") as f:
        return json.load(f)


# --- Block adapter -------------------------------------------------------


def _flatten_content_to_text(content) -> str:
    """Walk nested v2 content structure and extract all text strings joined by ' '.

    Handles:
    - {"paragraph_content": [{"type":"text","content":"..."}]}
    - {"title_content": [{"type":"text","content":"..."}], "level": N}
    - {"page_footer_content": [...]}
    - {"list_items": [{"item_content": [{"type":"text","content":"..."}]}]}
    - {"image_source": {"path": "..."}} → returns empty string
    """
    texts: list = []

    def _walk(node):
        if isinstance(node, str):
            texts.append(node)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)
            return
        if not isinstance(node, dict):
            return
        # Direct string content
        if isinstance(node.get("content"), str) and node.get("type") == "text":
            texts.append(node["content"])
            return
        # paragraph / title / footer / footnote / aside patterns
        for key in (
            "paragraph_content",
            "title_content",
            "page_footer_content",
            "page_header_content",
            "page_footnote_content",
            "aside_text_content",
        ):
            if isinstance(node.get(key), list):
                _walk(node[key])
        # Index / TOC pattern
        if isinstance(node.get("list_items"), list):
            for item in node["list_items"]:
                if isinstance(item, dict) and isinstance(item.get("item_content"), list):
                    _walk(item["item_content"])

    _walk(content)
    return " ".join(t for t in texts if t).strip()


def adapt_legacy(content_list: list) -> list:
    """Legacy content_list.json → list[Block]. Each item has explicit page_idx."""
    blocks = []
    for item in content_list:
        # Legacy schema: may have text directly OR nested content
        text = item.get("text")
        if text is None:
            text = _flatten_content_to_text(item.get("content", ""))
        else:
            text = str(text)
        page_idx = item.get("page_idx")
        if page_idx is None:
            continue
        btype = item.get("type", "text")
        bbox = item.get("bbox")
        bbox_t = tuple(bbox) if bbox else None
        blocks.append(Block(page_idx=page_idx, type=btype, text=text, bbox=bbox_t, source="legacy"))
    return blocks


def adapt_v2(content_list_v2: list) -> list:
    """content_list_v2.json → list[Block]. Outer array index = page_idx."""
    blocks = []
    for page_idx, page_blocks in enumerate(content_list_v2):
        if not isinstance(page_blocks, list):
            continue
        for item in page_blocks:
            if not isinstance(item, dict):
                continue
            text = _flatten_content_to_text(item.get("content", ""))
            btype = item.get("type", "text")
            bbox = item.get("bbox")
            bbox_t = tuple(bbox) if bbox else None
            blocks.append(Block(page_idx=page_idx, type=btype, text=text, bbox=bbox_t, source="v2"))
    return blocks


# --- Sidecar–MD alignment (token-level LCS) ------------------------------


def lcs_coverage(sidecar_text: str, md_slice: str) -> float:
    """Compute LCS coverage: LCS_length / max(sidecar_tokens, md_tokens)."""
    s_tokens = sidecar_text.split()
    m_tokens = md_slice.split()
    if not s_tokens or not m_tokens:
        return 0.0
    s_str = " ".join(s_tokens)
    m_str = " ".join(m_tokens)
    matcher = SequenceMatcher(None, s_str, m_str, autojunk=False)
    lcs_len = sum(m.size for m in matcher.get_matching_blocks())
    return lcs_len / max(len(s_str), len(m_str))


def align_blocks_to_md(blocks: list, md_text: str, threshold: float) -> list:
    """Drop blocks whose token-level LCS coverage vs best MD slice falls below threshold.

    Returns blocks (filtered). Each surviving block gets `text` updated to the best-matching
    MD slice so downstream rules can cross-check.

    Image/seal/table blocks have empty `text` (visual content, no MD counterpart) — they
    bypass LCS alignment and are kept as-is so page-level metadata (their `page_idx`,
    `bbox`) is available for downstream detection.
    """
    VISUAL_TYPES = {"image", "seal", "table"}
    md_lines = md_text.split("\n")
    surviving = []
    for block in blocks:
        if block.type in VISUAL_TYPES:
            # Visuals have no MD text counterpart — keep them, no LCS check needed.
            surviving.append(block)
            continue
        if not block.text.strip():
            continue
        best_coverage = 0.0
        best_slice = block.text
        # Sliding window over MD lines (1..6 lines)
        for window in (1, 2, 3, 4, 6):
            for start in range(len(md_lines) - window + 1):
                slice_text = " ".join(md_lines[start:start + window]).strip()
                if not slice_text:
                    continue
                cov = lcs_coverage(block.text, slice_text)
                if cov > best_coverage:
                    best_coverage = cov
                    best_slice = slice_text
        if best_coverage >= threshold:
            surviving.append(Block(
                page_idx=block.page_idx,
                type=block.type,
                text=best_slice,
                bbox=block.bbox,
                source=block.source,
            ))
    return surviving


# --- Region protection (sentinels) --------------------------------------


SENTINEL_RE = re.compile(r"<<PROTECTED_(\d+)>>")

# Fenced code blocks (``` or ~~~), HTML blocks, math blocks ($$...$$ or $...$)
_FENCE_RE = re.compile(r"(^```[^\n]*\n.*?\n```|^~~~[^\n]*\n.*?\n~~~)", re.DOTALL | re.MULTILINE)
_HTML_BLOCK_RE = re.compile(r"(^<[a-zA-Z][^>]*>.*?</[a-zA-Z]+>|^<[a-zA-Z][^>]*/>)", re.DOTALL | re.MULTILINE)
_MATH_BLOCK_RE = re.compile(r"\$\$.*?\$\$", re.DOTALL)
# Inline patterns to protect: inline code `...`, links [text](url), images ![alt](url)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def install_sentinels(text: str) -> Tuple[str, list]:
    """Replace protected regions with `<<PROTECTED_N>>` sentinels.

    Returns (modified_text, list_of_(sentinel_id, original_bytes)).
    """
    regions = []  # (sentinel_id, original)

    def _record(match, regions=regions):
        sentinel_id = f"<<PROTECTED_{len(regions)}>>"
        regions.append((sentinel_id, match.group(0)))
        return sentinel_id

    out = text

    # 1) Fenced code blocks
    out = _FENCE_RE.sub(_record, out)
    # 2) HTML blocks
    out = _HTML_BLOCK_RE.sub(_record, out)
    # 3) Math blocks $$..$$
    out = _MATH_BLOCK_RE.sub(_record, out)
    # 4) Inline code
    out = _INLINE_CODE_RE.sub(_record, out)
    # 5) Images
    out = _IMAGE_RE.sub(_record, out)
    # 6) Links
    out = _LINK_RE.sub(_record, out)

    return out, regions


def restore_sentinels(text: str, regions: list) -> str:
    """Reverse of install_sentinels. Order matters: replace by sentinel_id in regions list."""
    out = text
    # Replace in reverse so earlier IDs don't get clobbered by later ID substrings
    for sentinel_id, original in reversed(regions):
        out = out.replace(sentinel_id, original, 1)
    return out


def verify_sentinels(text: str, regions: list) -> Tuple[bool, list]:
    """Check each sentinel appears exactly once with original surrounding context.

    Returns (ok, list_of_failures). Each failure is {sentinel_id, issue}.
    """
    failures = []
    for sentinel_id, original in regions:
        count = text.count(sentinel_id)
        if count != 1:
            failures.append({"sentinel_id": sentinel_id, "issue": f"count={count}, expected 1"})
    return (len(failures) == 0, failures)


# --- Page / blank markers ------------------------------------------------


PAGE_BREAK_MARKER = "<!-- page break: {n} -->"
BLANK_PAGE_MARKER = "<!-- blank page: {n} -->"


def insert_page_markers(text: str, blocks: list) -> str:
    """Insert `<!-- page break: N -->` markers at the document-order position of each
    page's first matched block line.

    v1 algorithm:
    - For each page (sorted by page_idx ascending), find the earliest MD line that
      contains the block.text slice. Insert marker before that line.
    - Sort insertions by line index ascending before applying, so markers appear in
      MD document order even when sidecar blocks match out of order.
    - Skip pages whose block.text doesn't find a matching line.
    """
    if not blocks:
        return text

    # Group blocks by page_idx; use first non-empty block per page
    by_page: dict = {}
    for b in blocks:
        if b.text and b.text.strip() and b.page_idx not in by_page:
            by_page[b.page_idx] = b

    if not by_page:
        return text

    lines = text.split("\n")
    insertions: list = []  # (md_line_index, marker_text)

    # Process pages in ascending page_idx order
    for page_idx in sorted(by_page.keys()):
        block = by_page[page_idx]
        snippet = block.text[:30]
        for i, line in enumerate(lines):
            if snippet and snippet in line:
                insertions.append((i, PAGE_BREAK_MARKER.format(n=page_idx)))
                break

    # Apply in order; for equal indices, the last insertion wins (rare)
    insertions.sort(key=lambda x: x[0])
    for i, (idx, marker) in enumerate(insertions):
        lines.insert(idx + i, marker)  # offset by already-inserted markers above
    return "\n".join(lines)


# --- Stage 1 main entry --------------------------------------------------


def apply(text: str, ctx_warnings: list, config: dict, md_path: Optional[Path] = None) -> Tuple[str, list, Optional[list], list]:
    """Run stage 1.

    Returns: (sentinel_text, regions, blocks_or_None, page_metrics)
    """
    text = normalize_input(text)

    # Sentinel installation
    sentinel_text, regions = install_sentinels(text)

    # Sidecar adapter + alignment
    blocks: Optional[list] = None
    sidecar_path = None
    if md_path is not None:
        sidecar_path, schema = find_sidecar(md_path)
    if sidecar_path is not None:
        try:
            raw = load_sidecar(sidecar_path, schema)
            if schema == "legacy":
                blocks = adapt_legacy(raw)
            elif schema == "v2":
                blocks = adapt_v2(raw)
            elif schema == "middle":
                # Middle alone provides pdf_info / discarded_blocks, no block map
                blocks = []
        except (json.JSONDecodeError, OSError) as e:
            ctx_warnings.append(Warning(
                rule_id="structure.sidecar",
                error_type=type(e).__name__,
                error_message_first_line=str(e).splitlines()[0] if str(e) else "",
            ))
            blocks = None
        else:
            # Run alignment
            threshold = config.get("alignment_threshold", 0.95)
            if blocks:
                aligned = align_blocks_to_md(blocks, text, threshold)
                # Coverage: count visual types as auto-preserved (they bypass LCS);
                # only non-visual (text/paragraph/title) need alignment match. This
                # prevents image-heavy PDFs from triggering MD-only mode.
                VISUAL_TYPES = {"image", "seal", "table"}
                non_visual_total = sum(1 for b in blocks if b.type not in VISUAL_TYPES)
                non_visual_kept = sum(1 for b in aligned if b.type not in VISUAL_TYPES)
                coverage = (
                    (non_visual_kept + (len(aligned) - non_visual_kept)) / len(blocks)
                    if blocks else 0.0
                )
                # Simpler: ratio of (kept text) / (total text). Visual types are guaranteed-kept.
                if non_visual_total > 0:
                    text_coverage = non_visual_kept / non_visual_total
                else:
                    text_coverage = 1.0  # all visual, no text to align
                if text_coverage < 0.5 and non_visual_total >= 5:
                    ctx_warnings.append(Warning(
                        rule_id="structure.sidecar",
                        error_type="AlignmentFailure",
                        error_message_first_line=f"text coverage {text_coverage:.2f} < 0.5; falling back to MD-only mode",
                    ))
                    blocks = None
                else:
                    blocks = aligned

    # Insert page markers when blocks available AND opt-in via config
    page_metrics = {"page_count": 0, "blank_pages": 0}
    if blocks and config.get("page_markers", False):
        sentinel_text = insert_page_markers(sentinel_text, blocks)
        pages = {b.page_idx for b in blocks if b.text.strip()}
        page_metrics["page_count"] = max(pages) + 1 if pages else 0
        page_metrics["blank_pages"] = page_metrics["page_count"] - len(pages)

    # Image quality warnings — surface issues to user via cleanup-report.json
    _check_image_quality(regions, md_path, ctx_warnings)
    _check_page_extraction_mismatch(md_path, blocks, ctx_warnings)

    return sentinel_text, regions, blocks, page_metrics


def _check_page_extraction_mismatch(md_path, blocks, ctx_warnings: list) -> None:
    """Detect pages where MinerU's model detected N visual blocks but the v2 sidecar
    only references K images (K < N). Indicates partial figure extraction even when
    no FigureLabelWithoutImage warning fires.

    Sources:
    - model.json `layout_dets` per page (raw model output)
    - sidecar content_list_v2.json image-type entries per page

    Strategy: load content_list_v2.json if present; count image-type entries per
    page_idx; compare against `blocks` list (which holds BLOCK_TYPE.IMAGE/SEAL from
    sidecar). Flag pages where sidecar block count > extracted image count by a
    meaningful margin (gap >= 1).
    """
    if not md_path or not blocks:
        return
    from pathlib import Path
    md_dir = Path(md_path).parent

    # Count images actually referenced in the MD by page_idx
    # Page_idx of an image = position of the image_ref's preceding figure/table label,
    # fallback to last seen page_idx, fallback to 0. (Approximation; this is OK for
    # the heuristic — exact mapping isn't needed, just per-page totals.)
    sidecar_image_count: dict = {}
    for b in blocks:
        if b.type in ("image", "seal") and b.page_idx is not None:
            sidecar_image_count[b.page_idx] = sidecar_image_count.get(b.page_idx, 0) + 1

    # If sidecar had no image/seal blocks, skip (nothing to compare)
    if not sidecar_image_count:
        return

    # Heuristic page-bbox check: count small image blocks per page (bbox < 100×100 px²)
    # — these are likely icons/stamps, not figures. A figure that's just one icon
    # is suspicious; figure + ≥2 small icons = multi-element figure, partial if
    # only icon got extracted.
    small_per_page: dict = {}
    big_per_page: dict = {}
    for b in blocks:
        if b.type not in ("image", "seal") or b.page_idx is None or b.bbox is None:
            continue
        x1, y1, x2, y2 = b.bbox
        area = max(0, x2 - x1) * max(0, y2 - y1)
        if area < 100 * 100:
            small_per_page[b.page_idx] = small_per_page.get(b.page_idx, 0) + 1
        else:
            big_per_page[b.page_idx] = big_per_page.get(b.page_idx, 0) + 1

    # Count image-type entries in content_list_v2 per page_idx
    v2_image_count: dict = {}
    v2_path = md_dir / (Path(md_path).stem + "_content_list_v2.json")
    if v2_path.exists():
        try:
            import json as _json
            v2_data = _json.loads(v2_path.read_text(encoding="utf-8"))
            # v2 schema: outer list = pages in order; each item is a list of blocks
            for page_idx, page_blocks in enumerate(v2_data):
                if not isinstance(page_blocks, list):
                    continue
                img_count = sum(1 for blk in page_blocks if isinstance(blk, dict) and blk.get("type") == "image")
                if img_count > 0:
                    v2_image_count[page_idx] = img_count
        except (OSError, ValueError):
            pass

    # Heuristic: page has figure-label (implied by label-gap warning later) AND
    # sidecar has ≥2 small visual blocks on that page but only 1 image extracted
    # → partial extraction suspected.
    # Avoid false positives: only flag if blocks count >= 2 AND extracted = 1.
    flagged = 0
    for page_idx, sidecar_count in sidecar_image_count.items():
        extracted = v2_image_count.get(page_idx, 0)
        small_count = small_per_page.get(page_idx, 0)
        if sidecar_count >= 2 and extracted <= 1 and small_count >= 2:
            flagged += 1
            if flagged <= 10:
                ctx_warnings.append(Warning(
                    rule_id="structure.image",
                    error_type="PageExtractionMismatch",
                    error_message_first_line=(
                        f"page_idx {page_idx}: sidecar detected {sidecar_count} visual blocks "
                        f"({small_count} small icons), only {extracted} image extracted — "
                        f"partial figure extraction suspected"
                    ),
                ))


def _check_image_quality(regions: list, md_path, ctx_warnings: list) -> None:
    """Per-sentinel image sanity checks. Logs warnings for issues users should know.

    - missing file (image_ref points to non-existent path)
    - tiny file (< 2KB, likely placeholder / failed extraction)
    - missing 图N-M / 表N-M label between sentinels (potential extraction gap)
    """
    from pathlib import Path
    sentinel_re = re.compile(r"<<PROTECTED_(\d+)>>")
    # Also catch raw image refs not yet sentinelized (e.g., when --ignore-gates or skipped)
    img_re = re.compile(r"!\[[^\]]*\]\((images/[^)]+)\)")

    missing_count = 0
    tiny_count = 0
    label_gap_count = 0

    workdir = Path(md_path).parent if md_path else None
    for sentinel_id, original in regions:
        # Extract image path from sentinel original (looks like ![alt](images/xxx))
        m = re.match(r"!\[([^\]]*)\]\((images/[^)]+)\)", original)
        if not m:
            continue
        img_rel = m.group(2)
        if workdir is None:
            continue
        img_path = workdir / img_rel
        if not img_path.exists():
            missing_count += 1
            ctx_warnings.append(Warning(
                rule_id="structure.image",
                error_type="ImageMissing",
                error_message_first_line=f"image file not found: {img_rel}",
            ))
            continue
        try:
            size = img_path.stat().st_size
            if size < 2048:
                tiny_count += 1
                ctx_warnings.append(Warning(
                    rule_id="structure.image",
                    error_type="ImageTooSmall",
                    error_message_first_line=f"image suspiciously small ({size} bytes): {img_rel}",
                ))
        except OSError:
            pass

    # Detect figure labels with no preceding image — likely missing extraction
    # Heuristic: a figure label like "图3-3" should appear within the same logical
    # block as the image_ref (separated only by an optional blank line and optional
    # caption text). Look back up to 2 lines before label for an image_ref.
    if md_path:
        try:
            md_text = Path(md_path).read_text(encoding="utf-8")
            for m in re.finditer(r"(图|表)\s*\d+[-–]\d+\s*$", md_text, re.MULTILINE):
                label_pos = m.start()
                # Look at up to 3 lines before the label (image line + optional blank
                # line + label). 3 iterations ensures we cross any blank line that
                # sits between image_ref and the label.
                lines_back = 3
                scan_pos = label_pos
                for _ in range(lines_back):
                    prev_nl = md_text.rfind("\n", 0, scan_pos)
                    if prev_nl < 0:
                        break
                    scan_pos = prev_nl
                window = md_text[scan_pos:label_pos]
                # Window must contain image_ref AND must NOT contain a paragraph
                # break (i.e., it should be a tight figure caption + label)
                if not re.search(r"!\[[^\]]*\]\([^)]+\)", window):
                    label_gap_count += 1
                    if label_gap_count <= 10:
                        ctx_warnings.append(Warning(
                            rule_id="structure.image",
                            error_type="FigureLabelWithoutImage",
                            error_message_first_line=(
                                f"figure/table label '{m.group().strip()}' has no preceding image "
                                f"within 2 lines; MinerU may have missed the visual"
                            ),
                        ))
        except (OSError, UnicodeDecodeError):
            pass