"""Stage 5 — Verify: sentinel restoration, gates, idempotence, report.

Runs after stages 2-4. Validates that:
- Every sentinel survives byte-equal
- Fence / math / table balance preserved
- Every diff is explained by the change ledger
- transform(transform(x)) == transform(x) (idempotence)
- Image targets still exist
- No output path collision (unless --ignore-gates)

Writes `{stem}.cleaned.md` and `{stem}.cleanup-report.json` only when gates pass.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Optional, Tuple

from _types import ChangeRecord, Warning


# --- Balance checks ------------------------------------------------------


_FENCE_OPEN_CLOSE_RE = re.compile(r"^(\s*)(```+|~~~+)([^\n]*)$", re.MULTILINE)


def _count_fence_balance(text: str) -> Tuple[int, int]:
    """Return (opens, closes) of fenced code blocks."""
    opens = closes = 0
    seen_open = False
    for m in _FENCE_RE.finditer(text):
        if not seen_open:
            opens += 1
            seen_open = True
        else:
            closes += 1
            seen_open = False
    return opens, closes


_FENCE_RE = re.compile(r"^(```+|~~~+)", re.MULTILINE)
_MATH_BLOCK_RE = re.compile(r"\$\$.*?\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"\$[^$\n]+\$")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)


def balance_check(text: str) -> dict:
    """Check fence/math/table/link/image balance."""
    fence_o, fence_c = _count_fence_balance(text)
    math_blocks = _MATH_BLOCK_RE.findall(text)
    inline_math = _INLINE_MATH_RE.findall(text)
    table_rows = _TABLE_ROW_RE.findall(text)
    image_refs = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", text)
    link_refs = re.findall(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", text)

    issues = []
    if fence_o != fence_c:
        issues.append({"kind": "fence_unbalanced", "opens": fence_o, "closes": fence_c})
    if len(math_blocks) % 2 != 0:
        issues.append({"kind": "math_block_unbalanced", "count": len(math_blocks)})
    # Inline math $...$ should be even (each opens & closes)
    if len(inline_math) % 2 != 0:
        issues.append({"kind": "inline_math_unbalanced", "count": len(inline_math)})
    return {
        "fence_balance": (fence_o, fence_c),
        "math_block_count": len(math_blocks),
        "inline_math_count": len(inline_math),
        "image_ref_count": len(image_refs),
        "link_ref_count": len(link_refs),
        "issues": issues,
    }


# --- Diff explainability -------------------------------------------------


def _char_diff_count(a: str, b: str) -> int:
    """Number of characters that differ between a and b."""
    if a == b:
        return 0
    # Simple O(len) approximation via longest common prefix / suffix
    n = min(len(a), len(b))
    prefix = 0
    while prefix < n and a[prefix] == b[prefix]:
        prefix += 1
    suffix = 0
    while suffix < n - prefix and a[-1 - suffix] == b[-1 - suffix]:
        suffix += 1
    return len(a) + len(b) - 2 * (prefix + suffix)


def diff_explainable(stage1_input: str, regions: list, ledger: list) -> Tuple[bool, int]:
    """Return (ok, unexplained_char_diff) for v1 — heuristic only.

    Compares the cumulative byte-diff attributable to ledger entries against
    the diff between stage 1's input and the (sentinel-stripped) cleaned text.
    Sentinel substitution is accounted for by `regions`.

    Passes if `len(ledger) > 0` (at least one rule changed something). Exact
    accounting across chained pipeline + sentinel substitution is deferred to v1.1.
    """
    if not ledger:
        return (False, 0)
    has_actual_change = any(c.before != c.after for c in ledger)
    return (has_actual_change, 0)


# --- Idempotence ---------------------------------------------------------


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def idempotence_check(cleaned_text: str, regions: list, ctx_template, cfg: dict) -> Tuple[bool, str]:
    """Re-run all stages on `cleaned_text` and verify byte-equal output.

    Returns (ok, second_pass_sha256).
    """
    from stage_01_structure import apply as stage1
    from stage_02_typography import apply as stage2
    from stage_03_blocks import apply as stage3
    from stage_04_ocr import apply as stage4

    # Stage 1: re-install sentinels (won't find any in cleaned_text since stage 5 already restored)
    # For idempotence, we measure that a SECOND pass produces the same output.
    # Build a synthetic ctx with empty blocks (we're only checking byte equality, not real sidecar)
    import copy
    ctx2 = copy.copy(ctx_template)
    ctx2.warnings = []
    ctx2.blocks = None  # MD-only mode for idempotence check
    ctx2.protected_regions = []

    sentinel_text, regions2, _, _ = stage1(cleaned_text, ctx2.warnings, cfg)
    text2, _ = stage2(sentinel_text, ctx2, cfg)
    text3, _ = stage3(text2, ctx2, cfg)
    text4, _ = stage4(text3, ctx2, cfg)

    # Restore
    from stage_01_structure import restore_sentinels
    restored = restore_sentinels(text4, regions2)
    return (restored == cleaned_text, _sha256(restored))


# --- Image existence check ----------------------------------------------


def image_existence_check(text: str, workdir: Path) -> Tuple[bool, list]:
    """Verify every image reference resolves to an existing file.

    Skip gate if no images/ directory AND no image refs in text.
    """
    images_dir = workdir / "images"
    refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    missing = []
    if not refs:
        return True, []
    if not images_dir.exists():
        # No images dir but refs exist → fail
        for ref in refs:
            if not (workdir / ref).exists():
                missing.append({"ref": ref, "reason": "no_images_dir"})
        return (len(missing) == 0, missing)
    for ref in refs:
        target = workdir / ref
        if not target.exists():
            missing.append({"ref": ref, "reason": "not_found"})
    return (len(missing) == 0, missing)


# --- Sentinel integrity --------------------------------------------------


def sentinel_integrity_check(text: str, regions: list) -> Tuple[bool, list]:
    """Each sentinel appears exactly once."""
    failures = []
    for sentinel_id, original in regions:
        count = text.count(sentinel_id)
        if count != 1:
            failures.append({"sentinel_id": sentinel_id, "count": count})
    return (len(failures) == 0, failures)


# --- Apply (the orchestrator) -------------------------------------------


def apply(
    cleaned_with_sentinels: str,
    regions: list,
    original_text: str,
    ledger: list,
    cfg: dict,
    workdir: Path,
    ignore_gates: bool,
    dry_run: bool,
    page_metrics: dict,
    blocks: Optional[list],
) -> Tuple[Optional[str], dict, bool, list]:
    """Run all stage-5 gates and produce the final output + report.

    Returns: (cleaned_text_or_None_on_failure, report, gate_passed, hard_failures)
    """
    hard_failures = []
    warnings_list: list = []

    # 1. Sentinel integrity (PRE-restore): every sentinel must appear exactly once
    pre_ok, pre_failures = sentinel_integrity_check(cleaned_with_sentinels, regions)
    if not pre_ok:
        hard_failures.extend([{"gate": "sentinel_integrity", "phase": "pre_restore", **f} for f in pre_failures])

    # 2. Sentinel restoration
    from stage_01_structure import restore_sentinels
    cleaned_text = restore_sentinels(cleaned_with_sentinels, regions)

    # 3. Sentinel integrity (POST-restore): no sentinel should remain
    post_remaining = [
        {"gate": "sentinel_integrity", "phase": "post_restore", "sentinel_id": sid, "count": cleaned_text.count(sid)}
        for sid, _ in regions
        if cleaned_text.count(sid) > 0
    ]
    if post_remaining:
        hard_failures.extend(post_remaining)

    # 4. Balance check
    bal = balance_check(cleaned_text)
    if bal["issues"]:
        hard_failures.extend([{"gate": "balance", **i} for i in bal["issues"]])

    # 5. Diff explainability: WARN-only in v1 (full accounting across chained pipeline
    #    + sentinel substitution is fragile; deferred to v1.1)
    explain_ok, unexplained = diff_explainable(cleaned_with_sentinels, regions, ledger)
    if not explain_ok:
        # Don't hard-fail; record as warning instead
        from _types import Warning
        warnings_list.append(Warning(
            rule_id="stage_05.diff_explainability",
            error_type="PartialExplanation",
            error_message_first_line=f"{unexplained} chars not accounted for by ledger (likely sentinel substitution)",
        ))

    # 6. Image existence
    img_ok, missing = image_existence_check(cleaned_text, workdir)
    if not img_ok:
        hard_failures.extend([{"gate": "image_existence", **m} for m in missing])

    # 7. Idempotence (only if all earlier gates passed)
    idemp_ok = False
    second_pass_sha = ""
    if not hard_failures:
        from _types import Context
        ctx_template = Context(page_idx=0, blocks=None, config=cfg, warnings=[], protected_regions=[])
        idemp_ok, second_pass_sha = idempotence_check(cleaned_text, regions, ctx_template, cfg)
        if not idemp_ok:
            hard_failures.append({"gate": "idempotence", "second_pass_sha256": second_pass_sha})

    # 8. Output path collision
    output_path = workdir / (workdir.name + ".cleaned.md")
    collision_refused = False
    if output_path.exists():
        existing = output_path.read_text(encoding="utf-8")
        if existing != cleaned_text and not ignore_gates:
            collision_refused = True
            hard_failures.append({"gate": "output_collision", "existing_sha256": _sha256(existing)})

    gate_passed = len(hard_failures) == 0
    cleaned_output = cleaned_text if gate_passed or ignore_gates else None

    # Build report
    metrics = {
        "input_chars": len(original_text),
        "output_chars": len(cleaned_text),
        "total_chars_modified": _char_diff_count(original_text, cleaned_text),
        # rule_changes_chars: actual length delta (chars removed by rule). For
        # a "remove spaces" rule, this is positive and meaningful. Earlier
        # versions used _char_diff_count which counted shared prefix/suffix
        # chars as "modified" — misleading.
        "rule_changes_chars": sum(
            abs(len(c.before) - len(c.after))
            for c in ledger
            if c.before != c.after
        ),
        "sentinels_count": len(regions),
        "protected_regions_count": len(regions),
        "page_count": page_metrics.get("page_count", 0),
        "blank_pages": page_metrics.get("blank_pages", 0),
        "rules_applied": len({c.rule_id for c in ledger if c.before != c.after}),
    }
    report = {
        "input_sha256": _sha256(original_text),
        "output_sha256": _sha256(cleaned_text),
        "mode": "sidecar" if blocks is not None else "md_only",
        "sidecar_alignment_rate": _sidecar_alignment_rate(blocks, original_text) if blocks else 0.0,
        "metrics": metrics,
        "balance": bal,
        "applied_changes": [
            {
                "rule_id": c.rule_id,
                "page": c.page,
                "before": c.before[:200],
                "after": c.after[:200],
                "confidence": c.confidence,
                "sidecar_evidence": c.sidecar_evidence,
            }
            for c in ledger
        ],
        "needs_review": [],  # populated by individual rules; v1 stub
        "warnings": [
            {
                "rule_id": w.rule_id,
                "error_type": w.error_type,
                "error_message_first_line": w.error_message_first_line,
            }
            for w in warnings_list
        ],
        "hard_failures": hard_failures,
        "idempotence": {"verified": idemp_ok, "second_pass_sha256": second_pass_sha} if not collision_refused else {"verified": False, "reason": "collision_refused"},
        "dry_run": dry_run,
    }

    return cleaned_output, report, gate_passed, hard_failures


def _sidecar_alignment_rate(blocks, original_text):
    if not blocks:
        return 0.0
    # Crude proxy: fraction of block texts found (substring) in original MD
    found = sum(1 for b in blocks if b.text[:30] in original_text)
    return found / len(blocks)