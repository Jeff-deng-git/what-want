"""Generate side-by-side comparison HTML for visual review.

Usage: python3 compare.py <pdf_path> <output_dir> [page_num]

If page_num given: single page comparison
If not: index page listing all pages with thumbnails
"""
import os
import sys
import re

import pymupdf

from lib_drawings import render_full_page_png


def make_single_compare(pdf_path, page_num, out_dir):
    """Build compare_p{N}.html with original full-page PNG + extracted HTML iframe."""
    doc = pymupdf.open(pdf_path)
    if page_num > doc.page_count:
        print(f"Page {page_num} out of range")
        return

    # Render full page PNG
    page = doc[page_num - 1]
    full_png = os.path.join(out_dir, "images", f"page{page_num}_full.png")
    render_full_page_png(page, full_png, dpi=120)

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>p{page_num} comparison</title>
<style>
  body {{ font-family: -apple-system, "PingFang SC", sans-serif; margin: 0; padding: 20px; background: #fafaf5; }}
  h1 {{ font-size: 18px; margin: 0 0 16px 0; }}
  .compare {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; max-width: 1400px; margin: 0 auto; }}
  .panel {{ background: white; border: 1px solid #e5e5e0; border-radius: 12px; padding: 20px; }}
  .panel h2 {{ font-size: 14px; margin: 0 0 12px 0; color: #888; }}
  .panel img {{ max-width: 100%; border: 1px solid #eee; }}
  iframe {{ width: 100%; height: 1400px; border: 1px solid #eee; }}
</style></head>
<body>
<h1>PDF 提取效果对比 — 第 {page_num} 页</h1>
<div class="compare">
  <div class="panel">
    <h2>① 原版 PDF</h2>
    <img src="images/page{page_num}_full.png" alt="original">
  </div>
  <div class="panel">
    <h2>② 提取的 HTML（可选中）</h2>
    <iframe src="styled_p{page_num}.html"></iframe>
  </div>
</div>
</body></html>'''

    compare_path = os.path.join(out_dir, f"compare_p{page_num}.html")
    with open(compare_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Written: {compare_path}")


def make_index(out_dir):
    """Index page linking to all single-page compares."""
    pages = []
    for f in sorted(os.listdir(out_dir)):
        m = re.match(r"styled_p(\d+)\.html", f)
        if m:
            pages.append(int(m.group(1)))

    if not pages:
        print("No pages to index")
        return

    links = '\n'.join(
        f'<li><a href="compare_p{p}.html">第 {p} 页</a> (<a href="styled_p{p}.html">直接查看 HTML</a>)</li>'
        for p in pages
    )

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Extraction comparison index</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 24px; }}
  h1 {{ font-size: 22px; }}
  ul {{ line-height: 2; }}
  a {{ color: #2563eb; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style></head>
<body>
<h1>提取效果对比索引</h1>
<p>共 {len(pages)} 页，点击查看单页对比：</p>
<ul>
{links}
</ul>
</body></html>'''

    idx_path = os.path.join(out_dir, "index.html")
    with open(idx_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Index: {idx_path}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    pdf_path = sys.argv[1]
    out_dir = sys.argv[2]

    if len(sys.argv) > 3:
        page_num = int(sys.argv[3])
        make_single_compare(pdf_path, page_num, out_dir)
    else:
        # Auto: generate compare for first page, then index for all
        # Find existing pages from styled_p*.html
        pages = []
        for f in sorted(os.listdir(out_dir)):
            m = re.match(r"styled_p(\d+)\.html", f)
            if m:
                pages.append(int(m.group(1)))

        if pages:
            # Generate compare for first page (sample)
            make_single_compare(pdf_path, pages[0], out_dir)
            make_index(out_dir)
        else:
            print("No extracted pages found. Run extract.py first.")


if __name__ == "__main__":
    main()