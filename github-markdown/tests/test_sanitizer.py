"""Sanitisation: hostile HTML must not survive, benign markup must."""

from __future__ import annotations

import pytest

from github_markdown import GitHubMarkdown, RenderOptions
from github_markdown.sanitizer import HAVE_NH3

pytestmark = pytest.mark.skipif(not HAVE_NH3, reason="nh3 is not installed")


@pytest.fixture
def render():
    return GitHubMarkdown().render


class TestScriptInjection:
    def test_script_tag_and_its_contents_are_removed(self, render):
        html = render("<script>alert('xss')</script>")
        assert "<script" not in html
        assert "alert" not in html

    def test_script_split_across_markdown_constructs(self, render):
        html = render("*a*<script>alert(1)</script>*b*")
        assert "alert" not in html

    def test_style_block_is_removed_with_contents(self, render):
        html = render("<style>body{display:none}</style>")
        assert "display:none" not in html

    def test_iframe_is_removed(self, render):
        assert "<iframe" not in render('<iframe src="https://evil.test"></iframe>')

    def test_object_and_embed_are_removed(self, render):
        html = render('<object data="x"></object><embed src="y">')
        assert "<object" not in html and "<embed" not in html


class TestEventHandlers:
    @pytest.mark.parametrize(
        "markup",
        [
            '<img src="x" onerror="alert(1)">',
            '<div onclick="alert(1)">text</div>',
            '<a href="https://a.b" onmouseover="alert(1)">link</a>',
            '<body onload="alert(1)">',
            '<svg onload="alert(1)"></svg>',
        ],
    )
    def test_event_handlers_are_stripped(self, render, markup):
        html = render(markup)
        assert "alert(1)" not in html
        assert "onerror" not in html and "onclick" not in html
        assert "onmouseover" not in html and "onload" not in html


class TestDangerousUrls:
    @pytest.mark.parametrize(
        "url",
        [
            "javascript:alert(1)",
            "JaVaScRiPt:alert(1)",
            "vbscript:msgbox(1)",
            "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
            "file:///etc/passwd",
        ],
    )
    def test_dangerous_schemes_do_not_become_hrefs(self, render, url):
        """markdown-it refuses to build the anchor at all, so the URL survives
        as inert paragraph text. What matters is that it never reaches an
        ``href``, and that no link element is produced."""
        html = render(f"[click]({url})")
        assert f'href="{url}"' not in html
        assert "<a " not in html
        assert 'href="javascript' not in html.lower()
        assert 'href="vbscript' not in html.lower()
        assert 'href="data:' not in html.lower()

    def test_dangerous_scheme_in_raw_html(self, render):
        html = render('<a href="javascript:alert(1)">x</a>')
        assert "javascript:" not in html.lower()

    def test_safe_schemes_survive(self, render):
        for url in ("https://example.com", "mailto:a@b.com", "tel:+123"):
            assert url in render(f"[x]({url})")

    def test_target_attribute_is_stripped(self, render):
        """No ``target`` means no reverse-tabnabbing vector at all."""
        html = render('<a href="https://a.b" target="_blank">x</a>')
        assert "target=" not in html


class TestStyleAndComments:
    def test_style_attribute_is_stripped(self, render):
        html = render('<div style="position:fixed;top:0">overlay</div>')
        assert "style=" not in html
        assert "overlay" in html

    def test_html_comments_are_removed(self, render):
        html = render("<!-- secret note -->\n\nVisible\n")
        assert "secret note" not in html
        assert "Visible" in html


class TestBenignMarkupSurvives:
    """Sanitisation that breaks legitimate content is a bug, not safety."""

    def test_details_and_summary(self, render):
        html = render("<details><summary>More</summary>\n\nHidden text\n\n</details>")
        assert "<details>" in html and "<summary>" in html

    def test_formatting_tags(self, render):
        html = render("<b>b</b> <i>i</i> <kbd>Ctrl</kbd> <sup>1</sup> <mark>m</mark>")
        for tag in ("<b>", "<i>", "<kbd>", "<sup>", "<mark>"):
            assert tag in html

    def test_image_attributes(self, render):
        html = render('<img src="https://a.b/x.png" alt="Alt" width="100">')
        assert 'alt="Alt"' in html and 'width="100"' in html

    def test_generated_anchor_svg_survives(self, render):
        html = render("## Heading")
        assert "<svg" in html and "<path" in html and 'viewBox="0 0 16 16"' in html

    def test_generated_alert_icon_survives(self, render):
        html = render("> [!NOTE]\n> Body\n")
        assert "<svg" in html and "octicon-info" in html

    def test_highlight_spans_survive(self, render):
        html = render("```python\ndef f():\n    pass\n```\n")
        assert '<span class="k">def</span>' in html

    def test_table_align_attributes_survive(self, render):
        html = render("| a |\n|:-:|\n| 1 |\n")
        assert 'align="center"' in html

    def test_task_list_checkbox_survives(self, render):
        html = render("- [x] done\n")
        assert 'type="checkbox"' in html and "checked" in html

    def test_footnote_ids_survive(self, render):
        html = render("Text[^1]\n\n[^1]: Note\n")
        assert "id=" in html and "footnote" in html


class TestSanitizerConfiguration:
    def test_unsanitised_mode_passes_raw_html_through(self):
        """Explicitly opting out must actually opt out -- this is the mode for
        trusted, self-authored content."""
        renderer = GitHubMarkdown(RenderOptions(sanitize=False))
        assert "<script>" in renderer.render("<script>alert(1)</script>")

    def test_allow_html_false_escapes_instead_of_stripping(self):
        renderer = GitHubMarkdown(RenderOptions(allow_html=False))
        html = renderer.render("<b>bold</b>")
        assert "&lt;b&gt;" in html
        assert "<b>" not in html

    def test_allow_html_false_still_renders_markdown(self):
        renderer = GitHubMarkdown(RenderOptions(allow_html=False))
        assert "<em>x</em>" in renderer.render("*x* <b>y</b>")

    def test_extra_allowed_tags(self):
        renderer = GitHubMarkdown(
            RenderOptions(extra_allowed_tags=frozenset({"iframe"}))
        )
        assert "<iframe" in renderer.render('<iframe src="https://a.b"></iframe>')

    def test_sanitisation_is_idempotent(self, render):
        """Re-rendering sanitised output must not degrade it further."""
        source = "## Heading\n\n```python\nx = 1\n```\n\n| a |\n|:-:|\n| 1 |\n"
        once = render(source)
        renderer = GitHubMarkdown()
        assert renderer.render(source) == once
