"""Slug generation, matching GitHub's ``github-slugger``."""

from __future__ import annotations

import pytest

from github_markdown import GitHubMarkdown, RenderOptions, Slugger, slugify


class TestSlugify:
    """Character-level rules, checked against what github-slugger produces."""

    @pytest.mark.parametrize(
        "heading, expected",
        [
            ("Hello World", "hello-world"),
            ("Hello, World!", "hello-world"),
            ("UPPER case", "upper-case"),
            ("trailing spaces   ", "trailing-spaces---"),
            ("C++ vs. Rust", "c-vs-rust"),
            ("What's new?", "whats-new"),
            ("100% coverage", "100-coverage"),
            ("under_score-and-dash", "under_score-and-dash"),
            ("a & b", "a--b"),
            ("a  b", "a--b"),
            ("#hashtag", "hashtag"),
            ("[brackets]", "brackets"),
            ("dots...everywhere", "dotseverywhere"),
        ],
    )
    def test_ascii_rules(self, heading, expected):
        assert slugify(heading) == expected

    @pytest.mark.parametrize(
        "heading, expected",
        [
            ("Grüße aus Berlin", "grüße-aus-berlin"),
            ("Überschrift", "überschrift"),
            ("日本語の見出し", "日本語の見出し"),
            ("Ελληνικά", "ελληνικά"),
            ("Привет мир", "привет-мир"),
        ],
    )
    def test_unicode_letters_survive(self, heading, expected):
        assert slugify(heading) == expected

    def test_emoji_is_dropped_without_leaving_a_separator(self):
        assert slugify("Release 🎉 notes") == "release--notes"

    def test_punctuation_only_heading_slugifies_to_empty(self):
        assert slugify("***") == ""
        assert slugify("!!!") == ""

    def test_empty_string(self):
        assert slugify("") == ""

    def test_whitespace_only(self):
        assert slugify("   ") == "---"

    def test_tabs_and_newlines_become_hyphens(self):
        assert slugify("a\tb\nc") == "a-b-c"

    def test_composed_and_decomposed_forms_agree(self):
        """NFC normalisation means the same visible heading always gets the
        same id, however the author's editor encoded the accent."""
        composed = "caf\u00e9"  # é as one code point
        decomposed = "cafe\u0301"  # e + combining acute
        assert slugify(composed) == slugify(decomposed)

    def test_rejects_non_string(self):
        with pytest.raises(TypeError, match="must be a string"):
            slugify(None)


class TestSlugger:
    """Document-level uniqueness."""

    def test_first_occurrence_is_unsuffixed(self):
        assert Slugger().slug("Setup") == "setup"

    def test_duplicates_get_numeric_suffixes(self):
        slugger = Slugger()
        assert [slugger.slug("Setup") for _ in range(4)] == [
            "setup",
            "setup-1",
            "setup-2",
            "setup-3",
        ]

    def test_literal_heading_colliding_with_a_generated_suffix(self):
        """``Setup``/``Setup``/``Setup 1`` must not both claim ``setup-1``."""
        slugger = Slugger()
        assert slugger.slug("Setup") == "setup"
        assert slugger.slug("Setup") == "setup-1"
        assert slugger.slug("Setup 1") == "setup-1-1"

    def test_reverse_collision_order(self):
        slugger = Slugger()
        assert slugger.slug("Setup 1") == "setup-1"
        assert slugger.slug("Setup") == "setup"
        assert slugger.slug("Setup") == "setup-2"

    def test_empty_headings_fall_back_and_still_deduplicate(self):
        slugger = Slugger()
        assert slugger.slug("***") == "section"
        assert slugger.slug("!!!") == "section-1"

    def test_prefix_is_applied_to_every_slug(self):
        slugger = Slugger("user-content-")
        assert slugger.slug("Setup") == "user-content-setup"
        assert slugger.slug("Setup") == "user-content-setup-1"

    def test_reset_clears_history(self):
        slugger = Slugger()
        slugger.slug("Setup")
        slugger.reset()
        assert slugger.slug("Setup") == "setup"

    def test_rejects_non_string_prefix(self):
        with pytest.raises(TypeError):
            Slugger(prefix=42)


class TestHeadingIdsInRenderedOutput:
    """The slugger is only useful if the renderer wires it up correctly."""

    def test_id_and_anchor_href_agree(self):
        html = GitHubMarkdown().render("## Getting Started")
        assert 'id="getting-started"' in html
        assert 'href="#getting-started"' in html

    def test_slug_uses_rendered_text_not_markdown_source(self):
        """``## **Bold** and `code`` must slugify the visible words, not the
        asterisks and backticks around them."""
        html = GitHubMarkdown().render("## **Bold** and `code`")
        assert 'id="bold-and-code"' in html

    def test_link_in_heading_slugifies_to_the_link_text(self):
        html = GitHubMarkdown().render("## See [the docs](https://example.com)")
        assert 'id="see-the-docs"' in html
        assert "example" not in html.split("</h2>")[0].split("<a class")[0]

    def test_image_in_heading_uses_alt_text(self):
        html = GitHubMarkdown().render("## ![Build status](badge.svg) Status")
        assert 'id="build-status-status"' in html

    def test_inline_html_in_heading_contributes_nothing(self):
        html = GitHubMarkdown().render("## Hello <em>there</em>")
        assert 'id="hello-there"' in html

    def test_duplicate_headings_across_a_document(self):
        html = GitHubMarkdown().render("## Notes\n\n## Notes\n\n## Notes\n")
        for expected in ('id="notes"', 'id="notes-1"', 'id="notes-2"'):
            assert expected in html

    def test_slug_state_does_not_leak_between_renders(self):
        """A shared renderer must not remember headings from a previous call --
        this is what makes the instance safe to reuse."""
        renderer = GitHubMarkdown()
        first = renderer.render("## Notes")
        second = renderer.render("## Notes")
        assert first == second
        assert 'id="notes-1"' not in second

    def test_heading_id_prefix_option(self):
        renderer = GitHubMarkdown(RenderOptions(heading_id_prefix="user-content-"))
        html = renderer.render("## Setup")
        assert 'id="user-content-setup"' in html
        assert 'href="#user-content-setup"' in html

    def test_anchor_style_none_emits_no_id_or_anchor(self):
        html = GitHubMarkdown(RenderOptions(anchor_style="none")).render("## Setup")
        assert html.count("<h2>") == 1
        assert "anchor" not in html

    def test_anchor_style_github_puts_the_id_on_the_anchor(self):
        renderer = GitHubMarkdown(
            RenderOptions(anchor_style="github", heading_id_prefix="user-content-")
        )
        html = renderer.render("## Setup")
        assert '<h2><a id="user-content-setup"' in html
        assert 'href="#user-content-setup"' in html
