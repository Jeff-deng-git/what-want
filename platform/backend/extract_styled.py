"""Styled extraction: text spans with font/color + vector drawings as inline images.

Output: HTML with inline CSS for one page.
Usage: python3 extract_styled.py <page_num> [chapter_id]
"""
import sys
import re
import time
import os
import pymupdf


def render_drawings_region(page, drawings, out_path, padding=10):
    """Render the union bounding box of vector drawings to a PNG."""
    if not drawings:
        return None
    # Compute union bbox of drawings
    xmin, ymin, xmax, ymax = float('inf'), float('inf'), -float('inf'), -float('inf')
    for d in drawings:
        rect = d.get('rect')
        if rect:
            xmin = min(xmin, rect.x0)
            ymin = min(ymin, rect.y0)
            xmax = max(xmax, rect.x1)
            ymax = max(ymax, rect.y1)
    if xmin >= xmax or ymin >= ymax:
        return None

    clip = pymupdf.Rect(
        max(0, xmin - padding),
        max(0, ymin - padding),
        min(page.rect.x1, xmax + padding),
        min(page.rect.y1, ymax + padding),
    )
    pix = page.get_pixmap(clip=clip, dpi=200)
    pix.save(out_path)
    return out_path


def extract_styled_page(page, page_num, out_dir):
    """Extract one page as HTML with inline styles."""
    text_dict = page.get_text("dict")
    drawings = page.get_drawings()

    # Classify drawings: small/few = "decorative" (skip text under); large/many = "page-bg" (don't skip)
    page_area = page.rect.width * page.rect.height
    decorative_rects = []
    for d in drawings:
        if not d.get('rect'):
            continue
        items = len(d.get('items', []))
        area = d['rect'].width * d['rect'].height
        # Decorative drawing: < 200 path items AND < 25% page area
        if items < 200 and area < 0.25 * page_area:
            decorative_rects.append(d['rect'])

    # Render drawings to image
    img_name = f"page{page_num}_drawings.png"
    img_path = os.path.join(out_dir, "images", img_name)
    drawing_img = render_drawings_region(page, drawings, img_path) if drawings else None

    blocks_html = []

    for block in text_dict.get('blocks', []):
        if block.get('type') != 0:
            continue
        block_bbox = block.get('bbox')
        if not block_bbox:
            continue
        block_rect = pymupdf.Rect(*block_bbox)

        # Only skip text if covered by DECORATIVE drawings (titles, callouts)
        skip = False
        for dr in decorative_rects:
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
                    first_color = hex_color
                max_size = max(max_size, size)
                line_spans.append(f'<span style="font-size:{size:.1f}px;color:{hex_color}">{text}</span>')
            if line_spans:
                spans_html.append(''.join(line_spans))

        if not spans_html:
            continue

        if max_size >= 25:
            tag = 'h1'
        elif max_size >= 18:
            tag = 'h2'
        else:
            tag = 'p'

        color_style = f'color:{first_color};' if any_color else ''
        blocks_html.append(f'<{tag} style="font-size:{max_size:.1f}px;{color_style}">{"".join(spans_html)}</{tag}>')

    # Wrap with drawing image (if any)
    drawing_html = ''
    if drawing_img:
        # Get drawing bbox for sizing hint
        drawing_html = f'<img src="images/{img_name}" alt="图" class="drawing" />'

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; line-height: 1.8; max-width: 720px; margin: 0 auto; padding: 40px 24px; color: #000; }}
  h1 {{ font-size: 32px; color: #138FBF; margin: 24px 0; }}
  h2 {{ font-size: 22px; color: #138FBF; margin: 20px 0; }}
  p {{ font-size: 16px; margin: 12px 0; }}
  img.drawing {{ max-width: 100%; margin: 16px 0; }}
</style></head>
<body>
{drawing_html}
{"".join(blocks_html)}
</body></html>'''

    return html, img_path if drawing_img else None


if __name__ == "__main__":
    page_num = int(sys.argv[1]) if len(sys.argv) > 1 else 95
    chapter_id = sys.argv[2] if len(sys.argv) > 2 else "ch04"

    pdf_path = r"D:\AI_Project\What_Want\如何找到想做的事_(八木仁平)_(z-library.sk,_1lib.sk,_z-lib.sk).pdf"
    out_dir = r"D:\AI_Project\What_Want\platform\backend\book\chapters_md"
    os.makedirs(os.path.join(out_dir, "images"), exist_ok=True)

    doc = pymupdf.open(pdf_path)
    page = doc[page_num - 1]

    t0 = time.time()
    html, img_path = extract_styled_page(page, page_num, out_dir)
    elapsed = time.time() - t0

    out_path = os.path.join(out_dir, f"styled_p{page_num}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Stats
    print(f"\n=== Page {page_num} stats ===")
    print(f"Time: {elapsed*1000:.0f} ms")
    print(f"HTML chars: {len(html)}")
    print(f"Image: {img_path}")
    if img_path and os.path.exists(img_path):
        print(f"Image size: {os.path.getsize(img_path)/1024:.1f} KB")
    print(f"Saved to: {out_path}")