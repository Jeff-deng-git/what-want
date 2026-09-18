---
name: mineru-cleanup
description: |
  Cleans up MinerU PDF→MD output by applying Layer 2 (MD post-processing)
  and Layer 3 (OCR anomaly repair) fixes. Run on a MinerU workdir containing
  a `.md` file and optional `_content_list.json` / `_content_list_v2.json` /
  `_middle.json` sidecar JSONs. Use when Chinese typeset PDFs produce MinerU
  output with OCR artifacts like CJK-character gaps, callout misclassification,
  heading concatenation, identifier errors (JGJ/DGJ/GB standards), and blank-line
  drift. Conservative by default — high precision over high recall; ambiguous
  cases land in `needs_review`, never silently rewritten.
allowed-tools:
  - Bash
  - Read
  - Glob
---

# mineru-cleanup

Post-processes MinerU `.md` output to remove OCR/layout artifacts that MinerU
cannot fix on its own. Standalone skill — does **not** invoke MinerU, does
**not** couple to `pdf-styled-extract`, does **not** integrate with the
What_Want backend. You run MinerU separately, then point this skill at the
resulting workdir.

## When to use

- You have a MinerU workdir (folder containing `{stem}.md` plus optional
  `_content_list.json` / `_content_list_v2.json` / `_middle.json` sidecar)
- The PDF was typeset in Chinese (textbooks, manuals, standards, books)
- OCR/layout artifacts need fixing before downstream consumption

## When NOT to use

- MinerU has not been run yet — run MinerU first
- The MD is from a non-MinerU extractor — patterns are calibrated to MinerU output
- You need PDF→MD conversion — use MinerU (`mineru.exe`) or `pdf-styled-extract`
- You need in-place editing — this skill is non-destructive, writes `.cleaned.md`

## Usage

```bash
python scripts/run.py "<minerU-workdir>" [--dry-run] [--disable RULE_ID ...] [--ignore-gates] [--verbose] [--list-rules]
```

Outputs in `<workdir>`:
- `{stem}.cleaned.md` — cleaned Markdown (NOT written on `--dry-run` or when
  hard gates fail)
- `{stem}.cleanup-report.json` — full change ledger + metrics + warnings

## What it fixes (v1)

| Rule ID | What it does |
|---|---|
| `typography.spacing.blank_lines` | 3+ blank lines → 2 |
| `typography.spacing.number_gap` | Spaces inside decimal / chapter-number / identifier tokens |
| `typography.spacing.cjk_gap` | Multi-signal heuristic for ASCII spaces between CJK chars |
| `blocks.callout.point` | `## POINT` → `> **POINT**` blockquote |
| `blocks.title.split` | Heading concatenation (e.g., `# 5.2电梯5.2.1内容` → two headings) |
| `ocr.identifier.jgj` | `l/I/O` → `1/1/0` in `JGJ-\d{3}` numeric slots |
| `ocr.identifier.dgj` | `l/I/O` → `1/1/0` in `DGJ-\d{2}-\d{3}-\d{4}` numeric slots |
| `ocr.identifier.gb` | `l/I/O` → `1/1/0` in `GB/T-\d+(?:\.\d+)?` numeric slots |

## Safety

- Original `.md` is never modified
- Hard gates (sentinel integrity, balance, idempotence) prevent writing
  `.cleaned.md` if any rule breaks the document
- `cleanup-report.json.applied_changes` shows exactly what was changed and why
- `cleanup-report.json.needs_review` lists ambiguous candidates for manual review
- MD-only fallback: if sidecar is absent / malformed / fails alignment, the
  skill still runs (in `md_only` mode) but skips bbox-dependent rules

## Adding new rules

See `references/patterns.md` for the rule catalog and `references/config.example.json`
for per-book config schema. New rule = one function + one entry in the stage's
`RULES` list. No architectural change required.