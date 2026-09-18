"""Stage 4 — OCR: identifier_rules (l/I/O → 1/1/0 in numeric slots).

Default identifier_rules ship in _types.DEFAULT_CONFIG; user can extend via per-book config.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from _types import ChangeRecord, Warning


# OCR-confusable map: l, I, O → 1, 1, 0
_CONFUSABLES = {"l": "1", "I": "1", "O": "0"}


def _identifier_regex(prefix: str, suffix_pattern: str) -> re.Pattern:
    """Build regex matching `<prefix>-?<suffix_pattern>` with OCR-confusable chars in slots."""
    expanded = re.sub(
        r"\[0-9\]",
        r"[0-9lIO]",
        suffix_pattern,
    )
    # Allow optional `-` between prefix and first suffix char (e.g. "JGJ-102")
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(prefix)}-?({expanded})(?![A-Za-z0-9])")


def _fix_confusables(match: re.Match, suffix_pattern: str) -> str:
    """Replace confusables in numeric slots of the suffix."""
    prefix = match.group(0).split(match.group(1))[0]
    suffix = match.group(1)
    # Walk suffix with the original pattern to identify numeric positions
    pos = 0
    out = []
    # Crude: any [0-9lIO] slot is numeric → substitute
    for ch in suffix:
        if ch in _CONFUSABLES:
            out.append(_CONFUSABLES[ch])
        elif ch.isdigit():
            out.append(ch)
        else:
            out.append(ch)
    return prefix + "".join(out)


def _make_identifier_rule(prefix: str, suffix_pattern: str, rule_id: str):
    """Closure producing an identifier repair rule."""
    pattern = _identifier_regex(prefix, suffix_pattern)

    def rule_fn(text: str, ctx, cfg: dict) -> Tuple[str, Optional[ChangeRecord]]:
        original = text
        new_text = pattern.sub(lambda m: _fix_confusables(m, suffix_pattern), text)
        if new_text == original:
            return original, None
        return new_text, ChangeRecord(
            rule_id=rule_id,
            page=ctx.page_idx,
            before=original[:120],
            after=new_text[:120],
            confidence="high",
        )

    return rule_fn


# --- Build default rules from config -------------------------------------


def _build_rules(cfg: dict) -> list:
    from _types import DEFAULT_CONFIG
    rules = []
    identifier_rules = cfg.get("identifier_rules")
    if not identifier_rules:
        identifier_rules = DEFAULT_CONFIG["identifier_rules"]
    for entry in identifier_rules:
        rule_id = entry.get("id", f"ocr.identifier.{entry.get('prefix', 'unknown').lower().replace('/', '')}")
        prefix = entry["prefix"]
        suffix = entry["suffix_pattern"]
        rules.append({
            "id": rule_id,
            "fn": _make_identifier_rule(prefix, suffix, rule_id),
            "scope": "prose",
            "confidence": "high",
        })
    return rules


def _RULES(cfg: dict) -> list:
    return _build_rules(cfg)


def apply(text: str, ctx, cfg: dict) -> Tuple[str, list]:
    """Iterate identifier rules; each may modify text or append a ChangeRecord."""
    import traceback
    changes: list = []
    for rule in _RULES(cfg):
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