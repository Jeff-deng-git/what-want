# mineru-cleanup rule catalog

Each rule has: id, scope, before/after examples, confidence, known limits. The
catalog is the prose side of the rule registry in code — every shipped rule
must have an entry here AND a unit test.

## CJK Unicode ranges

`is_cjk(c)` covers:
- U+4E00–U+9FFF (CJK Unified Ideographs)
- U+3400–U+4DBF (Extension A)
- U+F900–U+FAFF (CJK Compatibility Ideographs)
- U+2F800–U+2FA1F (CJK Compatibility Ideographs Supplement)

**Known gap**: Extension B–G (U+20000–U+2EBF0) requires surrogate-pair
handling; not covered in v1. Rare in practice; revisit if precision audit
shows misses.

---

## structure.regions.protect

- **Scope**: global
- **Confidence**: high
- **What it does**: Replaces fenced code blocks, HTML blocks, math blocks,
  inline code, images, and links with `<<PROTECTED_N>>` sentinels. Stage 5
  restores them byte-for-byte.
- **Example**:
  - Before: `Inline code: `use MinerU`` and a [link](https://example.com).`
  - After: `Inline code: <<PROTECTED_0>> and a <<PROTECTED_1>>.`
- **Limits**: Nested fences with mismatched markers (e.g., ``` then ~~~) may
  confuse the protection regex. Stage 5 catches via sentinel integrity gate.

---

## structure.sidecar.{legacy,v2,middle}

- **Scope**: pre-processing
- **Confidence**: high (when sidecar present); falls back to MD-only mode
- **What it does**: Discovers and parses MinerU sidecar JSONs, builds unified
  `Block` model.
- **Precedence**: v2 > legacy > middle > none
- **Algorithm**: Token-level LCS coverage ≥ `alignment_threshold` (default
  0.95) for block-to-MD alignment.
- **Limits**: Whole-doc coverage < 0.5 triggers MD-only mode + warning.

---

## structure.markers.{page,blank}

- **Scope**: pre-processing
- **Confidence**: medium
- **What it does**: Inserts `<!-- page break: N -->` / `<!-- blank page: N -->`
  markers where sidecar confirms page boundaries.
- **Limits**: Heuristic insertion (line-matches block.text prefix). v1 may
  insert markers at slightly off positions for tables-of-contents.

---

## typography.spacing.blank_lines

- **Scope**: global
- **Confidence**: high
- **Before**:
  ```
  paragraph one


  paragraph two
  ```
- **After**:
  ```
  paragraph one

  paragraph two
  ```
- **Limits**: None.

---

## typography.spacing.number_gap

- **Scope**: prose
- **Confidence**: high
- **Before**: `JGJ- 102`, `12. 3`, `5. 2 章节`, `DGJ- 08-103-2003`
- **After**: `JGJ-102`, `12.3`, `5.2 章节`, `DGJ-08-103-2003`
- **Limits**: Does NOT touch `12. version` (space not between digits).
  Does NOT touch `26 °C` (digit + space + unit, not part of the rule).

---

## typography.spacing.cjk_gap

- **Scope**: prose (non-poetry, non-table, non-heading, non-list, non-blockquote)
- **Confidence**: medium
- **Branches**:
  - **A (bulk)**: ≥2 candidates per block AND ≥3 per page → all candidates fixed
  - **B (sidecar-anchored single)**: exactly 1 candidate AND sidecar has no
    space at same span → fixed
  - **Else**: candidate logged to `needs_review`, no modification
- **Negative signals** (line skipped from consideration entirely):
  - ≤3 Han characters on the line (poetry)
  - All candidates use U+3000 (full-width space, intentional)
  - Inside table cell (`|` at line start)
  - Heading (`#` at start)
  - List item (`-` / `*` / digit+`.` at start)
  - Blockquote (`>` at start)
- **Before**: `自 己` in a paragraph with multiple candidates; page has ≥3 such candidates
- **After**: `自己`
- **Limits**: Conservative by default. Single isolated gaps without sidecar
  evidence go to `needs_review`. Aggressive mode available via per-book
  `cjk_gap: "off"` then explicit allowlist (v1.1).

---

## blocks.callout.{label}

- **Scope**: heading lines
- **Confidence**: high (whole-line label) / medium (label + body)
- **Default labels**: `POINT` (configurable via `callout_labels`)
- **Before**:
  ```
  ## POINT

  以价值观为中心工作，就能一直保持工作动力。
  ```
- **After**:
  ```
  > **POINT**
  >
  > 以价值观为中心工作，就能一直保持工作动力。
  ```
- **Limits**: v1 converts heading-style callouts only. Multi-line callouts
  spanning multiple headings are not handled.

---

## blocks.title.split

- **Scope**: heading lines
- **Confidence**: high
- **Before**: `# 5.2电梯5.2.1内容`
- **After**:
  ```
  # 5.2 电梯

  ## 5.2.1 内容
  ```
- **Trigger**: line is a heading AND contains exactly 2 valid level numbers
  AND second is exactly one level deeper than first.
- **Limits**: Will NOT split if titles empty (`# 5.25.2.1`) or if levels
  don't validate.

---

## ocr.identifier.{jgj,dgj,gb}

- **Scope**: prose
- **Confidence**: high
- **Before**: `JGJ-lO2`, `DGJ-O8-l03-2003`, `GB/T-IO2`
- **After**: `JGJ-102`, `DGJ-08-103-2003`, `GB/T-102`
- **Confusables**: `l`, `I` → `1`; `O` → `0` (only in numeric slots)
- **Hard protection**: Roman numerals (`I`, `II`, `III`), ISO prefix, product
  SKUs are not touched (no `prefix` match → rule does not fire).
- **Limits**: Single character substitution per slot; if the source string is
  missing multiple chars the rule does not guess them.

---

## Adding a new rule

1. Identify target stage (`structure.*` / `typography.*` / `blocks.*` / `ocr.*` / `verify.*`)
2. Implement `rule_fn(text, ctx, cfg) -> (text, ChangeRecord | None)` matching
   the interface (see `references/patterns.md` and `_types.py`)
3. Append `{"id": "<stage.category.name>", "fn": rule_fn, "scope": ..., "confidence": ...}`
   to that stage's `RULES` (or to its `_build_rules` factory for parametric rules)
4. Add 1 positive + 1 negative + 1 protected-context fixture under `fixtures/`
5. Add per-rule idempotence test in `tests/test_stages.py`
6. Document in this file with id, scope, before/after, confidence, limits
7. Run `python -m unittest discover -s tests` — all green
8. (Optional) Dry-run on test PDF; manually review first-10 before/after pairs

A new rule shipping ≈ 30-60 LOC + 3-5 fixtures + 1 unit test. No architectural
change required.