# pdf-styled-extract

Extract PDF pages to styled HTML with selectable text + rendered vector decorations.

## Quick start

```bash
# 1. Extract pages 95-133 from book.pdf → ./out/
python3 extract.py book.pdf 95 133 ./out

# 2. Sanity-check the output
python3 verify.py ./out

# 3. Generate side-by-side comparison (original PDF vs extracted HTML)
python3 compare.py book.pdf ./out 96

# 4. Open compare_p96.html in browser for review
```

Output structure:
```
out/
├── styled_p{N}.html       # one per page (text-selectable)
├── images/
│   ├── page{N}_drawings.png   # rendered vector decorations
│   ├── page{N}_full.png       # full-page render for comparison
└── compare_p{N}.html     # side-by-side review page
```

## Tunable parameters

Set via env vars before running `extract.py`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DECORATION_AREA_FRAC` | 0.25 | Drawings smaller than this fraction of page area → "decorative" → skip text under |
| `DECORATION_ITEM_LIMIT` | 200 | Drawings with fewer path items → decorative |
| `H1_SIZE` | 25 | Font-size threshold for `<h1>` (pt) |
| `H2_SIZE` | 18 | Font-size threshold for `<h2>` (pt) |

## Adjusting if output looks wrong

| Issue | Fix |
|-------|-----|
| Body text missing (filtered too aggressively) | `DECORATION_AREA_FRAC=0.4` |
| Title shown twice (drawing + text overlay) | `DECORATION_AREA_FRAC=0.15` |
| Headings not detected | Increase `H1_SIZE` / `H2_SIZE` |
| Headings too aggressive | Decrease thresholds |

## Validated on

- 《如何找到想做的事》(八木仁平), p95-133, 39 pages
- ~125ms/page extraction, 185KB drawings/page
- 100% color/heading fidelity, text selectable

## How it works

1. pymupdf extracts `get_text("dict")` — per-span font/size/color
2. pymupdf `get_drawings()` returns vector paths
3. Drawings classified as **decorative** (small/few) vs **page-background** (large/many, e.g. Type3-font text)
4. Decorative drawings: rendered as PNG, **text underneath skipped** (no double-render)
5. Page-background drawings: rendered as PNG, **text underneath kept** (styled HTML)
6. Final: HTML = `[drawings PNG] + [styled text spans]`

## Limitations

- Scanned PDFs (image-only) won't work — use OCR first
- Type3-font text is rendered twice (in drawings + text layer); usually invisible if positions match
- Complex tables/multi-column layouts may need manual adjustment