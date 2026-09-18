"""Stage 3 — Blocks: callout (POINT → blockquote), title split.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from _types import ChangeRecord, Warning


# --- Rule: callout.point --------------------------------------------------


# Match a heading line whose ENTIRE stripped text equals a callout label
_HEADING_LABEL_RE = re.compile(r"^(#+)\s+(\S+)\s*$")


def callout_point_rule(text: str, ctx, cfg: dict) -> Tuple[str, Optional[ChangeRecord]]:
    """`## POINT` (whole-line, no body) → `> **POINT**` blockquote stub.

    Body callout detection (POINT + body lines) is a v1.1 feature; v1 converts
    heading-style callouts only.
    """
    labels = set(cfg.get("callout_labels", ["POINT"]))
    lines = text.split("\n")
    new_lines = []
    any_change = False
    rule_id = None
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _HEADING_LABEL_RE.match(line)
        if m and m.group(2) in labels:
            label = m.group(2)
            rule_id = f"blocks.callout.{label.lower()}"
            new_lines.append(f"> **{label}**")
            new_lines.append(">")
            # Find next non-blank line as body (skip intermediate blanks)
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                body = lines[j].strip()
                new_lines.append(f"> {body}")
                i = j + 1
                any_change = True
                continue
            i += 1
            any_change = True
            continue
        new_lines.append(line)
        i += 1
    if not any_change:
        return text, None
    return "\n".join(new_lines), ChangeRecord(
        rule_id=rule_id or "blocks.callout.point",
        page=ctx.page_idx,
        before=text[:120],
        after="\n".join(new_lines)[:120],
        confidence="high",
    )


# --- Rule: title.split ---------------------------------------------------


# Match a heading line whose text contains TWO valid level numbers, e.g.
# "5.2电梯5.2.1内容"
_NUM_RE = re.compile(r"(\d+(?:\.\d+)+)")
_HEADING_NUM_RE = re.compile(r"^(#+)\s+(.*)$")


def _split_levels(num: str) -> list:
    """Split "5.2.1" → [5, 2, 1]."""
    return [int(x) for x in num.split(".")]


def _valid_split(num1: str, num2: str) -> bool:
    """True iff num2 is a deeper level than num1 (e.g., 5.2.1 deeper than 5.2)."""
    l1 = _split_levels(num1)
    l2 = _split_levels(num2)
    if len(l2) != len(l1) + 1:
        return False
    return l2[:-1] == l1


def title_split_rule(text: str, ctx, cfg: dict) -> Tuple[str, Optional[ChangeRecord]]:
    """Split headings with two valid level numbers concatenated.

    Example: `# 5.2电梯5.2.1内容` →
        `# 5.2 电梯`
        `## 5.2.1 内容`
    Only fires when:
    - Line is a heading (^#+\s)
    - Contains exactly 2 valid level numbers
    - Second is exactly one level deeper than first
    """
    lines = text.split("\n")
    new_lines = []
    any_change = False
    for line in lines:
        m = _HEADING_NUM_RE.match(line)
        if not m:
            new_lines.append(line)
            continue
        hashes, body = m.group(1), m.group(2).strip()
        nums = _NUM_RE.findall(body)
        if len(nums) != 2:
            new_lines.append(line)
            continue
        num1, num2 = nums
        if not _valid_split(num1, num2):
            new_lines.append(line)
            continue
        # Split: text between numbers → first heading's title; text after num2 → second's title
        idx1 = body.find(num1)
        idx2 = body.find(num2, idx1 + len(num1))
        title1 = body[idx1 + len(num1):idx2].strip()
        title2 = body[idx2 + len(num2):].strip()
        if not title1 or not title2:
            new_lines.append(line)
            continue
        new_lines.append(f"{hashes} {num1} {title1}")
        new_lines.append("")  # blank line between split headings (Markdown convention)
        new_lines.append(f"{'#' * (len(hashes) + 1)} {num2} {title2}")
        any_change = True
    if not any_change:
        return text, None
    return "\n".join(new_lines), ChangeRecord(
        rule_id="blocks.title.split",
        page=ctx.page_idx,
        before=text[:160],
        after="\n".join(new_lines)[:160],
        confidence="high",
    )


# --- RULES registry ------------------------------------------------------


RULES = [
    {"id": "blocks.callout.point", "fn": callout_point_rule, "scope": "heading", "confidence": "high"},
    {"id": "blocks.title.split", "fn": title_split_rule, "scope": "heading", "confidence": "high"},
]


def apply(text: str, ctx, cfg: dict) -> Tuple[str, list]:
    """Iterate RULES; collect ChangeRecords."""
    import traceback
    changes: list = []
    for rule in RULES:
        if rule["id"] in cfg.get("disabled_rules", []):
            continue
        # Also skip dynamically-disabled callouts (one rule per label)
        if rule["id"].startswith("blocks.callout."):
            label = rule["id"].rsplit(".", 1)[-1]
            label_upper = label.upper()
            # Always allow point; user can disable via `blocks.callout.<label>` in disabled_rules
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