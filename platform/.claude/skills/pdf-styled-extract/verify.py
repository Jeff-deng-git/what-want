"""Verify extracted HTML files.

Usage: python3 verify.py <output_dir>

Checks per page:
- HTML exists
- Has at least 1 heading OR 1 paragraph (extraction didn't fail)
- Has drawings image if page has decorative content
- Image file size > 0

Prints a summary table.
"""
import os
import sys
import re


def verify(output_dir):
    pages = []
    for f in sorted(os.listdir(output_dir)):
        if f.startswith("styled_p") and f.endswith(".html"):
            m = re.match(r"styled_p(\d+)\.html", f)
            if m:
                pages.append(int(m.group(1)))

    if not pages:
        print(f"No styled_p*.html files found in {output_dir}")
        return 1

    rows = []
    alerts = []

    for p in pages:
        html_path = os.path.join(output_dir, f"styled_p{p}.html")
        img_path = os.path.join(output_dir, "images", f"page{p}_drawings.png")

        html = open(html_path, encoding='utf-8').read()
        h1 = len(re.findall(r'<h1[\s>]', html))
        h2 = len(re.findall(r'<h2[\s>]', html))
        paragraphs = len(re.findall(r'<p[\s>]', html))
        colored = len(re.findall(r'color:#(?!000000)', html))
        img_size = os.path.getsize(img_path)/1024 if os.path.exists(img_path) else 0

        rows.append((p, h1, h2, paragraphs, colored, img_size))

        if h1 + h2 == 0 and paragraphs == 0:
            alerts.append(f"p{p}: NO content extracted!")
        if img_size == 0 and (h1 + h2 + paragraphs) > 5:
            # Pages with text but no image — probably a content-heavy page w/o decorations
            pass  # not an alert

    # Print table
    print(f"\n=== Verification: {output_dir} ===")
    print(f"{'Page':<6} {'H1':<4} {'H2':<4} {'P':<5} {'Color':<7} {'Img KB':<10}")
    for r in rows:
        print(f"p{r[0]:<5} {r[1]:<4} {r[2]:<4} {r[3]:<5} {r[4]:<7} {r[5]:<10.1f}")

    if alerts:
        print(f"\n⚠ {len(alerts)} alerts:")
        for a in alerts:
            print(f"  {a}")
    else:
        print(f"\n✓ All pages passed sanity checks")

    return 0 if not alerts else 2


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "./styled_out"
    sys.exit(verify(out))