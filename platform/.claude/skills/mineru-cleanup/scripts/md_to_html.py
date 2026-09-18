"""Convert a Markdown file (with relative image refs) to self-contained HTML.

Reads `<md_path>` and emits `<md_path>.html` next to it. All `![](images/x)`
image references are inlined as base64 data URIs so the HTML is fully
self-contained — open it in any browser and images render.

Usage:
    python scripts/md_to_html.py <path-to-cleaned.md>
    python scripts/md_to_html.py <workdir>     # picks up *.cleaned.md
"""
from __future__ import annotations

import base64
import html
import json
import mimetypes
import re
import sys
from pathlib import Path


_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _img_to_data_uri(img_path: Path) -> str:
    """Read image at img_path, return data URI string. Empty string on failure."""
    try:
        data = img_path.read_bytes()
    except OSError:
        return ""
    mime, _ = mimetypes.guess_type(str(img_path))
    if mime is None:
        suffix = img_path.suffix.lower()
        mime = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".svg": "image/svg+xml",
        }.get(suffix, "application/octet-stream")
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _load_emphasis_phrases(md_path: Path) -> list:
    """Load emphasis phrase list from a sidecar JSON if present.

    Looks for `mineru-emphasis.json` in the same directory as the MD file.
    Returns a flat deduplicated list of phrases (no per-page tracking;
    simple substring match). Combines two sources:
      - per-page phrases keyed by page-index (int-as-string): pymupdf-extracted
      - "custom_phrases" top-level array: manually-specified phrases for cases
        where the PDF's color metadata is incomplete (e.g., some "blue" text
        rendered by PDF viewers has color=0 in pymupdf's dict output)

    Empty list if no sidecar found.
    """
    sidecar = md_path.parent / "mineru-emphasis.json"
    if not sidecar.exists():
        return []
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    seen: set = set()
    phrases: list = []
    for key, value in data.items():
        if isinstance(value, list):
            for p in value:
                if isinstance(p, str) and p not in seen:
                    seen.add(p)
                    phrases.append(p)
    return phrases


def _wrap_emphasis_phrases(text: str, phrases: list) -> str:
    """Wrap occurrences of emphasis phrases with <span class="pdf-emphasis">.

    Two-pass to avoid nested wrapping:
    1. Substitute each phrase with a unique placeholder (sorted longest-first)
    2. Replace placeholders with the actual <span> markup

    Skips phrases < 3 chars (avoids noise like single "2" or quoted marks).
    """
    if not phrases:
        return text
    sorted_phrases = sorted(
        [p for p in phrases if len(p) >= 3 and p.strip()],
        key=len,
        reverse=True,
    )
    if not sorted_phrases:
        return text

    placeholders: dict = {}
    out = text
    for i, phrase in enumerate(sorted_phrases):
        token = f"\x00E{i:04d}\x00"
        placeholders[token] = f'<span class="pdf-emphasis">{phrase}</span>'
        if phrase in out:
            out = out.replace(phrase, token)
    for token, html in placeholders.items():
        out = out.replace(token, html)
    return out


# Matches data: URIs (image or any base64 payload). We must skip these when
# wrapping emphasis phrases because the random bytes inside base64 might happen
# to contain short ASCII sequences like "100" or "POINT" that match PDF emphasis
# phrases — but those are coincidences, not actual emphasis in the rendered
# output. Wrapping them would corrupt the data URI.
_DATA_URI_RE = re.compile(r"data:[^\"\s<>]+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _wrap_emphasis_skip_data_uris(text: str, phrases: list) -> str:
    """Wrap emphasis phrases while leaving data: URIs untouched.

    Splits text at data URI boundaries, runs wrap on the surrounding text only,
    and reassembles. Without this, phrases like the number "100" (a common
    PDF emphasis) get wrapped inside data URIs and break the embedded images.
    """
    if not phrases:
        return text
    parts: list = []
    last_end = 0
    for m in _DATA_URI_RE.finditer(text):
        # Wrap the prose segment preceding the data URI
        if m.start() > last_end:
            parts.append(_wrap_emphasis_phrases(text[last_end:m.start()], phrases))
        # Append the data URI verbatim (no wrapping inside opaque bytes)
        parts.append(m.group())
        last_end = m.end()
    if last_end < len(text):
        parts.append(_wrap_emphasis_phrases(text[last_end:], phrases))
    return "".join(parts)


def _wrap_emphasis_skip_html_tags(html_text: str, phrases: list) -> str:
    """Wrap emphasis phrases in rendered HTML while preserving tag structure.

    Splits at HTML tag boundaries, applies wrap (with data-URI skip) only to
    the text segments between tags, and reassembles. Lets inline HTML blocks
    (e.g., <table>...</table>) get the same emphasis-color treatment as prose.

    Tags themselves and data URIs inside attributes (e.g., <img src="data:...">)
    pass through verbatim.
    """
    if not phrases or not html_text:
        return html_text
    parts: list = []
    last_end = 0
    for m in _HTML_TAG_RE.finditer(html_text):
        if m.start() > last_end:
            # Wrap text segment between tags (data URIs inside still safe —
            # _wrap_emphasis_skip_data_uris handles them).
            parts.append(_wrap_emphasis_skip_data_uris(html_text[last_end:m.start()], phrases))
        # Append the HTML tag verbatim
        parts.append(m.group())
        last_end = m.end()
    if last_end < len(html_text):
        parts.append(_wrap_emphasis_skip_data_uris(html_text[last_end:], phrases))
    return "".join(parts)


def md_to_self_contained_html(md_path: Path) -> Path:
    """Inline all images (and optionally PDF-emphasis phrases) and emit <md_path>.html."""
    md_text = md_path.read_text(encoding="utf-8")
    base_dir = md_path.parent
    emphasis_phrases = _load_emphasis_phrases(md_path)

    def _sub(match: re.Match) -> str:
        alt = match.group(1)
        ref = match.group(2)
        # Skip data: URIs and absolute URLs
        if ref.startswith(("data:", "http://", "https://")):
            return match.group(0)
        img_path = (base_dir / ref).resolve()
        if not img_path.exists():
            # Leave as-is if image file missing
            return match.group(0)
        data_uri = _img_to_data_uri(img_path)
        if not data_uri:
            return match.group(0)
        return f"![{alt}]({data_uri})"

    inlined = _IMG_RE.sub(_sub, md_text)

    # Minimal HTML shell with readable styling (no JS, no external resources)
    safe_title = html.escape(md_path.stem)
    body_html = _md_to_html_lightweight(inlined, emphasis_phrases=emphasis_phrases)
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif; max-width: 820px; margin: 2em auto; padding: 0 1em; line-height: 1.7; color: #222; }}
  h1, h2, h3, h4 {{ line-height: 1.3; margin-top: 1.5em; }}
  h1 {{ font-size: 1.8em; border-bottom: 1px solid #ccc; padding-bottom: .2em; }}
  h2 {{ font-size: 1.4em; border-bottom: 1px solid #eee; padding-bottom: .2em; }}
  img {{ max-width: 100%; height: auto; display: block; margin: 1em auto; border: 1px solid #ddd; cursor: zoom-in; }}
  img.zoomed {{ position: fixed; top: 0; left: 0; max-width: 95vw; max-height: 95vh; background: #fff; padding: 1em; z-index: 1000; box-shadow: 0 0 20px rgba(0,0,0,.4); cursor: zoom-out; }}
  p {{ margin: .8em 0; }}
  blockquote {{ border-left: 4px solid #ccc; margin: 1em 0; padding: .5em 1em; color: #555; }}
  code {{ background: #f4f4f4; padding: .15em .35em; border-radius: 3px; font-family: Menlo, Consolas, monospace; }}
  pre {{ background: #f4f4f4; padding: .8em; border-radius: 4px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; }}
  hr {{ border: 0; border-top: 1px solid #ddd; margin: 2em 0; }}
  table {{ border-collapse: collapse; margin: 1em auto; min-width: 60%; }}
  table th, table td {{ border: 1px solid #ccc; padding: .4em .8em; vertical-align: top; }}
  table th {{ background: #f4f4f4; }}
  table tr:nth-child(even) {{ background: #fafafa; }}
  .pdf-emphasis {{ color: #1350a0; font-weight: 500; background: linear-gradient(transparent 60%, rgba(19,80,160,.08) 60%); }}
  .chapter-title {{ font-size: 2em; color: #1a3a6e; border-bottom: 3px solid #1a3a6e; padding-bottom: .4em; margin: 1.5em 0 .8em; }}
  .point-callout {{ background: #e8f0f7; border-left: 5px solid #2c5fae; padding: 1em 1.5em; margin: 1.5em 0; border-radius: 4px; }}
  .point-callout-label {{ display: inline-block; background: #2c5fae; color: white; padding: 3px 12px; border-radius: 3px; font-size: 0.85em; font-weight: 600; margin-bottom: 0.6em; letter-spacing: 0.05em; }}
  .point-callout-body {{ display: block; margin-top: 0.3em; }}
</style>
</head>
<body>
{body_html}
<script>
document.body.addEventListener('click', function(e) {{
  if (e.target.tagName === 'IMG' && e.target.alt !== 'figure') {{
    e.target.classList.toggle('zoomed');
  }});
}});
</script>
</body>
</html>
"""
    out_path = md_path.with_suffix(".html")
    out_path.write_text(html_doc, encoding="utf-8")
    return out_path


def _md_to_html_lightweight(md_text: str, emphasis_phrases: list | None = None) -> str:
    """Tiny MD→HTML for our subset. Handles headings, paragraphs, images, blockquotes,
    fenced code, inline code, hr, bold, italic, lists, GFM tables, and inline HTML
    pass-through (<table>, <br>, etc. are detected and rendered as-is).
    Not a general-purpose converter.
    """
    lines = md_text.split("\n")
    out = []
    i = 0
    in_para = False

    def _flush_para():
        nonlocal in_para
        if in_para:
            out.append("</p>")
            in_para = False

    # --- Inline HTML block pass-through --------------------------------------
    # Detect blocks of HTML embedded in markdown (e.g., MinerU emits raw <table>...</table>
    # for tables it can't represent as MD). When a line starts with `<` and matches a
    # block tag, render it raw — do NOT escape.
    _HTML_BLOCK_TAGS = {"table", "div", "section", "article", "aside", "figure",
                        "details", "summary", "fieldset", "blockquote"}
    _HTML_BLOCK_RE = re.compile(
        r"^\s*<(table|div|section|article|aside|figure|details|summary|fieldset|blockquote)\b",
        re.IGNORECASE,
    )
    _HTML_CLOSE_RE = re.compile(
        r"</(table|div|section|article|aside|figure|details|summary|fieldset|blockquote)\s*>",
        re.IGNORECASE,
    )

    # --- Markdown table parser ------------------------------------------------
    _TABLE_HEAD_SEP_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")

    # --- Chapter title detection -------------------------------------------
    # `## 第X章` (Chinese chapter title) → render as <h1 class="chapter-title"> instead of <h2>.
    # Matches: 第[一二三四五六七八九十百千万]+章 at start of heading content.
    _CHAPTER_TITLE_RE = re.compile(r"^第[一二三四五六七八九十百千万]+章[ 　]?")

    # --- POINT callout detection ------------------------------------------
    # `POINT` on its own line (Chinese book "callout box" convention).
    # Body content follows after a blank line. Wrapped as <blockquote class="point-callout">.
    _POINT_RE = re.compile(r"^POINT\s*[：:]\s*$|^POINT\s*$", re.IGNORECASE)

    def _parse_table(start: int) -> tuple[str, int]:
        """Parse a Markdown table starting at lines[start]. Returns (html, next_idx)."""
        header_cells = [c.strip() for c in lines[start].strip().strip("|").split("|")]
        if start + 1 >= len(lines) or not _TABLE_HEAD_SEP_RE.match(lines[start + 1]):
            return "", start
        rows = []
        j = start + 2
        while j < len(lines) and lines[j].strip().startswith("|"):
            cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
            rows.append(cells)
            j += 1
        html_parts = ["<table>"]
        html_parts.append("<thead><tr>")
        for h in header_cells:
            html_parts.append(f"<th>{_inline(h)}</th>")
        html_parts.append("</tr></thead>")
        if rows:
            html_parts.append("<tbody>")
            for row in rows:
                html_parts.append("<tr>")
                for c in row:
                    html_parts.append(f"<td>{_inline(c)}</td>")
                html_parts.append("</tr>")
            html_parts.append("</tbody>")
        html_parts.append("</table>")
        return "\n".join(html_parts), j

    def _inline(text: str, skip_emphasis: bool = False) -> str:
        # PDF emphasis wrapping BEFORE escaping (so phrase text matches MD verbatim).
        # Skipped for heading content (passed skip_emphasis=True) since headings have
        # their own styling and wrapping phrases inside <h*> tags produces nested emphasis.
        # Skip data: URIs during wrap — base64 inside may contain ASCII that
        # coincidentally matches an emphasis phrase, which would corrupt the image.
        if not skip_emphasis:
            text = _wrap_emphasis_skip_data_uris(text, emphasis_phrases or [])
        # Images first (data: URIs already inlined)
        text = _IMG_RE.sub(
            lambda m: f'<img alt="{html.escape(m.group(1))}" src="{html.escape(m.group(2))}">',
            text,
        )
        # Inline code
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        # Bold
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        # Italic
        text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
        # Escape the rest
        text = html.escape(text, quote=False)
        # Restore the tags we just produced (escape undid them too aggressively for &lt;)
        text = re.sub(r"&lt;img alt=\"([^\"]*)\" src=\"([^\"]*)\"&gt;", r'<img alt="\1" src="\2">', text)
        text = re.sub(r"&lt;code&gt;", "<code>", text)
        text = re.sub(r"&lt;/code&gt;", "</code>", text)
        text = re.sub(r"&lt;strong&gt;", "<strong>", text)
        text = re.sub(r"&lt;/strong&gt;", "</strong>", text)
        text = re.sub(r"&lt;em&gt;", "<em>", text)
        text = re.sub(r"&lt;/em&gt;", "</em>", text)
        # Restore emphasis spans that got escaped
        text = re.sub(r"&lt;span class=\"pdf-emphasis\"&gt;([^&]+)&lt;/span&gt;",
                      r'<span class="pdf-emphasis">\1</span>', text)
        return text

    while i < len(lines):
        line = lines[i]
        s = line.strip()

        # Fenced code
        if s.startswith("```"):
            _flush_para()
            lang = s[3:].strip()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            attr = f' class="language-{html.escape(lang)}"' if lang else ""
            out.append(f"<pre{attr}><code>{html.escape(chr(10).join(buf))}</code></pre>")
            continue

        # Headings
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            _flush_para()
            level = len(m.group(1))
            content = m.group(2)
            # Chapter title: "## 第X章 ..." → bump up to <h1> for visual prominence
            if level == 2 and _CHAPTER_TITLE_RE.match(content):
                out.append(f'<h1 class="chapter-title">{_inline(content, skip_emphasis=True)}</h1>')
            else:
                out.append(f"<h{level}>{_inline(content, skip_emphasis=True)}</h{level}>")
            i += 1
            continue

        # POINT callout: "POINT" on its own line → wrap with body content as a styled blockquote
        if _POINT_RE.match(s):
            _flush_para()
            # Collect body lines after POINT. Tolerate one optional leading blank
            # line (common pattern: "POINT\n\nbody content").
            body_lines = []
            j = i + 1
            # Skip at most one blank line right after POINT
            if j < len(lines) and not lines[j].strip():
                j += 1
            while j < len(lines):
                next_s = lines[j].strip()
                if not next_s:
                    break  # blank → end of callout
                if re.match(r"^#{1,6}\s", next_s) or next_s.startswith("```") or next_s.startswith("~~~"):
                    break  # heading/fence → end
                body_lines.append(lines[j])
                j += 1
            # Build the callout. POINT is fixed text (escaped), body comes from joined lines
            point_label = html.escape("POINT")
            body_html = ""
            if body_lines:
                # Render body as inline (with emphasis wrap)
                body_text = " ".join(line.strip() for line in body_lines)
                body_html = _wrap_emphasis_skip_html_tags(_inline(body_text, skip_emphasis=False), emphasis_phrases or [])
            inner = f'<span class="point-callout-label">{point_label}</span><span class="point-callout-body">{body_html}</span>' if body_html else f'<span class="point-callout-label">{point_label}</span>'
            out.append(f'<blockquote class="point-callout">{inner}</blockquote>')
            i = j
            continue

        # Horizontal rule
        if re.match(r"^-{3,}$|^\*{3,}$|_{3,}$", s):
            _flush_para()
            out.append("<hr>")
            i += 1
            continue

        # Blockquote
        if s.startswith(">"):
            _flush_para()
            buf = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                buf.append(lines[i].lstrip()[1:].lstrip())
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(buf))}</blockquote>")
            continue

        # Markdown table (header row + separator + body rows)
        if s.startswith("|") and i + 1 < len(lines) and _TABLE_HEAD_SEP_RE.match(lines[i + 1]):
            _flush_para()
            table_html, next_i = _parse_table(i)
            if table_html:
                out.append(table_html)
                i = next_i
                continue

        # Inline HTML block pass-through (e.g., MinerU raw <table>)
        if _HTML_BLOCK_RE.match(line):
            _flush_para()
            # Detect tag and find matching close
            tag_match = _HTML_BLOCK_RE.match(line)
            if tag_match:
                tag = tag_match.group(1).lower()
                buf = [line]
                if not _HTML_CLOSE_RE.search(line):
                    j = i + 1
                    while j < len(lines):
                        buf.append(lines[j])
                        if _HTML_CLOSE_RE.search(lines[j]):
                            j += 1
                            break
                        j += 1
                    i = j
                else:
                    i += 1
                # Pass through as raw HTML, but apply emphasis wrap to text between
                # tags so phrases like 重要的事 get the blue color treatment inside
                # inline HTML blocks too (e.g., <table> cells).
                html_block = "\n".join(buf)
                out.append(_wrap_emphasis_skip_html_tags(html_block, emphasis_phrases or []))
                continue

        # Unordered list
        if re.match(r"^[-*]\s+", line):
            _flush_para()
            out.append("<ul>")
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i]):
                item = re.sub(r"^[-*]\s+", "", lines[i])
                out.append(f"<li>{_inline(item)}</li>")
                i += 1
            out.append("</ul>")
            continue

        # Ordered list
        if re.match(r"^\d+\.\s+", line):
            _flush_para()
            out.append("<ol>")
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                item = re.sub(r"^\d+\.\s+", "", lines[i])
                out.append(f"<li>{_inline(item)}</li>")
                i += 1
            out.append("</ol>")
            continue

        # Blank line
        if not s:
            _flush_para()
            i += 1
            continue

        # Paragraph (collect contiguous non-empty lines)
        if not in_para:
            out.append("<p>")
            in_para = True
        else:
            out[-1] = out[-1] + "<br>"
        out[-1] = out[-1] + _inline(line) + " "
        i += 1

    _flush_para()
    return "\n".join(out)


# --- CLI -----------------------------------------------------------------


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python md_to_html.py <path-to-cleaned.md|dir>", file=sys.stderr)
        return 2
    target = Path(sys.argv[1]).resolve()
    if target.is_dir():
        md_files = list(target.glob("*.cleaned.md"))
    elif target.suffix == ".md":
        md_files = [target]
    else:
        print(f"Not a .md file or directory: {target}", file=sys.stderr)
        return 2
    if not md_files:
        print(f"No .cleaned.md files found", file=sys.stderr)
        return 1
    for md in md_files:
        out = md_to_self_contained_html(md)
        size_kb = out.stat().st_size / 1024
        print(f"OK: {md.name} -> {out.name} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
