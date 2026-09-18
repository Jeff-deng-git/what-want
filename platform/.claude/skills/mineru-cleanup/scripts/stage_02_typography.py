"""Stage 2 — Typography: blank_lines, number_gap, cjk_gap.

Each rule is registered in RULES. Order: blank_lines → number_gap → cjk_gap.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from _types import ChangeRecord, Warning, is_cjk


# --- Rule: blank_lines ---------------------------------------------------


def blank_lines_rule(text: str, ctx, cfg: dict) -> Tuple[str, Optional[ChangeRecord]]:
    """3+ blank lines → 2."""
    # Split, count consecutive blank lines, collapse runs of 3+ to 2
    lines = text.split("\n")
    out = []
    blank_run = 0
    changed = False
    for line in lines:
        if line.strip() == "":
            blank_run += 1
        else:
            if blank_run > 2:
                out.extend([""] * 2)
                changed = True
            elif blank_run > 0:
                out.extend([""] * blank_run)
            blank_run = 0
            out.append(line)
    # Tail
    if blank_run > 2:
        out.extend([""] * 2)
        changed = True
    elif blank_run > 0:
        out.extend([""] * blank_run)

    if not changed:
        return text, None
    new_text = "\n".join(out)
    return new_text, ChangeRecord(
        rule_id="typography.spacing.blank_lines",
        page=ctx.page_idx,
        before=text,
        after=new_text,
        confidence="high",
    )


# --- Rule: number_gap ----------------------------------------------------


# Patterns where spaces inside should be removed:
# (pattern, replacement) — replacement must preserve original punctuation
# Note: identifier slots use [0-9lIO] to accept OCR confusables (so number_gap
# strips the space and stage 4 ocr.identifier.* fixes the confusable letter)
_NUMBER_GAP_PATTERNS = [
    (re.compile(r"(\d)\.\s+(\d)"), r"\1.\2"),  # decimal: 12. 3 → 12.3
    (re.compile(r"(\d+)\.\s+(\d+)\b"), r"\1.\2"),  # chapter number: 5. 2 → 5.2
    (re.compile(r"([A-Z][A-Z0-9/]+)-\s+([0-9lIO])"), r"\1-\2"),  # standard: JGJ- lO2 → JGJ-lO2
    (re.compile(r"([A-Z][A-Z0-9/]+)-\s+([0-9lIO]{2}-[0-9lIO])"), r"\1-\2"),  # DGJ- O8-l03
]


def number_gap_rule(text: str, ctx, cfg: dict) -> Tuple[str, Optional[ChangeRecord]]:
    """Remove spaces inside decimal / chapter-number / identifier tokens."""
    original = text
    for pattern, replacement in _NUMBER_GAP_PATTERNS:
        text = pattern.sub(replacement, text)
    if text == original:
        return original, None
    return text, ChangeRecord(
        rule_id="typography.spacing.number_gap",
        page=ctx.page_idx,
        before=original[:120],
        after=text[:120],
        confidence="high",
    )


# --- Rule: cjk_gap (multi-signal heuristic) ------------------------------


# Negative signal patterns: skip lines matching these entirely
_POETRY_LINE_RE = re.compile(r"^[一-鿿㐀-䶿\s　]+$")  # only Han chars + spaces (no punctuation, no ASCII letters/digits)
_TABLE_LINE_RE = re.compile(r"^\s*\|")
_HEADING_RE = re.compile(r"^#+\s")
_LIST_RE = re.compile(r"^\s*([-*]|\d+\.)\s")
_BLOCKQUOTE_RE = re.compile(r"^>\s")

# Candidate pattern: Han + ASCII space + Han
_CANDIDATE_RE = re.compile(r"([一-鿿㐀-䶿])([  ]+)([一-鿿㐀-䶿])")


def _is_negative_line(line: str) -> bool:
    """True if line should be excluded from CJK gap detection."""
    if not _CANDIDATE_RE.search(line):
        return False
    # Strip out sentinels for negative-signal check
    sentinel_stripped = re.sub(r"<<PROTECTED_\d+>>", "", line)
    if _POETRY_LINE_RE.match(sentinel_stripped):
        return True
    if _TABLE_LINE_RE.match(sentinel_stripped):
        return True
    # NOTE: HEADING is NOT a negative signal as of 2026-07-30.
    # Page-density signal (≥3 candidates on the page) provides confidence that
    # even chapter-title gaps are likely OCR noise, not design choice.
    # Original 八木仁平 PDF has 0 "自 己"; MD has 69; removing the HEADING
    # negative recovers 2 missed TOC/heading gaps.
    if _LIST_RE.match(sentinel_stripped):
        return True
    if _BLOCKQUOTE_RE.match(sentinel_stripped):
        return True
    # All-candidates-use-U+3000 (full-width space) — likely intentional
    if all("　" in m.group(0) for m in _CANDIDATE_RE.finditer(line)):
        return True
    return False


def _count_candidates(line: str) -> int:
    """Count Han-space-Han gaps in line (handles overlapping gaps like '自 己 是')."""
    count = 0
    sentinel_stripped = re.sub(r"<<PROTECTED_\d+>>", "", line)
    for i in range(len(sentinel_stripped) - 2):
        if is_cjk(sentinel_stripped[i]) and sentinel_stripped[i + 1] == " " and is_cjk(sentinel_stripped[i + 2]):
            count += 1
    return count


def _strip_spaces(line: str) -> str:
    """Iteratively remove ASCII spaces between Han chars (handles adjacent gaps like '自 己 是')."""
    prev = None
    while prev != line:
        prev = line
        line = _CANDIDATE_RE.sub(lambda m: m.group(1) + m.group(3), line)
    return line


def cjk_gap_rule(text: str, ctx, cfg: dict) -> Tuple[str, Optional[ChangeRecord]]:
    """Multi-signal CJK gap deletion.

    Branches (by cjk_gap config):
    - "off" — rule disabled entirely
    - "conservative" (default) — Branch A only:
        - Per-line density: ≥2 candidates in a single line
        - Per-page density: ≥3 candidates across all lines on the page
          (catches systematic OCR noise like 八木仁平's 69 "自 己" instances
          that the line-only signal misses)
    - "aggressive" — Branch A + Branch B (sidecar-anchored single); Branch B
      requires strict sidecar evidence (fewer spaces than line at same span)
    - Below thresholds, candidates silently stay in MD (not logged to needs_review
      for v1; deferred)
    """
    cjk_gap_mode = cfg.get("cjk_gap", "conservative")
    if cjk_gap_mode == "off":
        return text, None

    lines = text.split("\n")

    # Page-level signal: total candidates on the page (across non-negative lines)
    page_candidates_total = sum(
        _count_candidates(ln) for ln in lines if not _is_negative_line(ln)
    )
    page_density_mode = page_candidates_total >= 3

    new_lines = []
    any_change = False

    for line in lines:
        if _is_negative_line(line):
            new_lines.append(line)
            continue
        n = _count_candidates(line)
        if n == 0:
            new_lines.append(line)
            continue

        should_fix = False
        if n >= 2:
            # Branch A line-density: ≥2 candidates in same line
            should_fix = True
        elif n >= 1 and page_density_mode:
            # Branch A page-density: ≥3 candidates on page → fix all singles
            should_fix = True
        elif n == 1 and cjk_gap_mode == "aggressive":
            # Branch B: sidecar-anchored single — STRICT evidence
            sidecar_blocks = ctx.blocks if hasattr(ctx, "blocks") else None
            if sidecar_blocks:
                stripped_line = _strip_spaces(line)
                for b in sidecar_blocks:
                    btext = b.text or ""
                    if (
                        stripped_line.replace(" ", "") == btext.replace(" ", "")
                        and btext.count(" ") < line.count(" ")
                    ):
                        should_fix = True
                        break

        if should_fix:
            new_line = _strip_spaces(line)
            new_lines.append(new_line)
            any_change = True
        else:
            new_lines.append(line)

    if not any_change:
        return text, None
    new_text = "\n".join(new_lines)
    # Store full before/after in ChangeRecord; serialization to JSON truncates
    return new_text, ChangeRecord(
        rule_id="typography.spacing.cjk_gap",
        page=ctx.page_idx,
        before=text,
        after=new_text,
        confidence="medium",
        sidecar_evidence="branch_a",
    )


# --- RULES registry ------------------------------------------------------


RULES = [
    {"id": "typography.spacing.blank_lines", "fn": blank_lines_rule, "scope": "global", "confidence": "high"},
    {"id": "typography.spacing.number_gap", "fn": number_gap_rule, "scope": "prose", "confidence": "high"},
    {"id": "typography.spacing.cjk_gap", "fn": cjk_gap_rule, "scope": "prose", "confidence": "medium"},
]


def apply(text: str, ctx, cfg: dict) -> Tuple[str, list]:
    """Iterate RULES in fixed order; each rule may modify text or append a ChangeRecord."""
    import traceback
    changes: list = []
    for rule in RULES:
        if rule["id"] in cfg.get("disabled_rules", []):
            continue
        try:
            new_text, change = rule["fn"](text, ctx, cfg)
            if change is not None:
                changes.append(change)
            text = new_text
        except Exception as e:
            ctx.warnings.append(Warning(
                rule_id=rule["id"],
                error_type=type(e).__name__,
                error_message_first_line=str(e).splitlines()[0] if str(e) else "",
                trace=traceback.format_exc() if cfg.get("_verbose") else None,
            ))
    return text, changes