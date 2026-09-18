"""Extract a chapter from PDF → markdown + images.

Usage:
  python3 extract_chapter.py <chapter_id> <start_page> <end_page>
  e.g. python3 extract_chapter.py 04 95 133
"""
import sys
import re
import os
import pymupdf

def extract(chapter_id: str, start: int, end: int, pdf_path: str, out_dir: str):
    doc = pymupdf.open(pdf_path)
    md_lines = [f"# 第{chapter_id}章 (pages {start}-{end})\n"]

    for page_idx in range(start - 1, min(end, doc.page_count)):
        page = doc[page_idx]
        text = page.get_text()

        # Clean text per page
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped:
                md_lines.append(stripped)

        # Extract images from this page
        img_list = page.get_images(full=True)
        for img_idx, img_info in enumerate(img_list):
            xref = img_info[0]
            try:
                pix = pymupdf.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:  # CMYK
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                ext = "png"
                img_name = f"p{page_idx+1}_img{img_idx}.{ext}"
                img_path = os.path.join(out_dir, "images", img_name)
                pix.save(img_path)
                md_lines.append(f"\n![图](images/{img_name})\n")
                pix = None
            except Exception as e:
                md_lines.append(f"\n[图片提取失败: {e}]\n")

        md_lines.append(f"\n<!-- page break: {page_idx+1} -->\n")

    return '\n'.join(md_lines)


if __name__ == "__main__":
    chapter_id = sys.argv[1] if len(sys.argv) > 1 else "04"
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 95
    end = int(sys.argv[3]) if len(sys.argv) > 3 else 133
    pdf_path = r"D:\AI_Project\What_Want\如何找到想做的事_(八木仁平)_(z-library.sk,_1lib.sk,_z-lib.sk).pdf"
    out_dir = r"D:\AI_Project\What_Want\platform\backend\book\chapters_md"
    os.makedirs(os.path.join(out_dir, "images"), exist_ok=True)

    md = extract(chapter_id, start, end, pdf_path, out_dir)
    out_path = os.path.join(out_dir, f"{chapter_id}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    # Count images extracted
    img_count = len([f for f in os.listdir(os.path.join(out_dir, "images")) if f.startswith(f"p")])
    print(f"Done: {out_path}")
    print(f"MD length: {len(md)} chars")
    print(f"Images extracted (total in dir): {img_count}")