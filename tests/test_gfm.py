"""GitHub-Flavoured Markdown extensions, on top of strict CommonMark."""

from __future__ import annotations

import pytest

from md_to_html_renderer import MarkdownRenderer, RenderOptions


@pytest.fixture
def render():
    renderer = MarkdownRenderer()
    return renderer.render


class TestTables:
    def test_basic_table_structure(self, render):
        html = render("| a | b |\n|---|---|\n| 1 | 2 |\n")
        assert "<table>" in html
        assert "<thead>" in html and "<tbody>" in html
        assert "<th>a</th>" in html
        assert "<td>1</td>" in html

    @pytest.mark.parametrize(
        "delimiter, alignment",
        [(":---", "left"), (":---:", "center"), ("---:", "right")],
    )
    def test_alignment_becomes_an_align_attribute(self, render, delimiter, alignment):
        """GitHub emits ``align=``; an inline ``style`` would be stripped by the
        sanitiser, so the attribute form is both accurate and robust."""
        html = render(f"| h |\n|{delimiter}|\n| c |\n")
        assert f'<th align="{alignment}">' in html
        assert f'<td align="{alignment}">' in html
        assert "style=" not in html

    def test_unaligned_columns_get_no_attribute(self, render):
        html = render("| a |\n|---|\n| 1 |\n")
        assert "align=" not in html

    def test_escaped_pipe_stays_literal(self, render):
        html = render("| a | b |\n|---|---|\n| x \\| y | z |\n")
        assert "x | y" in html
        assert html.count("<td") == 2

    def test_pipe_inside_inline_code_does_not_split_the_cell(self, render):
        html = render("| a | b |\n|---|---|\n| `x\\|y` | z |\n")
        assert html.count("<td") == 2

    def test_ragged_rows_are_padded_and_truncated(self, render):
        """GFM ignores surplus cells and pads short rows rather than failing."""
        html = render("| a | b |\n|---|---|\n| 1 |\n| 1 | 2 | 3 |\n")
        assert "<table>" in html
        body = html.split("<tbody>")[1]
        assert body.count("<tr>") == 2

    def test_inline_markup_inside_cells(self, render):
        html = render("| a |\n|---|\n| **b** `c` |\n")
        assert "<strong>b</strong>" in html
        assert "<code>c</code>" in html

    def test_table_disabled_renders_pipes_as_text(self):
        html = MarkdownRenderer(RenderOptions(tables=False)).render(
            "| a | b |\n|---|---|\n| 1 | 2 |\n"
        )
        assert "<table>" not in html

    def test_table_without_body_rows(self, render):
        html = render("| a | b |\n|---|---|\n")
        assert "<table>" in html
        assert "<th>a</th>" in html


class TestTaskLists:
    def test_unchecked_and_checked(self, render):
        html = render("- [ ] todo\n- [x] done\n")
        assert 'class="contains-task-list"' in html
        assert html.count('type="checkbox"') == 2
        assert "checked" in html

    def test_checkboxes_are_disabled_by_default(self, render):
        assert "disabled" in render("- [ ] todo\n")

    def test_editable_option_removes_disabled(self):
        html = MarkdownRenderer(RenderOptions(tasklists_editable=True)).render("- [ ] a\n")
        assert "disabled" not in html

    def test_uppercase_x_counts_as_checked(self, render):
        assert "checked" in render("- [X] done\n")

    def test_nested_task_lists(self, render):
        html = render("- [ ] parent\n  - [x] child\n")
        assert html.count('type="checkbox"') == 2

    def test_text_that_merely_looks_like_a_checkbox(self, render):
        """``[ ]`` mid-sentence is not a task item."""
        html = render("- not a [ ] checkbox\n")
        assert 'type="checkbox"' not in html

    def test_disabled_option_leaves_plain_brackets(self):
        html = MarkdownRenderer(RenderOptions(tasklists=False)).render("- [ ] todo\n")
        assert 'type="checkbox"' not in html


class TestAlerts:
    @pytest.mark.parametrize(
        "kind", ["NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"]
    )
    def test_every_alert_kind(self, render, kind):
        html = render(f"> [!{kind}]\n> Body text\n")
        assert f'markdown-alert markdown-alert-{kind.lower()}' in html
        assert 'class="markdown-alert-title"' in html
        assert kind.capitalize() in html

    def test_alert_includes_an_icon(self, render):
        html = render("> [!NOTE]\n> Body\n")
        assert "<svg" in html and "octicon" in html

    def test_unknown_kind_stays_an_ordinary_blockquote(self, render):
        html = render("> [!BOGUS]\n> Body\n")
        assert "markdown-alert" not in html
        assert "<blockquote>" in html

    def test_alert_body_supports_block_content(self, render):
        html = render("> [!TIP]\n> - one\n> - two\n")
        assert "<ul>" in html and html.count("<li>") == 2

    def test_alerts_disabled(self):
        html = MarkdownRenderer(RenderOptions(alerts=False)).render("> [!NOTE]\n> Body\n")
        assert "markdown-alert" not in html
        assert "<blockquote>" in html


class TestStrikethrough:
    def test_double_tilde_renders_del(self, render):
        """GFM specifies ``<del>``; markdown-it's default ``<s>`` is overridden."""
        html = render("~~gone~~")
        assert "<del>gone</del>" in html
        assert "<s>" not in html

    def test_single_tilde_by_default(self, render):
        assert "<del>gone</del>" in render("~gone~")

    def test_single_tilde_can_be_disabled(self):
        html = MarkdownRenderer(
            RenderOptions(strikethrough_single_tilde=False)
        ).render("~gone~")
        assert "<del>" not in html

    def test_tilde_fence_is_not_strikethrough(self, render):
        html = render("~~~\ncode\n~~~\n")
        assert "<pre>" in html
        assert "<del>" not in html


class TestAutolinks:
    def test_bare_url_is_linked(self, render):
        assert '<a href="https://example.com"' in render("See https://example.com now")

    def test_www_host_gets_a_scheme(self, render):
        assert 'href="http://www.example.com"' in render("www.example.com")

    def test_email_becomes_mailto(self, render):
        assert 'href="mailto:a@b.com"' in render("a@b.com")

    def test_url_inside_code_span_is_not_linked(self, render):
        html = render("`https://example.com`")
        assert "<a " not in html

    def test_linkify_disabled(self):
        html = MarkdownRenderer(RenderOptions(linkify=False)).render("https://example.com")
        assert "<a " not in html

    def test_angle_bracket_autolink_always_works(self):
        """``<url>`` is CommonMark, not GFM, so it survives linkify=False."""
        html = MarkdownRenderer(RenderOptions(linkify=False)).render("<https://example.com>")
        assert '<a href="https://example.com"' in html

    def test_trailing_punctuation_is_excluded(self, render):
        html = render("Go to https://example.com.")
        assert 'href="https://example.com"' in html


class TestLinkRel:
    def test_absolute_links_get_rel(self, render):
        assert 'rel="nofollow noopener noreferrer"' in render("[x](https://example.com)")

    def test_relative_and_fragment_links_do_not(self, render):
        html = render("[a](#section) and [b](./page.md)")
        assert "rel=" not in html

    def test_rel_can_be_disabled(self):
        html = MarkdownRenderer(RenderOptions(link_rel="")).render("[x](https://a.b)")
        assert "rel=" not in html

    def test_rel_applied_to_all_links_when_option_off(self):
        renderer = MarkdownRenderer(RenderOptions(absolute_links_only_rel=False))
        assert "rel=" in renderer.render("[a](#section)")


class TestFootnotes:
    def test_reference_and_definition(self, render):
        html = render("Text[^1]\n\n[^1]: The note\n")
        assert "footnote-ref" in html
        assert 'class="footnotes"' in html
        assert "The note" in html

    def test_backreference_is_generated(self, render):
        html = render("Text[^1]\n\n[^1]: Note\n")
        assert "footnote-backref" in html

    def test_named_footnote_labels(self, render):
        html = render("Text[^note]\n\n[^note]: Body\n")
        assert "Body" in html

    def test_undefined_reference_stays_literal(self, render):
        html = render("Text[^missing]\n")
        assert "footnotes" not in html
        assert "[^missing]" in html

    def test_footnotes_disabled(self):
        html = MarkdownRenderer(RenderOptions(footnotes=False)).render(
            "Text[^1]\n\n[^1]: Note\n"
        )
        assert "footnote-ref" not in html

    def test_fragment_id_prefix_namespaces_footnote_ids(self):
        """Two documents on one page must not fight over ``#fn1``."""
        renderer = MarkdownRenderer(RenderOptions(fragment_id_prefix="doc1"))
        html = renderer.render("Text[^1]\n\n[^1]: Note\n")
        assert "doc1" in html


class TestEmoji:
    def test_known_shortcode_is_replaced(self, render):
        assert "😄" in render("Hello :smile:")

    def test_unknown_shortcode_is_left_alone(self, render):
        assert ":definitely_not_an_emoji:" in render("x :definitely_not_an_emoji: y")

    def test_shortcode_inside_code_span_is_literal(self, render):
        html = render("`:smile:`")
        assert ":smile:" in html
        assert "😄" not in html

    def test_shortcode_inside_fenced_block_is_literal(self, render):
        html = render("```\n:smile:\n```\n")
        assert ":smile:" in html
        assert "😄" not in html

    def test_emoji_disabled(self):
        html = MarkdownRenderer(RenderOptions(emoji=False)).render(":smile:")
        assert ":smile:" in html

    def test_url_containing_colons_is_not_mangled(self, render):
        html = render("https://example.com:8080/path")
        assert "example.com:8080" in html


class TestFrontMatter:
    def test_yaml_front_matter_is_stripped(self, render):
        html = render("---\ntitle: Hello\n---\n\n# Body\n")
        assert "title: Hello" not in html
        assert "Body" in html

    def test_front_matter_kept_when_disabled(self):
        html = MarkdownRenderer(RenderOptions(strip_front_matter=False)).render(
            "---\ntitle: Hello\n---\n\n# Body\n"
        )
        assert "Body" in html

    def test_thematic_break_mid_document_is_not_front_matter(self, render):
        html = render("# Title\n\n---\n\nText\n")
        assert "<hr" in html
