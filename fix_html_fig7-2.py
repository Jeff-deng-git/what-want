#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix 6 HTML files for 图7-2:
1. Replace broken 图7-2 base64 (b6fdaa788) with correct 037b6015 base64
2. Delete duplicate list (11 items between "（见图7-2）。" reference and 图7-2 image)
3. Delete df3d71c9 base64 (POINT callout image after 图7-2)
4. Insert POINT blockquote text after "如果不能很好地组合起来..." paragraph
"""
import re
import sys
from pathlib import Path

BASE = Path(r'D:/AI_Project/What_Want/platform/.claude/skills/mineru-cleanup/output/full-book-1-257/如何找到想做的事_(八木仁平)_(z-library.sk,_1lib.sk,_z-lib.sk)/auto')

# Load correct 037b6015 base64
correct_b64 = Path('/tmp/037b6015.b64').read_text().strip()
print(f'Loaded 037b6015 base64: {len(correct_b64)} chars')

# HTML files to fix
html_files = [
    BASE / '如何找到想做的事_(八木仁平)_(z-library.sk,_1lib.sk,_z-lib.sk).cleaned -Final.html',
    BASE / '如何找到想做的事_(八木仁平)_(z-library.sk,_1lib.sk,_z-lib.sk).cleaned.html',
    BASE / '如何找到想做的事_(八木仁平)_(z-library.sk,_1lib.sk,_z-lib.sk).html',
    BASE / '如何找到想做的事_(八木仁平)_(z-library.sk,_1lib.sk,_z-lib.sk).cleaned  - 副本.html',
    BASE / '如何找到想做的事_(八木仁平)_(z-library.sk,_1lib.sk,_z-lib.sk).cleaned-ch5.html',
    BASE / 'split-by-chapter' / '如何找到想做的事_(八木仁平)_(z-library.sk,_1lib.sk,_z-lib.sk).cleaned -Final-第七章-找到真正想做的事，活出真实的自己.html',
]

# POINT blockquote HTML to insert
POINT_HTML = '<blockquote class="point-callout"><span class="point-callout-label">POINT</span><span class="point-callout-body">通过“喜欢的事×擅长的事”，假设出自己想做的事。</span></blockquote>'

# Build correct 图7-2 image tag (find exact pattern from existing HTML first)
# Pattern: <p><img alt="" src="data:image/jpeg;base64,BROKEN...">   <br>图7-2 </p>
# We'll match the img tag and replace its src

# Pattern for the broken 图7-2 img (ends with "/Z" + ">" + whitespace + "<br>图7-2")
img_fig7_pattern = re.compile(
    r'(<p[^>]*>\s*<img\s+alt=""\s+src="data:image/jpeg;base64,)([A-Za-z0-9+/=]+)("\s*>\s*<br>\s*图7-2\s*</p>)',
    re.DOTALL
)

# Pattern for duplicate list section: between "（见图7-2）。" paragraph end and the 图7-2 img
# We need to find: </p> + any list items + <p><img (fig 7-2) — and delete the middle
# Simpler: match "<p>正如大家所看到的...（见图7-2）。</p>" followed by duplicate list until <p><img ...><br>图7-2</p>
duplicate_list_pattern = re.compile(
    r'(<p[^>]*>正如大家所看到的.*?（见图7-2）。\s*</p>)\s*(<p>·构建自我认知体系并传授给别人的人.*?</p>\s*)+(<p[^>]*>\s*<img)',
    re.DOTALL
)
# Above won't work if list items have varying patterns. Let me use a simpler approach.

# Pattern: between "（见图7-2）。" reference paragraph and the 图7-2 img, delete all list <p>...</p>
# Simpler: match from "（见图7-2）。</p>" to "<p><img" and capture only the closing </p> + img opening
ref_to_img_pattern = re.compile(
    r'(<p[^>]*>[^<]*（见图7-2）。\s*</p>)\s*(?:<p>.*?</p>\s*)+?(?=<p[^>]*>\s*<img)',
    re.DOTALL
)

# Pattern for df3d71c9 (POINT callout img) after "图7-2" title
# The pattern: after 图7-2 img, "图7-2" title, paragraph "如果不能很好地组合起来...", then df3d71c9 img
point_img_pattern = re.compile(
    r'(<p[^>]*>如果不能很好地组合起来也没关系.*?尽情写出“想做的事”吧。\s*</p>)\s*<p[^>]*>\s*<img\s+alt=""\s+src="data:image/jpeg;base64,[A-Za-z0-9+/=]+"\s*>\s*</p>',
    re.DOTALL
)

for html_path in html_files:
    if not html_path.exists():
        print(f'SKIP (not found): {html_path.name}')
        continue

    print(f'\n=== Processing: {html_path.name} ===')
    html = html_path.read_text(encoding='utf-8')
    orig_len = len(html)

    # Step 1: Replace broken 图7-2 base64
    matches_fig7 = list(img_fig7_pattern.finditer(html))
    print(f'  Broken 图7-2 img found: {len(matches_fig7)}')
    if matches_fig7:
        # Replace each match
        def replace_fig7(m):
            old_b64 = m.group(2)
            print(f'    Old base64 length: {len(old_b64)}')
            return m.group(1) + correct_b64 + m.group(3)
        html = img_fig7_pattern.sub(replace_fig7, html)

    # Step 2: Delete duplicate list between ref and 图7-2 img
    # Match: "（见图7-2）。\n</p>\n" + duplicate list + (留到 <p><img)
    dup_matches = list(ref_to_img_pattern.finditer(html))
    print(f'  Duplicate list blocks found: {len(dup_matches)}')
    if dup_matches:
        def delete_dup(m):
            # Keep only the reference paragraph + direct jump to img
            return m.group(1)
        html = ref_to_img_pattern.sub(delete_dup, html)

    # Step 3: Delete df3d71c9 img + insert POINT text
    point_matches = list(point_img_pattern.finditer(html))
    print(f'  POINT img blocks found: {len(point_matches)}')
    if point_matches:
        def replace_point(m):
            # Keep paragraph + insert POINT blockquote (no img)
            return m.group(1) + '\n' + POINT_HTML
        html = point_img_pattern.sub(replace_point, html)

    new_len = len(html)
    diff = new_len - orig_len
    print(f'  Size: {orig_len} -> {new_len} (delta: {diff})')

    if diff != 0:
        html_path.write_text(html, encoding='utf-8')
        print(f'  ✓ Saved')
    else:
        print(f'  No change')

print('\n=== Done ===')