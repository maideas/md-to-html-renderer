"""The public API contract: options, assets, page output and the CLI."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from github_markdown import GitHubMarkdown, RenderOptions
from github_markdown.cli import main
from github_markdown.highlight import pygments_class_names
from github_markdown.renderer import STYLESHEET_NAMES


class TestOptionsValidation:
    def test_defaults_construct(self):
        assert RenderOptions().anchor_style == "heading"

    def test_options_are_immutable(self):
        options = RenderOptions()
        with pytest.raises(Exception):
            options.breaks = True  # type: ignore[misc]

    def test_evolve_returns_a_validated_copy(self):
        options = RenderOptions().evolve(breaks=True)
        assert options.breaks is True
        assert RenderOptions().breaks is False

    def test_invalid_anchor_style(self):
        with pytest.raises(ValueError, match="anchor_style"):
            RenderOptions(anchor_style="sideways")  # type: ignore[arg-type]

    def test_negative_limit(self):
        with pytest.raises(ValueError, match="max_input_bytes"):
            RenderOptions(max_input_bytes=-1)

    def test_non_integer_limit(self):
        with pytest.raises(TypeError):
            RenderOptions(max_highlight_bytes="lots")  # type: ignore[arg-type]

    def test_invalid_wrapper_tag(self):
        with pytest.raises(ValueError, match="wrapper_tag"):
            RenderOptions(wrapper_tag='div class="x"')

    def test_renderer_rejects_wrong_options_type(self):
        with pytest.raises(TypeError, match="RenderOptions"):
            GitHubMarkdown(options={"breaks": True})  # type: ignore[arg-type]


class TestWrapper:
    def test_default_wrapper(self):
        html = GitHubMarkdown().render("text")
        assert html.startswith('<article class="markdown-body">')
        assert html.rstrip().endswith("</article>")

    def test_custom_wrapper_tag_and_class(self):
        renderer = GitHubMarkdown(
            RenderOptions(wrapper_tag="section", wrapper_class="md")
        )
        assert '<section class="md">' in renderer.render("text")

    def test_no_wrapper(self):
        html = GitHubMarkdown(RenderOptions(wrapper_tag="")).render("text")
        assert html == "<p>text</p>\n"


class TestBreaks:
    def test_soft_break_is_a_newline_by_default(self):
        assert "<br" not in GitHubMarkdown().render("a\nb")

    def test_breaks_option_emits_br(self):
        assert "<br" in GitHubMarkdown(RenderOptions(breaks=True)).render("a\nb")

    def test_two_space_hard_break_always_works(self):
        assert "<br" in GitHubMarkdown().render("a  \nb")

    def test_backslash_hard_break_always_works(self):
        assert "<br" in GitHubMarkdown().render("a\\\nb")


class TestTableOfContents:
    def test_returns_headings_in_order(self):
        toc = GitHubMarkdown().table_of_contents("# One\n\n## Two\n\n### Three\n")
        assert [entry["text"] for entry in toc] == ["One", "Two", "Three"]
        assert [entry["level"] for entry in toc] == ["h1", "h2", "h3"]

    def test_ids_match_the_rendered_output(self):
        renderer = GitHubMarkdown()
        source = "# Setup\n\n## Setup\n"
        toc = renderer.table_of_contents(source)
        html = renderer.render(source)
        for entry in toc:
            assert f'id="{entry["id"]}"' in html

    def test_max_level_filters_deeper_headings(self):
        toc = GitHubMarkdown().table_of_contents("# A\n\n#### B\n", max_level=2)
        assert [entry["text"] for entry in toc] == ["A"]

    def test_invalid_max_level(self):
        with pytest.raises(ValueError, match="max_level"):
            GitHubMarkdown().table_of_contents("# A\n", max_level=9)

    def test_env_receives_heading_metadata(self):
        env: dict = {}
        GitHubMarkdown().render("# Title\n", env=env)
        assert env["gh_headings"][0]["id"] == "title"


class TestPageRendering:
    def test_page_is_a_complete_document(self):
        page = GitHubMarkdown().render_page("# Hi", title="Demo")
        assert page.startswith("<!DOCTYPE html>")
        assert "<title>Demo</title>" in page
        assert page.rstrip().endswith("</html>")

    def test_title_is_escaped(self):
        page = GitHubMarkdown().render_page("x", title="<script>alert(1)</script>")
        assert "<script>alert(1)</script>" not in page
        assert "&lt;script&gt;" in page

    def test_linked_stylesheets_by_default(self):
        page = GitHubMarkdown().render_page("x")
        for name in STYLESHEET_NAMES:
            assert f'href="{name}"' in page

    def test_inline_css_embeds_both_stylesheets(self):
        page = GitHubMarkdown().render_page("x", inline_css=True)
        assert "<style>" in page
        assert "--gh-canvas-default" in page
        assert "--gh-syn-keyword" in page

    def test_custom_css_hrefs(self):
        page = GitHubMarkdown().render_page("x", css_hrefs=["/static/gh.css"])
        assert 'href="/static/gh.css"' in page

    @pytest.mark.parametrize(
        "theme, expected",
        [("light", 'data-theme="light"'), ("dark", 'data-theme="dark"')],
    )
    def test_pinned_themes(self, theme, expected):
        assert expected in GitHubMarkdown().render_page("x", theme=theme)

    def test_auto_theme_leaves_it_to_the_browser(self):
        page = GitHubMarkdown().render_page("x", theme="auto")
        assert "data-theme" not in page
        assert 'content="light dark"' in page

    def test_invalid_theme(self):
        with pytest.raises(ValueError, match="theme"):
            GitHubMarkdown().render_page("x", theme="neon")  # type: ignore[arg-type]

    def test_lang_attribute(self):
        assert 'lang="de"' in GitHubMarkdown().render_page("x", lang="de")


class TestAssets:
    def test_both_stylesheets_exist_and_are_not_empty(self):
        for path in GitHubMarkdown.asset_paths():
            assert path.exists(), f"missing stylesheet {path}"
            assert path.stat().st_size > 1000

    def test_stylesheets_returns_concatenated_css(self):
        css = GitHubMarkdown.stylesheets()
        assert ".markdown-body" in css and ".highlight .k" in css

    def test_write_assets_creates_the_directory(self, tmp_path):
        target = tmp_path / "nested" / "static"
        written = GitHubMarkdown.write_assets(target)
        assert len(written) == 2
        assert all(path.exists() for path in written)

    def test_write_assets_is_safe_to_rerun(self, tmp_path):
        GitHubMarkdown.write_assets(tmp_path)
        first = (tmp_path / STYLESHEET_NAMES[0]).read_text()
        GitHubMarkdown.write_assets(tmp_path)
        assert (tmp_path / STYLESHEET_NAMES[0]).read_text() == first

    def test_write_assets_leaves_no_temp_files(self, tmp_path):
        GitHubMarkdown.write_assets(tmp_path)
        assert not list(tmp_path.glob("*.tmp"))

    def test_overwrite_false_preserves_local_edits(self, tmp_path):
        GitHubMarkdown.write_assets(tmp_path)
        edited = tmp_path / STYLESHEET_NAMES[0]
        edited.write_text("/* my edits */")
        GitHubMarkdown.write_assets(tmp_path, overwrite=False)
        assert edited.read_text() == "/* my edits */"


class TestStylesheetCoverage:
    """The CSS is a deliverable too, so its correctness is asserted here."""

    def test_every_pygments_token_class_is_styled(self):
        css = (
            Path(GitHubMarkdown.asset_paths()[1]).read_text(encoding="utf-8")
        )
        styled = set(re.findall(r"\.highlight \.([a-z0-9]+)", css))
        missing = pygments_class_names() - styled
        assert not missing, f"unstyled Pygments classes: {sorted(missing)}"

    def test_both_themes_define_the_same_variables(self):
        css = Path(GitHubMarkdown.asset_paths()[1]).read_text(encoding="utf-8")
        blocks = css.split("[data-theme=\"dark\"] {")
        light_vars = set(re.findall(r"(--gh-syn-[a-z-]+):", blocks[0]))
        dark_vars = set(re.findall(r"(--gh-syn-[a-z-]+):", blocks[-1]))
        assert light_vars == dark_vars

    def test_body_stylesheet_defines_both_palettes(self):
        css = Path(GitHubMarkdown.asset_paths()[0]).read_text(encoding="utf-8")
        assert "prefers-color-scheme: dark" in css
        assert '[data-theme="dark"]' in css
        assert '[data-theme="light"]' in css


class TestCli:
    def test_renders_a_file_to_stdout(self, tmp_path, capsys):
        source = tmp_path / "doc.md"
        source.write_text("# Title\n", encoding="utf-8")
        assert main([str(source)]) == 0
        assert "<h1" in capsys.readouterr().out

    def test_writes_to_an_output_file(self, tmp_path):
        source = tmp_path / "doc.md"
        source.write_text("# Title\n", encoding="utf-8")
        out = tmp_path / "doc.html"
        main([str(source), "-o", str(out)])
        assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")

    def test_fragment_mode_omits_the_document_shell(self, tmp_path, capsys):
        source = tmp_path / "doc.md"
        source.write_text("# Title\n", encoding="utf-8")
        main([str(source), "--fragment"])
        out = capsys.readouterr().out
        assert "<!DOCTYPE" not in out and "markdown-body" in out

    def test_missing_file_exits_with_a_clear_message(self, tmp_path):
        with pytest.raises(SystemExit) as excinfo:
            main([str(tmp_path / "nope.md")])
        assert "not found" in str(excinfo.value)

    def test_directory_as_input_is_rejected(self, tmp_path):
        with pytest.raises(SystemExit) as excinfo:
            main([str(tmp_path)])
        assert "directory" in str(excinfo.value)

    def test_invalid_utf8_is_reported_not_crashed(self, tmp_path):
        source = tmp_path / "bad.md"
        source.write_bytes(b"\xff\xfe invalid")
        with pytest.raises(SystemExit) as excinfo:
            main([str(source)])
        assert "UTF-8" in str(excinfo.value)

    def test_write_assets_flag(self, tmp_path):
        source = tmp_path / "doc.md"
        source.write_text("# Title\n", encoding="utf-8")
        main([str(source), "-o", str(tmp_path / "o.html"), "--write-assets", str(tmp_path)])
        assert (tmp_path / STYLESHEET_NAMES[0]).exists()

    def test_stdin_input(self, tmp_path, monkeypatch, capsys):
        import io

        monkeypatch.setattr("sys.stdin", io.StringIO("# From stdin\n"))
        main(["-", "--fragment"])
        assert "From stdin" in capsys.readouterr().out

    def test_output_leaves_no_temp_file(self, tmp_path):
        source = tmp_path / "doc.md"
        source.write_text("# Title\n", encoding="utf-8")
        main([str(source), "-o", str(tmp_path / "doc.html")])
        assert not list(tmp_path.glob("*.tmp"))
