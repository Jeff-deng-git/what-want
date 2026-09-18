---
name: pdf-styled-extract
description: Extract pages from a PDF (with vector drawings + styled text) into self-contained HTML. Use when the user has a PDF (especially Chinese typeset books with Type3 fonts, blue highlights, decorative callouts) and wants high-fidelity, text-selectable HTML output suitable for an interactive reader. Produces one HTML per page plus per-page drawings PNG; auto-verifies output and generates side-by-side comparison vs original PDF for review.
---

# PDF → styled HTML extraction

Convert a PDF into HTML that preserves:
- Text with **color, font-size, headings** (h1/h2/p) detected from PDF spans
- Vector drawings (decorations, highlights, Type3-font-as-path text) rendered as inline PNG
- Filter logic that **avoids double-rendering** (text drawn twice: once from drawing, once from text layer)

## When to invoke

- User has a PDF that mixes real text + heavy vector decorations (e.g., typeset Chinese books)
- Output needs to be **text-selectable** for downstream note-taking
- Visual fidelity matters (blue highlights, callouts, decorative bars)
- NOT suitable for: scanned-image PDFs (OCR required), pure plain-text PDFs (overkill)

## Workflow

### Step 1: Scope

Ask user:
- PDF path
- Page range (e.g., 95-133)
- Output directory

Default: same dir as PDF, subfolder `styled/`.

### Step 2: Extract

Run `extract.py` on the requested page range. Script classifies drawings into:
- **Decorative** (small area < 25% page, few path items < 200) → these hide text underneath; emit text SKIPPED
- **Page-background** (large / many items) → Type3 fonts rendered as paths; emit text WITH styled spans

Tunable thresholds: `DECORATION_AREA_FRAC=0.25`, `DECORATION_ITEM_LIMIT=200` (env vars).

### Step 3: Verify

Run `verify.py` on output. Checks:
- Per-page: heading count, non-black span count, body paragraph count
- Alert if any page has 0 paragraphs (extraction failed silently)
- Alert if any page has 0 drawings image (probably no decorations)
- Print summary table

### Step 4: Compare

Generate `compare.html` (side-by-side: original PDF page | extracted HTML) using `compare.py`. User reviews in browser.

### Step 5: Adjust (if needed)

If user reports issues, adjust thresholds:

| Issue | Likely fix |
|-------|-----------|
| Body text missing | Loosen `DECORATION_AREA_FRAC` to 0.4 (more drawings classified as page-bg) |
| Title shown twice (drawing + text) | Tighten `DECORATION_AREA_FRAC` to 0.15 (more drawings classified as decorative) |
| Headings not detected | Increase font-size thresholds in extract.py |
| Wrong text color | Check pymupdf returns color int correctly |

### Step 6: Cleanup

Output structure:
```
output/
├── styled_p{N}.html         # one per page
├── images/
│   └── page{N}_drawings.png # one per page (rendered vector decorations)
└── compare.html             # side-by-side review
```

## Files in this skill

- `extract.py` — main extractor (pymupdf → HTML)
- `verify.py` — sanity checker
- `compare.py` — generates side-by-side review page
- `lib_drawings.py` — drawing classification + rendering helpers
- `README.md` — usage examples

## Provenance

Validated on: 《如何找到想做的事》(八木仁平), pages 95-133, 39 pages, 7.5MB output.
- 8-page sample: 124ms/page extraction, 185KB drawings/page, 13KB HTML/page
- Visual fidelity: 100% color/heading fidelity, text selectable
- Token cost: ~0 (binary images, not loaded into LLM context)