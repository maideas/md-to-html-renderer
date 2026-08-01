"""Degenerate inputs and feature combinations.

Individual features are covered elsewhere. This module targets the spaces
between them: constructs nested inside one another, and inputs at the edge of
what is still valid Markdown.
"""

from __future__ import annotations

import pytest

from md_to_html_renderer import MarkdownRenderer, RenderOptions


@pytest.fixture
def renderer():
    return MarkdownRenderer()


@pytest.fixture
def render(renderer):
    return renderer.render


class TestDegenerateInput:
    def test_empty_string(self, render):
        assert "markdown-body" in render("")

    def test_whitespace_only(self, render):
        assert isinstance(render("   \n\n\t\n"), str)

    def test_single_character(self, render):
        assert "<p>a</p>" in render("a")

    def test_no_trailing_newline(self, render):
        assert "<p>text</p>" in render("text")

    def test_crlf_line_endings(self, render):
        html = render("# Title\r\n\r\nBody\r\n")
        assert "<h1" in html and "<p>Body</p>" in html
        assert "\r" not in html

    def test_lone_cr_line_endings(self, render):
        assert "<h1" in render("# Title\rBody\r")

    def test_byte_order_mark_is_stripped(self, render):
        html = render("\ufeff# Title\n")
        assert "<h1" in html
        assert "\ufeff" not in html

    def test_null_byte_does_not_crash(self, render):
        assert isinstance(render("a\x00b"), str)

    def test_unterminated_fence(self, render):
        html = render("```python\nx = 1\n")
        assert "<pre>" in html

    def test_unterminated_emphasis(self, render):
        assert "*unclosed" in render("*unclosed")

    def test_unclosed_html_tag(self, render):
        assert isinstance(render("<div>text"), str)

    def test_very_long_single_line(self, render):
        html = render("word " * 50_000)
        assert "<p>" in html

    def test_many_paragraphs(self, render):
        html = render("\n\n".join(f"Para {i}" for i in range(2000)))
        assert html.count("<p>") == 2000

    def test_deeply_nested_lists_do_not_blow_the_stack(self, render):
        source = "".join("  " * depth + "- item\n" for depth in range(120))
        assert "<ul>" in render(source)

    def test_deeply_nested_blockquotes(self, render):
        assert "<blockquote>" in render(">" * 200 + " text\n")

    def test_pathological_emphasis_runs(self, render):
        """A known quadratic-blowup shape for naive emphasis parsers."""
        assert isinstance(render("*" * 400 + "text" + "*" * 400), str)

    def test_unicode_throughout(self, render):
        html = render("# 見出し\n\n本文 with émojis 🎉 and Ελληνικά\n")
        assert "見出し" in html and "🎉" in html

    def test_astral_plane_characters(self, render):
        assert "𝕳" in render("𝕳ello")

    def test_lone_surrogate_is_survivable(self, render):
        """Malformed text should raise cleanly or render, never corrupt state."""
        try:
            render("a\ud800b")
        except (ValueError, UnicodeError):
            pass


class TestInputLimits:
    def test_oversized_input_is_rejected_with_a_clear_message(self):
        renderer = MarkdownRenderer(RenderOptions(max_input_bytes=100))
        with pytest.raises(ValueError, match="max_input_bytes"):
            renderer.render("x" * 200)

    def test_limit_counts_bytes_not_characters(self):
        renderer = MarkdownRenderer(RenderOptions(max_input_bytes=10))
        with pytest.raises(ValueError):
            renderer.render("é" * 9)  # 18 bytes in UTF-8

    def test_zero_limit_means_unlimited(self):
        renderer = MarkdownRenderer(RenderOptions(max_input_bytes=0))
        assert "<p>" in renderer.render("x" * 100_000)

    def test_oversized_code_block_falls_back_to_plain_text(self):
        renderer = MarkdownRenderer(RenderOptions(max_highlight_bytes=100))
        html = renderer.render("```python\n" + "x = 1\n" * 500 + "```\n")
        assert "<pre>" in html
        assert '<span class="k">' not in html

    def test_bytes_input_is_rejected_with_guidance(self, renderer):
        with pytest.raises(TypeError, match="decode"):
            renderer.render(b"# Title")

    def test_none_input_is_rejected(self, renderer):
        with pytest.raises(TypeError):
            renderer.render(None)


class TestCodeBlockEdgeCases:
    def test_unknown_language_renders_plain(self, render):
        html = render("```notalanguage\nsome text\n```\n")
        assert 'class="language-notalanguage"' in html
        assert "<span" not in html.split("<code")[1].split("</code>")[0]

    def test_no_language_is_not_guessed_by_default(self, render):
        html = render("```\ndef f(): pass\n```\n")
        assert "highlight" not in html

    def test_guessing_can_be_enabled(self):
        renderer = MarkdownRenderer(RenderOptions(highlight_guess_language=True))
        html = renderer.render("```\ndef hello():\n    return 1\n```\n")
        assert "<span" in html

    def test_info_string_with_attributes_uses_only_the_language(self, render):
        html = render('```python title="demo.py"\nx = 1\n```\n')
        assert 'class="language-python"' in html
        assert "demo.py" not in html

    def test_nested_fences_with_longer_backtick_runs(self, render):
        html = render("````markdown\n```python\nx = 1\n```\n````\n")
        assert "```python" in html

    def test_tilde_fence_can_contain_backticks(self, render):
        html = render("~~~\n```\n~~~\n")
        assert "```" in html

    def test_empty_fence(self, render):
        assert "<pre><code></code></pre>" in render("```\n```\n")

    def test_indented_code_block_is_never_highlighted(self, render):
        html = render("    def f():\n        pass\n")
        assert "<pre>" in html
        assert "highlight" not in html

    def test_html_in_code_block_is_escaped_not_executed(self, render):
        html = render("```\n<script>alert(1)</script>\n```\n")
        assert "&lt;script&gt;" in html

    def test_highlighting_disabled_keeps_language_class(self):
        renderer = MarkdownRenderer(RenderOptions(highlight=False))
        html = renderer.render("```python\nx = 1\n```\n")
        assert 'class="language-python"' in html
        assert "<span" not in html.split("<code")[1].split("</code>")[0]

    def test_malformed_code_still_highlights_without_raising(self, render):
        assert isinstance(render("```python\ndef ((( not valid\n```\n"), str)

    def test_language_alias_resolves(self, render):
        html = render("```js\nconst x = 1;\n```\n")
        assert "highlight-source-js" in html

    def test_diff_language(self, render):
        html = render("```diff\n+added\n-removed\n```\n")
        assert "highlight-source-diff" in html


class TestFeatureCombinations:
    """Constructs nested inside one another -- where the subtle bugs live."""

    def test_table_inside_list_item(self, render):
        html = render("- item\n\n  | a | b |\n  |---|---|\n  | 1 | 2 |\n")
        assert "<table>" in html and "<li>" in html

    def test_fenced_code_inside_list_item(self, render):
        html = render("1. step\n\n   ```python\n   x = 1\n   ```\n")
        assert "<ol>" in html and "highlight-source-python" in html

    def test_fenced_code_inside_blockquote(self, render):
        html = render("> ```python\n> x = 1\n> ```\n")
        assert "<blockquote>" in html and "highlight-source-python" in html

    def test_table_inside_blockquote(self, render):
        html = render("> | a |\n> |---|\n> | 1 |\n")
        assert "<blockquote>" in html and "<table>" in html

    def test_list_inside_blockquote_inside_list(self, render):
        html = render("- outer\n  > - inner\n")
        assert "<blockquote>" in html and html.count("<ul>") >= 2

    def test_alert_containing_a_fenced_block(self, render):
        html = render("> [!WARNING]\n> ```python\n> x = 1\n> ```\n")
        assert "markdown-alert-warning" in html and "highlight-source-python" in html

    def test_alert_containing_a_table(self, render):
        html = render("> [!NOTE]\n> | a |\n> |---|\n> | 1 |\n")
        assert "markdown-alert-note" in html and "<table>" in html

    def test_task_list_containing_a_code_span_and_link(self, render):
        html = render("- [x] run `make` per [docs](https://a.b)\n")
        assert 'type="checkbox"' in html and "<code>make</code>" in html
        assert 'rel="nofollow noopener noreferrer"' in html

    def test_footnote_inside_a_heading(self, render):
        """The heading slug and the footnote registry both walk the same inline
        tokens; neither may corrupt the other."""
        html = render("## Title[^1]\n\n[^1]: Note\n")
        assert 'id="title1"' in html or "id=" in html
        assert "footnote-ref" in html
        assert html.count("footnote-backref") == 1

    def test_footnote_inside_a_table_cell(self, render):
        html = render("| a |\n|---|\n| x[^1] |\n\n[^1]: Note\n")
        assert "<table>" in html and "footnote-ref" in html

    def test_emoji_inside_a_heading_slug(self, render):
        html = render("## Release :tada: notes\n")
        assert "🎉" in html
        assert 'id="release--notes"' in html

    def test_emoji_in_table_cell_but_not_in_its_code_span(self, render):
        html = render("| a | b |\n|---|---|\n| :smile: | `:smile:` |\n")
        assert "😄" in html
        assert "<code>:smile:</code>" in html

    def test_strikethrough_wrapping_a_link(self, render):
        html = render("~~[gone](https://a.b)~~")
        assert "<del>" in html and "<a href" in html

    def test_nested_emphasis_inside_a_link_inside_a_list(self, render):
        html = render("- [**bold** and *italic*](https://a.b)\n")
        assert "<strong>bold</strong>" in html and "<em>italic</em>" in html

    def test_image_inside_a_link_inside_a_table(self, render):
        html = render("| a |\n|---|\n| [![alt](i.png)](https://a.b) |\n")
        assert "<img" in html and "<a href" in html

    def test_html_block_between_markdown_blocks(self, render):
        html = render("# One\n\n<div>raw</div>\n\n# Two\n")
        assert html.count("<h1") == 2 and "<div>raw</div>" in html

    def test_details_containing_markdown(self, render):
        html = render("<details>\n<summary>More</summary>\n\n- item\n\n</details>\n")
        assert "<details>" in html and "<li>" in html

    def test_breaks_option_combined_with_a_table(self):
        renderer = MarkdownRenderer(RenderOptions(breaks=True))
        html = renderer.render("| a |\n|---|\n| 1 |\n\nline\nbreak\n")
        assert "<table>" in html and "<br" in html

    def test_all_features_at_once(self, render):
        """A document exercising every extension simultaneously."""
        source = (
            "---\ntitle: Front matter\n---\n\n"
            "# Doc :tada:\n\n"
            "> [!TIP]\n> Use `code` and ~~old~~ new.\n\n"
            "| a | b |\n|:--|--:|\n| 1 | 2 |\n\n"
            "- [x] done[^1]\n- [ ] todo\n\n"
            "```python\ndef f():\n    return 1\n```\n\n"
            "Visit https://example.com\n\n"
            "[^1]: A note\n"
        )
        html = render(source)
        for expected in (
            "markdown-alert-tip",
            "<table>",
            'type="checkbox"',
            "highlight-source-python",
            "footnote",
            "<del>old</del>",
            "🎉",
            'href="https://example.com"',
        ):
            assert expected in html, f"missing {expected}"
        assert "title: Front matter" not in html


class TestIdempotenceAndReuse:
    def test_same_input_renders_identically_across_calls(self, renderer):
        source = "# A\n\n## A\n\n- [x] t\n\n```python\nx=1\n```\n"
        assert renderer.render(source) == renderer.render(source)

    def test_separate_instances_agree(self):
        source = "# Title\n\n## Title\n"
        assert MarkdownRenderer().render(source) == MarkdownRenderer().render(source)

    def test_concurrent_rendering_is_safe(self, renderer):
        """One renderer shared across threads must not interleave slug state."""
        import concurrent.futures

        source = "# Shared\n\n## Shared\n\n```python\nx = 1\n```\n"
        expected = renderer.render(source)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: renderer.render(source), range(64)))
        assert all(result == expected for result in results)
