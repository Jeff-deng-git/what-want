"""Shared dataclasses for mineru-cleanup.

These types are the public contract between stage modules and rules. Adding
a field to a frozen dataclass forces review of all consumers (a deliberate
friction).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple


# --- Unicode CJK detection ----------------------------------------------

CJK_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs
    (0x3400, 0x4DBF),    # Extension A
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0x2F800, 0x2FA1F),  # CJK Compatibility Ideographs Supplement
)
# Ext B–G (0x20000–0x2EBF0) requires surrogate-pair handling — known gap in v1.


def is_cjk(c: str) -> bool:
    """True iff `c` is a CJK ideograph covered by CJK_RANGES."""
    if not c:
        return False
    cp = ord(c)
    for lo, hi in CJK_RANGES:
        if lo <= cp <= hi:
            return True
    return False


# --- Block model --------------------------------------------------------


@dataclass(frozen=True)
class Block:
    """Unified block model from sidecar adapter. `bbox` is None when not available."""
    page_idx: int
    type: str  # text | title | image | table | header | footer | page_number | page_footnote | aside_text
    text: str
    bbox: Optional[Tuple[float, float, float, float]] = None
    source: str = ""  # "legacy" | "v2" | "middle"


# --- Warning ------------------------------------------------------------


@dataclass
class Warning:
    rule_id: str
    error_type: str
    error_message_first_line: str
    trace: Optional[str] = None  # populated only with --verbose


# --- Context -------------------------------------------------------------
#
# Context is intentionally NOT frozen: `warnings`, `protected_regions`, and
# `blocks` are mutated in place by stage apply(). Block is frozen because
# rules should not mutate the underlying block map.


@dataclass
class Context:
    page_idx: int
    blocks: Optional[list]            # None when sidecar absent or alignment failed
    config: dict                      # per-book config (validated against schema)
    warnings: list                    # list[Warning]; mutated in place by stage apply()
    protected_regions: list           # list[tuple[sentinel_id, original_bytes]]


# --- Change record ------------------------------------------------------


@dataclass
class ChangeRecord:
    rule_id: str
    page: int
    before: str
    after: str
    confidence: str  # "high" | "medium" | "low"
    sidecar_evidence: Optional[str] = None


# --- Default config -----------------------------------------------------


DEFAULT_CONFIG: dict = {
    "callout_labels": ["POINT"],
    "identifier_rules": [
        {"id": "ocr.identifier.jgj", "prefix": "JGJ", "suffix_pattern": r"[0-9]{3}"},
        {"id": "ocr.identifier.dgj", "prefix": "DGJ", "suffix_pattern": r"[0-9]{2}-[0-9]{3}-[0-9]{4}"},
        {"id": "ocr.identifier.gb", "prefix": "GB/T", "suffix_pattern": r"[0-9]+(?:\.[0-9]+)?"},
    ],
    "parentheses": "preserve",
    "disabled_rules": [],
    "cjk_gap": "conservative",
    "alignment_threshold": 0.95,
    "page_markers": False,  # opt-in: see stage_01_structure.insert_page_markers
    "manual_replacements": [],
    "_verbose": False,
}