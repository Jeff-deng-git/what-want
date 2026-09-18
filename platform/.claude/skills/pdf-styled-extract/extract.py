"""Extract one or more PDF pages as styled HTML.

Usage:
  python3 extract.py <pdf_path> <start_page> <end_page> [output_dir]
  python3 extract.py book.pdf 95 133 ./out

Env vars (tunable thresholds):
  DECORATION_AREA_FRAC=0.25  # drawings smaller than this fraction are decorative
  DECORATION_ITEM_LIMIT=200  # drawings with fewer items are decorative
  H1_SIZE=25                 # font-size threshold for h1 (pt)
  H2_SIZE=18                 # font-size threshold for h2 (pt)
"""
import os
import sys
import time

import pymupdf

from lib_drawings import classify_drawings, render_drawings_to_png

# Tunables (env-overridable)
DECORATION_AREA_FRAC = float(os.getenv("DECORATION_AREA_FRAC", "0.25"))
DECORATION_ITEM_LIMIT = int(os.getenv("DECORATION_ITEM_LIMIT", "200"))
H1_SIZE = float(os.getenv("H1_SIZE", "25"))
H2_SIZE = float(os.getenv("H2_SIZE", "18"))
DEFAULT_OUTPUT = os.getenv("WW_OUTPUT_DIR", "./styled_out")


def html_escape(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def extract_page(page, page_num, out_dir, render_dpi=200):
    """Extract one page. Returns (html_path, drawings_path, stats_dict)."""
    text_dict = page.get_text("dict")
    classification = classify_drawings(
        page, area_frac=DECORATION_AREA_FRAC, item_limit=DECORATION_ITEM_LIMIT,
    )

    # Render drawings to image ONLY when text is suppressed (skip_all_text).
    # If text is rendered as HTML, the drawing image (which often duplicates
    # text via Type3-font paths) would be a duplicate.
    img_name = f"page{page_num}_drawings.png"
    img_path = os.path.join(out_dir, "images", img_name)
    drawing_img = None
    if classification.skip_all_text:
        drawing_img = render_drawings_to_png(
            page, classification.all_drawings, img_path, dpi=render_dpi,
        )

    # Extract raster images (figures, charts — these are NOT duplicates of text)
    # Each image stores (filename, y0) for position-aware interleaving
    raster_imgs = []
    for i, img_info in enumerate(page.get_images(full=True)):
        xref = img_info[0]
        try:
            # Get image bbox on page (y0 = top edge)
            bbox_list = page.get_image_rects(xref)
            y0 = bbox_list[0].y0 if bbox_list else 0
            pix = pymupdf.Pixmap(page.parent, xref)
            if pix.n - pix.alpha >= 4:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            # Skip tiny images (likely icons/decorations, not figures)
            if pix.width < 80 or pix.height < 80:
                continue
            fig_name = f"page{page_num}_fig{i}.png"
            fig_path = os.path.join(out_dir, "images", fig_name)
            pix.save(fig_path)
            raster_imgs.append((fig_name, y0))
        except Exception as e:
            print(f"  warn: failed to extract image {i} on p{page_num}: {e}")

    # Sort images by y position
    raster_imgs.sort(key=lambda x: x[1])

    blocks_html = []
    headings = 0
    paragraphs = 0
    colored_spans = 0

    for block in text_dict.get('blocks', []):
        if block.get('type') != 0:
            continue
        block_bbox = block.get('bbox')
        if not block_bbox:
            continue
        block_rect = pymupdf.Rect(*block_bbox)

        # Skip if covered by decorative drawing (title/callout)
        # OR if drawings dominate the page (Type3 fonts → drawings image has all text)
        skip = classification.skip_all_text
        if not skip:
            for dr in classification.decorative_rects:
                intersect = block_rect & dr
                if intersect.get_area() > 0.5 * block_rect.get_area():
                    skip = True
                    break
        if skip:
            continue

        spans_html = []
        max_size = 0
        any_color = False
        first_color = '#000000'

        for line in block.get('lines', []):
            line_spans = []
            for span in line.get('spans', []):
                text = span['text']
                if not text.strip():
                    continue
                size = span['size']
                color = span['color']
                hex_color = f"#{color:06x}"
                if hex_color != '#000000':
                    any_color = True
                    colored_spans += 1
                    first_color = hex_color
                max_size = max(max_size, size)
                line_spans.append(
                    f'<span style="font-size:{size:.1f}px;color:{hex_color}">{html_escape(text)}</span>'
                )
            if line_spans:
                spans_html.append(''.join(line_spans))

        if not spans_html:
            continue

        if max_size >= H1_SIZE:
            tag = 'h1'; headings += 1
        elif max_size >= H2_SIZE:
            tag = 'h2'; headings += 1
        else:
            tag = 'p'; paragraphs += 1

        color_style = f'color:{first_color};' if any_color else ''
        blocks_html.append((
            block_rect.y0,  # sort key
            f'<{tag} style="font-size:{max_size:.1f}px;{color_style}">{"".join(spans_html)}</{tag}>'
        ))

    # Insert images at their y position (interleaved with text)
    for name, y0 in raster_imgs:
        blocks_html.append((y0, f'<img src="images/{name}" alt="图示" class="figure" />'))

    # Sort all blocks by y position
    blocks_html.sort(key=lambda x: x[0])
    sorted_blocks = ''.join(html for _, html in blocks_html)

    drawing_html = f'<img src="images/{img_name}" alt="图" class="drawing" />' if drawing_img else ''

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; line-height: 1.8; max-width: 720px; margin: 0 auto; padding: 40px 24px; color: #000; }}
  h1 {{ font-size: 32px; color: #138FBF; margin: 24px 0; }}
  h2 {{ font-size: 22px; color: #138FBF; margin: 20px 0; }}
  p {{ font-size: 16px; margin: 12px 0; }}
  img.drawing {{ max-width: 100%; margin: 16px 0; }}
  img.figure {{ max-width: 100%; margin: 16px 0; border: 1px solid #eee; border-radius: 4px; }}
</style></head>
<body>
{drawing_html}
{sorted_blocks}
</body></html>'''

    html_path = os.path.join(out_dir, f"styled_p{page_num}.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return html_path, drawing_img, {
        'page': page_num,
        'html_chars': len(html),
        'img_size_kb': os.path.getsize(drawing_img)/1024 if drawing_img else 0,
        'headings': headings,
        'paragraphs': paragraphs,
        'colored_spans': colored_spans,
    }


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    pdf_path = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    out_dir = sys.argv[4] if len(sys.argv) > 4 else DEFAULT_OUTPUT

    os.makedirs(os.path.join(out_dir, "images"), exist_ok=True)

    doc = pymupdf.open(pdf_path)
    total_time = 0
    stats = []

    for page_num in range(start, end + 1):
        if page_num > doc.page_count:
            break
        page = doc[page_num - 1]
        t0 = time.time()
        html_path, img_path, s = extract_page(page, page_num, out_dir)
        s['time_ms'] = (time.time() - t0) * 1000
        stats.append(s)
        total_time += s['time_ms']
        print(f"p{page_num}: {s['time_ms']:.0f}ms | html={s['html_chars']}c | "
              f"img={s['img_size_kb']:.1f}KB | h={s['headings']} p={s['paragraphs']} c={s['colored_spans']}")

    # Summary
    n = len(stats)
    print(f"\n=== {n} pages ===")
    print(f"Total time: {total_time/1000:.1f}s ({total_time/n:.0f}ms/page)")
    print(f"Avg img:    {sum(s['img_size_kb'] for s in stats)/n:.1f}KB/page")
    print(f"Output: {out_dir}")
    print(f"HTML files: styled_p{{N}}.html")
    print(f"Images:     images/page{{N}}_drawings.png")


if __name__ == "__main__":
    main()