"""Drawing classification + rendering helpers.

Classifies vector drawings as:
- DECORATIVE: small area + few path items (titles, callouts, blue highlights) — skip text under
- PAGE_BACKGROUND: large / many paths (Type3-font text rendered as paths) — keep text
"""
import os
from dataclasses import dataclass
import pymupdf


@dataclass
class DrawingClassification:
    decorative_rects: list  # small drawings whose underlying text should be skipped
    all_drawings: list     # all drawings, for rendering
    skip_all_text: bool    # True if drawings dominate page (e.g., Type3 fonts as paths)
    total_drawing_area: float  # for diagnostics


def classify_drawings(page, area_frac=0.25, item_limit=200, page_dominance_frac=0.70):
    """Split drawings into decorative vs page-background.

    Args:
        page: pymupdf Page
        area_frac: drawings smaller than this fraction of page area are decorative
        item_limit: drawings with fewer than this many path items are decorative
        page_dominance_frac: if total drawing area > this fraction of page, mark skip_all_text
    """
    page_area = page.rect.width * page.rect.height
    decorative = []
    total_area = 0
    for d in page.get_drawings():
        if not d.get('rect'):
            continue
        items = len(d.get('items', []))
        area = d['rect'].width * d['rect'].height
        total_area += area
        if items < item_limit and area < area_frac * page_area:
            decorative.append(d['rect'])
    # Default: text is the source of truth. User prefers text-selectable over
    # pixel-perfect rendering. Drawings only render for pages where text is empty.
    skip_all = False
    return DrawingClassification(
        decorative_rects=decorative,
        all_drawings=page.get_drawings(),
        skip_all_text=skip_all,
        total_drawing_area=total_area,
    )


def render_drawings_to_png(page, drawings, out_path, padding=10, dpi=200):
    """Render the union bbox of all drawings to a PNG. Returns path or None."""
    if not drawings:
        return None
    xmin, ymin, xmax, ymax = float('inf'), float('inf'), -float('inf'), -float('inf')
    for d in drawings:
        r = d.get('rect')
        if r:
            xmin = min(xmin, r.x0); ymin = min(ymin, r.y0)
            xmax = max(xmax, r.x1); ymax = max(ymax, r.y1)
    if xmin >= xmax or ymin >= ymax:
        return None
    clip = pymupdf.Rect(
        max(0, xmin - padding),
        max(0, ymin - padding),
        min(page.rect.x1, xmax + padding),
        min(page.rect.y1, ymax + padding),
    )
    pix = page.get_pixmap(clip=clip, dpi=dpi)
    pix.save(out_path)
    return out_path


def render_full_page_png(page, out_path, dpi=120):
    """Render the entire page to a PNG (for comparison)."""
    pix = page.get_pixmap(dpi=dpi)
    pix.save(out_path)
    return out_path