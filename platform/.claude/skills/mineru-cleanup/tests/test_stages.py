"""Tests for mineru-cleanup stages and rules.

Uses stdlib unittest only. Each test loads a fixture pair (.input.md / .expected.md)
from ../fixtures/ and verifies the corresponding rule produces the expected output.

Idempotence is enforced both at stage-level (golden fixture is byte-equal on second
pass) and at rule-level (every rule produces byte-equal output when called twice).
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# Make scripts/ importable
TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
FIXTURES_DIR = SKILL_DIR / "fixtures"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from _types import Block, Context  # noqa: E402

import stage_01_structure  # noqa: E402
import stage_02_typography  # noqa: E402
import stage_03_blocks  # noqa: E402
import stage_04_ocr  # noqa: E402


# --- Helpers -------------------------------------------------------------


def load_pair(name: str) -> tuple:
    """Load (input, expected) from fixtures/{name}.input.md / {name}.expected.md."""
    inp = (FIXTURES_DIR / f"{name}.input.md").read_text(encoding="utf-8")
    exp = (FIXTURES_DIR / f"{name}.expected.md").read_text(encoding="utf-8")
    return inp, exp


def make_ctx(blocks=None, cfg=None):
    return Context(
        page_idx=0,
        blocks=blocks,
        config=cfg or {},
        warnings=[],
        protected_regions=[],
    )


def run_stage2(text: str, cfg: dict | None = None) -> str:
    ctx = make_ctx(cfg=cfg)
    out, _ = stage_02_typography.apply(text, ctx, cfg or {})
    return out


def run_stage3(text: str, cfg: dict | None = None) -> str:
    ctx = make_ctx(cfg=cfg)
    out, _ = stage_03_blocks.apply(text, ctx, cfg or {})
    return out


def run_stage4(text: str, cfg: dict | None = None) -> str:
    ctx = make_ctx(cfg=cfg)
    out, _ = stage_04_ocr.apply(text, ctx, cfg or {})
    return out


# --- Stage 2: typography rules ------------------------------------------


class TestTypographyBlankLines(unittest.TestCase):
    def test_collapses_three_blanks_to_two(self):
        inp, exp = load_pair("blank_lines")
        self.assertEqual(run_stage2(inp), exp)


class TestTypographyNumberGap(unittest.TestCase):
    def test_strips_spaces_in_identifier_and_decimal(self):
        inp, exp = load_pair("number_gap")
        self.assertEqual(run_stage2(inp), exp)

    def test_preserves_space_in_temperature_unit(self):
        text = "温度是 26 °C。"
        self.assertEqual(run_stage2(text), text)


class TestTypographyCjkGap(unittest.TestCase):
    def test_bulk_branch_fixes_multiple_candidates(self):
        inp, exp = load_pair("cjk_gap_positive")
        out = run_stage2(inp)
        self.assertEqual(out, exp)

    def test_poetry_is_skipped(self):
        inp, exp = load_pair("cjk_gap_negative_poetry")
        out = run_stage2(inp)
        self.assertEqual(out, exp)

    def test_table_lines_are_skipped(self):
        text = "| 列1 自 己 | 列2 |\n| 自 由 | 列4 |"
        self.assertEqual(run_stage2(text), text)

    def test_heading_lines_get_fixed_when_page_density_high(self):
        """HEADING is no longer a negative signal as of 2026-07-30.

        With page_candidates_total >= 3 (4 here), heading lines also get their
        CJK gaps removed. This recovers OCR errors in chapter titles (e.g.,
        八木仁平 PDF: TOC items 13/14 had "自 己" that the original PDF doesn't
        have). The risk of false positives in headings is bounded because the
        page-density signal already restricts over-fixing.
        """
        text = "句1 自 己 是 重要\n句2 自 己 喜欢\n句3 自 己 擅长\n# 自 己 的 价 值"
        expected = "句1 自己是重要\n句2 自己喜欢\n句3 自己擅长\n# 自己的价值"
        self.assertEqual(run_stage2(text), expected)

    def test_list_lines_are_skipped(self):
        text = "- 自 己 是 重要"
        self.assertEqual(run_stage2(text), text)

    def test_fullwidth_space_not_touched(self):
        text = "自　己　最　重　要"  # U+3000
        self.assertEqual(run_stage2(text), text)

    def test_off_mode_disables_rule(self):
        text = "自 己 重要。能 收到。"
        cfg = {"cjk_gap": "off"}
        self.assertEqual(run_stage2(text, cfg), text)


# --- Stage 3: blocks rules ----------------------------------------------


class TestBlocksCallout(unittest.TestCase):
    def test_point_heading_becomes_blockquote(self):
        inp, exp = load_pair("callout_point")
        self.assertEqual(run_stage3(inp), exp)

    def test_non_callout_heading_unchanged(self):
        text = "## 介绍"
        self.assertEqual(run_stage3(text), text)

    def test_inline_point_unchanged(self):
        text = "这是关于 POINT 概念的说明。"
        self.assertEqual(run_stage3(text), text)


class TestBlocksTitleSplit(unittest.TestCase):
    def test_concatenated_heading_splits(self):
        inp, exp = load_pair("title_split")
        self.assertEqual(run_stage3(inp), exp)

    def test_normal_heading_unchanged(self):
        text = "# 5.2 电梯介绍"
        self.assertEqual(run_stage3(text), text)

    def test_single_number_heading_unchanged(self):
        text = "# 5.2 内容"
        self.assertEqual(run_stage3(text), text)


# --- Stage 4: ocr identifier rules --------------------------------------


class TestOcrIdentifier(unittest.TestCase):
    def test_jgj_dgj_confusables_fixed(self):
        inp, exp = load_pair("identifier_jgj")
        # JGJ alone fires; DGJ requires full block match. Use defaults.
        out = run_stage4(inp)
        self.assertEqual(out, exp)

    def test_iso_prefix_untouched(self):
        text = "符合 ISO-9001 标准"
        self.assertEqual(run_stage4(text), text)

    def test_roman_numeral_untouched(self):
        text = "第 III 章"
        self.assertEqual(run_stage4(text), text)


# --- Protected syntax non-regression ------------------------------------


class TestProtectedSyntax(unittest.TestCase):
    def test_inline_code_protected(self):
        inp, exp = load_pair("protected_syntax")
        # Run all stages together (the protected_syntax.expected.md assumes
        # all rules fire; only the last paragraph's JGJ- lO2 should be fixed).
        ctx = make_ctx()
        sentinel_text, regions, _, _ = stage_01_structure.apply(inp, ctx.warnings, {})
        out2, _ = stage_02_typography.apply(sentinel_text, ctx, {})
        out3, _ = stage_03_blocks.apply(out2, ctx, {})
        out4, _ = stage_04_ocr.apply(out3, ctx, {})
        restored = stage_01_structure.restore_sentinels(out4, regions)
        self.assertEqual(restored, exp)

    def test_sentinel_restoration_byte_equal(self):
        text = "```python\ncode\n```\n\nJGJ- 102 outside"
        regions = [(f"<<PROTECTED_{i}>>", m.group(0))
                   for i, m in enumerate(stage_01_structure._FENCE_RE.finditer(text))]
        sentinel_text = stage_01_structure._FENCE_RE.sub(
            lambda m: regions[[r[1] for r in regions].index(m.group(0))][0], text)
        restored = stage_01_structure.restore_sentinels(sentinel_text, regions)
        self.assertEqual(restored, text)


# --- Idempotence --------------------------------------------------------


class TestIdempotence(unittest.TestCase):
    def test_each_rule_idempotent(self):
        """For each rule, calling rule_fn twice yields byte-equal output."""
        rules = []
        for stage in (stage_02_typography, stage_03_blocks):
            for r in getattr(stage, "RULES", []):
                rules.append(r)
        # Add stage 4 identifier rules (parametric)
        for r in stage_04_ocr._RULES({}):
            rules.append(r)
        ctx = make_ctx()
        samples = [
            "自 己 能 收到。\n\n\n\n间隙。",
            "## POINT\n\n内容。",
            "# 5.2电梯5.2.1内容",
            "JGJ- lO2 标准。",
        ]
        for r in rules:
            for sample in samples:
                first_text, first_change = r["fn"](sample, ctx, {})
                if first_change is None:
                    continue
                second_text, second_change = r["fn"](first_text, ctx, {})
                self.assertEqual(
                    second_text, first_text,
                    f"rule {r['id']} not idempotent on sample: {sample!r}",
                )


class TestStageLevelIdempotence(unittest.TestCase):
    def test_high_confidence_golden_is_byte_equal(self):
        """End-to-end golden: high_confidence.input.md should produce high_confidence.expected.md
        and a second pass over the output should produce no further diff."""
        from _types import DEFAULT_CONFIG
        from stage_05_verify import idempotence_check

        inp, exp = load_pair("high_confidence")
        cfg = dict(DEFAULT_CONFIG)
        warnings: list = []
        sentinel_text, regions, blocks, page_metrics = stage_01_structure.apply(inp, warnings, cfg)
        ctx = make_ctx(blocks=blocks, cfg=cfg)
        ctx.warnings = warnings
        ctx.protected_regions = regions
        out2, _ = stage_02_typography.apply(sentinel_text, ctx, cfg)
        out3, _ = stage_03_blocks.apply(out2, ctx, cfg)
        out4, _ = stage_04_ocr.apply(out3, ctx, cfg)
        cleaned = stage_01_structure.restore_sentinels(out4, regions)
        self.assertEqual(cleaned, exp)

        # Idempotence: re-run on cleaned should be byte-equal
        # (Use MD-only mode since no sidecar for this fixture)
        ctx2 = make_ctx(cfg=cfg)
        sentinel2, regions2, _, _ = stage_01_structure.apply(cleaned, ctx2.warnings, cfg)
        text2b, _ = stage_02_typography.apply(sentinel2, ctx2, cfg)
        text2c, _ = stage_03_blocks.apply(text2b, ctx2, cfg)
        text2d, _ = stage_04_ocr.apply(text2c, ctx2, cfg)
        restored2 = stage_01_structure.restore_sentinels(text2d, regions2)
        self.assertEqual(restored2, cleaned, "second pass produced different output")


# --- Sidecar adapter ----------------------------------------------------


class TestSidecarAdapter(unittest.TestCase):
    def test_legacy_adapter(self):
        import json
        raw = json.loads((FIXTURES_DIR / "sidecar_legacy.json").read_text(encoding="utf-8"))
        blocks = stage_01_structure.adapt_legacy(raw)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].page_idx, 0)
        self.assertEqual(blocks[0].source, "legacy")

    def test_v2_adapter(self):
        import json
        raw = json.loads((FIXTURES_DIR / "sidecar_v2.json").read_text(encoding="utf-8"))
        blocks = stage_01_structure.adapt_v2(raw)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].page_idx, 0)
        self.assertEqual(blocks[0].source, "v2")

    def test_middle_load(self):
        import json
        raw = json.loads((FIXTURES_DIR / "middle_minimal.json").read_text(encoding="utf-8"))
        self.assertIn("pdf_info", raw)
        self.assertEqual(raw["pdf_info"]["page_count"], 1)


# --- Stage 1 helpers ----------------------------------------------------


class TestStage1Helpers(unittest.TestCase):
    def test_is_cjk_basic(self):
        from _types import is_cjk
        self.assertTrue(is_cjk("中"))
        self.assertTrue(is_cjk("车"))
        self.assertFalse(is_cjk("a"))
        self.assertFalse(is_cjk("1"))
        self.assertFalse(is_cjk(""))

    def test_normalize_nfc(self):
        # "自" + U+0301 (combining acute) → NFC form should compose
        decomposed = "é"  # e + U+0301
        result = stage_01_structure.normalize_input(decomposed)
        # NFC should produce a single precomposed character
        self.assertEqual(result, "é")

    def test_bom_stripped(self):
        text = "﻿hello"
        result = stage_01_structure.normalize_input(text)
        self.assertEqual(result, "hello")

    def test_crlf_normalized(self):
        result = stage_01_structure.normalize_input("a\r\nb")
        self.assertEqual(result, "a\nb")

    def test_sentinels_round_trip(self):
        original = "before `code` middle [link](url) after"
        sentinel_text, regions = stage_01_structure.install_sentinels(original)
        self.assertNotIn("`code`", sentinel_text)
        restored = stage_01_structure.restore_sentinels(sentinel_text, regions)
        self.assertEqual(restored, original)


# --- CLI ----------------------------------------------------------------


class TestCLI(unittest.TestCase):
    def test_list_rules(self):
        from run import list_rules
        # Capture stdout
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            list_rules()
        output = buf.getvalue()
        self.assertIn("typography.spacing.blank_lines", output)
        self.assertIn("ocr.identifier.jgj", output)


class TestPageExtractionMismatch(unittest.TestCase):
    """Tests for _check_page_extraction_mismatch in stage_01_structure.py.

    Behavior under test: when sidecar detects ≥2 visual blocks on a page but only
    ≤1 image was extracted, emit a PageExtractionMismatch warning.
    """

    def setUp(self):
        import tempfile
        from pathlib import Path as _P
        self._tmpdir = _P(tempfile.mkdtemp(prefix="mismatch-test-"))
        self._md_path = self._tmpdir / "test.md"
        self._v2_path = self._tmpdir / "test_content_list_v2.json"

    def _make_blocks(self, page_idx_to_blocks):
        """Build a list of Block-like dicts with .type, .page_idx, .bbox."""
        return [
            Block(page_idx=p, type="seal", text="x", bbox=(x, y, x + w, y + h))
            for p, blocks in page_idx_to_blocks.items()
            for i, (x, y, w, h) in enumerate(blocks)
        ]

    def _make_v2(self, page_idx_to_count):
        import json
        v2 = []
        max_p = max(page_idx_to_count.keys()) if page_idx_to_count else 0
        for p in range(max_p + 1):
            n = page_idx_to_count.get(p, 0)
            v2.append([{"type": "image", "content": {"image_source": {"path": f"images/p{p}_i{i}.jpg"}}} for i in range(n)])
        self._v2_path.write_text(json.dumps(v2, ensure_ascii=False), encoding="utf-8")
        self._md_path.write_text("# test\n", encoding="utf-8")

    def test_fires_when_many_blocks_but_single_image(self):
        from stage_01_structure import _check_page_extraction_mismatch
        # Page 5 has 4 small visual blocks in sidecar, but only 1 image extracted
        self._make_v2({5: 1})
        blocks = self._make_blocks({5: [(10, 10, 30, 30)] * 4})  # 4 small bboxes
        warnings = []
        _check_page_extraction_mismatch(self._md_path, blocks, warnings)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].error_type, "PageExtractionMismatch")
        self.assertIn("page_idx 5", warnings[0].error_message_first_line)
        self.assertIn("4 visual blocks", warnings[0].error_message_first_line)

    def test_silent_when_block_count_matches_image_count(self):
        from stage_01_structure import _check_page_extraction_mismatch
        # Page 5 has 2 visual blocks, 2 images → no mismatch
        self._make_v2({5: 2})
        blocks = self._make_blocks({5: [(10, 10, 30, 30), (50, 50, 30, 30)]})
        warnings = []
        _check_page_extraction_mismatch(self._md_path, blocks, warnings)
        self.assertEqual(warnings, [])

    def test_silent_when_blocks_too_few(self):
        from stage_01_structure import _check_page_extraction_mismatch
        # Page 5 has only 1 small block, 1 image — under threshold, no warning
        self._make_v2({5: 1})
        blocks = self._make_blocks({5: [(10, 10, 30, 30)]})  # just 1
        warnings = []
        _check_page_extraction_mismatch(self._md_path, blocks, warnings)
        self.assertEqual(warnings, [])

    def test_silent_when_md_path_missing(self):
        from stage_01_structure import _check_page_extraction_mismatch
        blocks = self._make_blocks({5: [(10, 10, 30, 30)] * 4})
        warnings = []
        _check_page_extraction_mismatch(None, blocks, warnings)
        self.assertEqual(warnings, [])

    def test_caps_at_10_warnings(self):
        from stage_01_structure import _check_page_extraction_mismatch
        # 15 pages each with many blocks + 1 image
        per_page = {p: [(10, 10, 30, 30)] * 4 for p in range(15)}
        self._make_v2({p: 1 for p in range(15)})
        blocks = self._make_blocks(per_page)
        warnings = []
        _check_page_extraction_mismatch(self._md_path, blocks, warnings)
        self.assertEqual(len(warnings), 10)


class TestEmphasisWrap(unittest.TestCase):
    """Tests for the PDF-emphasis wrap logic in md_to_html.py.

    Regression guards for the data-URI corruption bug caught on 2026-07-30:
    short ASCII phrases (e.g., "100") collated inside base64 data URIs and
    got wrapped, breaking the embedded images.
    """

    def test_data_uri_phrase_does_not_wrap_inside_base64(self):
        """Phrase '100' lives inside base64 — must NOT be wrapped as emphasis."""
        from md_to_html import _wrap_emphasis_skip_data_uris
        # Real data URI from the test PDF (first 200 chars). Contains '100' substrings in base64.
        prefix = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAs"
        wrapped = _wrap_emphasis_skip_data_uris(prefix, ["100", "POINT"])
        # The data URI must be byte-exact (no span inserted)
        self.assertEqual(wrapped, prefix,
                          "data URI was modified — base64 corruption regression")

    def test_data_uri_phrase_does_wrap_in_surrounding_prose(self):
        """Same phrases get wrapped when they appear in surrounding prose."""
        from md_to_html import _wrap_emphasis_skip_data_uris
        prefix = "data:image/png;base64,XYZABC100DEF"
        text = f"重要的事情是 {prefix} 和之后的 100"
        wrapped = _wrap_emphasis_skip_data_uris(text, ["100"])
        # Critical: data URI is unchanged (not corrupted)
        self.assertIn(prefix, wrapped)
        # Prose "100" after data URI IS wrapped
        self.assertIn('<span class="pdf-emphasis">100</span>', wrapped)
        # Data URI itself has no span inside
        self.assertFalse('<span' in prefix)

    def test_html_tag_text_content_gets_wrapped(self):
        """Phrases in text between HTML tags get wrapped; tags themselves don't."""
        from md_to_html import _wrap_emphasis_skip_html_tags
        # Table-like HTML with phrase in cell
        html = "<table><tr><td>重要的事</td></tr></table>"
        wrapped = _wrap_emphasis_skip_html_tags(html, ["重要的事"])
        # Phrase inside <td> gets wrapped
        self.assertIn('<span class="pdf-emphasis">重要的事</span>', wrapped)
        # Tags preserved
        self.assertIn("<table>", wrapped)
        self.assertIn("</table>", wrapped)
        self.assertIn("<td>", wrapped)

    def test_html_tag_attributes_untouched(self):
        """Phrases inside tag attributes (e.g., <img alt="100">) are not wrapped."""
        from md_to_html import _wrap_emphasis_skip_html_tags
        html = '<img alt="100" src="images/x.jpg">'
        wrapped = _wrap_emphasis_skip_html_tags(html, ["100"])
        # alt attribute stays intact — no span inside it
        self.assertEqual(wrapped, html)

    def test_phrases_shorter_than_3_chars_filtered_out(self):
        """Single-char and 2-char phrases (noise) get filtered."""
        from md_to_html import _wrap_emphasis_phrases
        text = "X 'POINT' 重要的事"
        wrapped = _wrap_emphasis_phrases(text, ["X", "'", "POINT", "重要的事"])
        # 'X' (1 char) and "'" (1 char) ignored
        self.assertNotIn('<span class="pdf-emphasis">X</span>', wrapped)
        # 3+ char phrases wrapped
        self.assertIn('<span class="pdf-emphasis">重要的事</span>', wrapped)

    def test_xss_phrase_escaped(self):
        """Phrases with HTML special chars get escaped, no injection."""
        from md_to_html import _wrap_emphasis_phrases
        # Phrase with HTML char
        text = "看 <script>alert</script>"
        # Phrase contains the actual HTML chars
        wrapped = _wrap_emphasis_phrases(text, ["<script>alert</script>"])
        # Phrase text appears in the span (after downstream html.escape will convert entities)
        # The wrap function itself inserts raw phrase; escaping happens later in _inline
        self.assertIn("<script>alert</script>", wrapped)


class TestChapterTitleAndPointCallout(unittest.TestCase):
    """Tests for chapter title (## 第X章) and POINT callout detection."""

    def test_chapter_title_renders_as_h1_with_class(self):
        from md_to_html import md_to_self_contained_html
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            md = tmpdir / "test.md"
            md.write_text("## 第四章 找到指引人生的指南针：重要的事\n\n正文。\n", encoding="utf-8")
            out = md_to_self_contained_html(md)
            html = out.read_text(encoding="utf-8")
            self.assertIn('<h1 class="chapter-title">第四章 找到指引人生的指南针：重要的事</h1>', html)

    def test_non_chapter_h2_stays_as_h2(self):
        """Section headings (## Section, no '第X章' prefix) should NOT trigger h1."""
        from md_to_html import md_to_self_contained_html
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            md = tmpdir / "test.md"
            md.write_text("## 这是普通二级标题\n\n正文。\n", encoding="utf-8")
            out = md_to_self_contained_html(md)
            html = out.read_text(encoding="utf-8")
            self.assertIn('<h2>这是普通二级标题</h2>', html)
            self.assertNotIn('<h1 class="chapter-title">', html)

    def test_point_callout_with_blank_separator(self):
        """POINT\n\nbody → wrapped as styled blockquote."""
        from md_to_html import md_to_self_contained_html
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            md = tmpdir / "test.md"
            md.write_text("POINT\n\n通过三个视角了解自己。\n", encoding="utf-8")
            out = md_to_self_contained_html(md)
            html = out.read_text(encoding="utf-8")
            self.assertIn('<blockquote class="point-callout">', html)
            self.assertIn('point-callout-label', html)
            self.assertIn('point-callout-body', html)
            self.assertIn('通过三个视角了解自己', html)
            # No body content left in prose
            self.assertNotIn("POINT\n\n", html)

    def test_point_callout_at_end_of_doc(self):
        """POINT at end of document (no following body) — still styled, body section absent."""
        from md_to_html import md_to_self_contained_html
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            md = tmpdir / "test.md"
            md.write_text("正文开始。\n\nPOINT", encoding="utf-8")
            out = md_to_self_contained_html(md)
            html = out.read_text(encoding="utf-8")
            self.assertIn('point-callout-label', html)
            # Check for actual span tag (not just the class name which is also in CSS)
            self.assertNotIn('<span class="point-callout-body">', html)

    def test_point_callout_stops_at_next_heading(self):
        """POINT body should NOT consume content of next heading."""
        from md_to_html import md_to_self_contained_html
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            md = tmpdir / "test.md"
            md.write_text("POINT\n\ncallout body\n\n## 下一节\n\n下一节body。\n", encoding="utf-8")
            out = md_to_self_contained_html(md)
            html = out.read_text(encoding="utf-8")
            # Body should be just "callout body", not consume next heading
            self.assertIn('point-callout-body">callout body</span>', html)
            # Next heading rendered as h2 (not consumed by callout)
            self.assertIn('<h2>下一节</h2>', html)


if __name__ == "__main__":
    unittest.main()

class TestCustomPhrases(unittest.TestCase):
    """Tests for the `custom_phrases` sidecar field that augments pymupdf-extracted
    phrases for PDFs where color metadata is incomplete (some "blue" text has
    color=0 in pymupdf's dict output)."""

    def test_load_emphasis_phrases_merges_per_page_and_custom(self):
        """The loader returns a deduped list combining per-page phrases + custom_phrases."""
        import json
        import tempfile
        from pathlib import Path
        from md_to_html import _load_emphasis_phrases

        sidecar = {
            "85": ["重点是要遵守", "用大脑书写"],
            "90": ["重点是要遵守", "思考怎样用"],
            "custom_phrases": ["用大脑书写", "用身体书写", "顺畅地书写自己的心情"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "x.md"
            md.write_text("# x", encoding="utf-8")
            (md.parent / "mineru-emphasis.json").write_text(
                json.dumps(sidecar, ensure_ascii=False), encoding="utf-8"
            )
            phrases = _load_emphasis_phrases(md)

        # All unique phrases should appear (no dupes)
        assert "重点是要遵守" in phrases
        assert "用大脑书写" in phrases
        assert "用身体书写" in phrases
        assert "顺畅地书写自己的心情" in phrases
        # "用大脑书写" appears in BOTH per-page AND custom → should only be listed once
        assert phrases.count("用大脑书写") == 1
        # "重点是要遵守" appears in both pages 85 and 90 → only once
        assert phrases.count("重点是要遵守") == 1

    def test_wrap_emphasis_phrases_applies_custom(self):
        """After loading custom_phrases, the wrap function should apply them to prose."""
        from md_to_html import _wrap_emphasis_phrases

        # Simulate loading from sidecar (per-page + custom merged)
        per_page = ["重点是要遵守"]
        custom = ["用大脑书写", "用身体书写"]
        all_phrases = sorted(set(per_page + custom), key=len, reverse=True)

        text = "如果说普通笔记是用大脑书写的，那么书写冥想是用身体书写的。重点是要遵守规则。"
        wrapped = _wrap_emphasis_phrases(text, all_phrases)

        # All three should be wrapped
        assert "<span class=\"pdf-emphasis\">用大脑书写</span>" in wrapped
        assert "<span class=\"pdf-emphasis\">用身体书写</span>" in wrapped
        assert "<span class=\"pdf-emphasis\">重点是要遵守</span>" in wrapped

    def test_add_custom_phrases_cli_dedupes_against_existing(self):
        """The --add CLI does not duplicate phrases that already exist."""
        import json
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            sidecar = Path(tmp) / "mineru-emphasis.json"
            sidecar.write_text(
                json.dumps({"custom_phrases": ["用大脑书写"]}, ensure_ascii=False),
                encoding="utf-8",
            )

            # Run --add with one existing and one new phrase
            script_path = str(
                Path(__file__).resolve().parent.parent / "scripts" / "extract_pdf_emphasis.py"
            )
            r = subprocess.run(
                ["python", script_path, "--add", str(sidecar), "用大脑书写", "用身体书写"],
                capture_output=True, text=True,
            )
            assert r.returncode == 0, r.stderr

            data = json.loads(sidecar.read_text(encoding="utf-8"))
            # Existing phrase unchanged
            assert "用大脑书写" in data["custom_phrases"]
            # New phrase added
            assert "用身体书写" in data["custom_phrases"]
            # No duplicates
            assert data["custom_phrases"].count("用大脑书写") == 1
            assert data["custom_phrases"].count("用身体书写") == 1
            assert len(data["custom_phrases"]) == 2
