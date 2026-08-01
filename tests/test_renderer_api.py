"""The public API contract: options, assets, page output and the CLI."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from md_to_html_renderer import MarkdownRenderer, RenderOptions
from md_to_html_renderer.cli import main
from md_to_html_renderer.highlight import pygments_class_names
from md_to_html_renderer.palette import (
    PaletteError,
    available_palettes,
    build_css,
    load_palette,
    validate_palette,
)
from md_to_html_renderer.renderer import STRUCTURE_NAME


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
            MarkdownRenderer(options={"breaks": True})  # type: ignore[arg-type]


class TestWrapper:
    def test_default_wrapper(self):
        html = MarkdownRenderer().render("text")
        assert html.startswith('<article class="markdown-body">')
        assert html.rstrip().endswith("</article>")

    def test_custom_wrapper_tag_and_class(self):
        renderer = MarkdownRenderer(
            RenderOptions(wrapper_tag="section", wrapper_class="md")
        )
        assert '<section class="md">' in renderer.render("text")

    def test_no_wrapper(self):
        html = MarkdownRenderer(RenderOptions(wrapper_tag="")).render("text")
        assert html == "<p>text</p>\n"


class TestBreaks:
    def test_soft_break_is_a_newline_by_default(self):
        assert "<br" not in MarkdownRenderer().render("a\nb")

    def test_breaks_option_emits_br(self):
        assert "<br" in MarkdownRenderer(RenderOptions(breaks=True)).render("a\nb")

    def test_two_space_hard_break_always_works(self):
        assert "<br" in MarkdownRenderer().render("a  \nb")

    def test_backslash_hard_break_always_works(self):
        assert "<br" in MarkdownRenderer().render("a\\\nb")


class TestTableOfContents:
    def test_returns_headings_in_order(self):
        toc = MarkdownRenderer().table_of_contents("# One\n\n## Two\n\n### Three\n")
        assert [entry["text"] for entry in toc] == ["One", "Two", "Three"]
        assert [entry["level"] for entry in toc] == ["h1", "h2", "h3"]

    def test_ids_match_the_rendered_output(self):
        renderer = MarkdownRenderer()
        source = "# Setup\n\n## Setup\n"
        toc = renderer.table_of_contents(source)
        html = renderer.render(source)
        for entry in toc:
            assert f'id="{entry["id"]}"' in html

    def test_max_level_filters_deeper_headings(self):
        toc = MarkdownRenderer().table_of_contents("# A\n\n#### B\n", max_level=2)
        assert [entry["text"] for entry in toc] == ["A"]

    def test_invalid_max_level(self):
        with pytest.raises(ValueError, match="max_level"):
            MarkdownRenderer().table_of_contents("# A\n", max_level=9)

    def test_env_receives_heading_metadata(self):
        env: dict = {}
        MarkdownRenderer().render("# Title\n", env=env)
        assert env["gh_headings"][0]["id"] == "title"


class TestPageRendering:
    def test_page_is_a_complete_document(self):
        page = MarkdownRenderer().render_page("# Hi", title="Demo")
        assert page.startswith("<!DOCTYPE html>")
        assert "<title>Demo</title>" in page
        assert page.rstrip().endswith("</html>")

    def test_title_is_escaped(self):
        page = MarkdownRenderer().render_page("x", title="<script>alert(1)</script>")
        assert "<script>alert(1)</script>" not in page
        assert "&lt;script&gt;" in page

    def test_linked_stylesheets_by_default(self):
        page = MarkdownRenderer().render_page("x")
        assert 'href="palettes/github.css"' in page
        assert f'href="{STRUCTURE_NAME}"' in page

    def test_inline_css_embeds_palette_and_structure(self):
        page = MarkdownRenderer().render_page("x", inline_css=True)
        assert "<style>" in page
        assert "--md-canvas-default" in page   # palette
        assert "--md-syn-keyword" in page      # palette
        assert ".markdown-body" in page        # structure

    def test_custom_css_hrefs(self):
        page = MarkdownRenderer().render_page("x", css_hrefs=["/static/gh.css"])
        assert 'href="/static/gh.css"' in page

    @pytest.mark.parametrize(
        "theme, expected",
        [("light", 'data-theme="light"'), ("dark", 'data-theme="dark"')],
    )
    def test_pinned_themes(self, theme, expected):
        assert expected in MarkdownRenderer().render_page("x", theme=theme)

    def test_auto_theme_leaves_it_to_the_browser(self):
        page = MarkdownRenderer().render_page("x", theme="auto")
        assert "data-theme" not in page
        assert 'content="light dark"' in page

    def test_invalid_theme(self):
        with pytest.raises(ValueError, match="theme"):
            MarkdownRenderer().render_page("x", theme="neon")  # type: ignore[arg-type]

    def test_lang_attribute(self):
        assert 'lang="de"' in MarkdownRenderer().render_page("x", lang="de")


class TestAssets:
    def test_stylesheets_exist_and_are_not_empty(self):
        for path in MarkdownRenderer().asset_paths():
            assert path.exists(), f"missing stylesheet {path}"
            assert path.stat().st_size > 500

    def test_stylesheets_returns_concatenated_css(self):
        css = MarkdownRenderer().stylesheets()
        assert ".markdown-body" in css and ".highlight .k" in css

    def test_multiple_palettes_can_be_shipped_together(self):
        renderer = MarkdownRenderer()
        css = renderer.stylesheets(palettes=["github", "skeleton"])
        assert '[data-palette="github"]' in css
        assert '[data-palette="skeleton"]' in css

    def test_write_assets_creates_the_directory(self, tmp_path):
        target = tmp_path / "nested" / "static"
        written = MarkdownRenderer().write_assets(target)
        assert len(written) == 2
        assert all(path.exists() for path in written)

    def test_write_assets_mirrors_the_palettes_subdirectory(self, tmp_path):
        """Relative hrefs only work if the layout on disk matches css_hrefs."""
        renderer = MarkdownRenderer()
        renderer.write_assets(tmp_path)
        for href in renderer.css_hrefs():
            assert (tmp_path / href).exists(), f"{href} not written"

    def test_write_assets_is_safe_to_rerun(self, tmp_path):
        MarkdownRenderer().write_assets(tmp_path)
        first = (tmp_path / STRUCTURE_NAME).read_text()
        MarkdownRenderer().write_assets(tmp_path)
        assert (tmp_path / STRUCTURE_NAME).read_text() == first

    def test_write_assets_leaves_no_temp_files(self, tmp_path):
        MarkdownRenderer().write_assets(tmp_path)
        assert not list(tmp_path.rglob("*.tmp"))

    def test_overwrite_false_preserves_local_edits(self, tmp_path):
        MarkdownRenderer().write_assets(tmp_path)
        edited = tmp_path / STRUCTURE_NAME
        edited.write_text("/* my edits */")
        MarkdownRenderer().write_assets(tmp_path, overwrite=False)
        assert edited.read_text() == "/* my edits */"


class TestStylesheetCoverage:
    """The CSS is a deliverable too, so its correctness is asserted here."""

    def test_every_pygments_token_class_is_styled(self):
        css = Path(MarkdownRenderer.structure_css()).read_text(encoding="utf-8")
        styled = set(re.findall(r"\.highlight \.([a-z0-9]+)", css))
        missing = pygments_class_names() - styled
        assert not missing, f"unstyled Pygments classes: {sorted(missing)}"



    def test_no_css_variable_is_used_without_being_defined(self):
        """An undefined variable silently falls back to its literal default (or
        to nothing), which is exactly the kind of bug that only shows up in one
        theme. Catch it statically instead."""
        css = "".join(
            path.read_text(encoding="utf-8") for path in MarkdownRenderer().asset_paths()
        )
        used = set(re.findall(r"var\((--md-[a-z0-9-]+)", css))
        defined = set(re.findall(r"^\s*(--md-[a-z0-9-]+):", css, re.M))
        assert not used - defined, f"undefined CSS variables: {sorted(used - defined)}"

    def test_page_shell_only_uses_tokens_the_palette_defines(self):
        """The standalone-page shell is CSS too, and is easy to forget when
        tokens are renamed."""
        from md_to_html_renderer.templates import PAGE_SHELL_CSS

        used = set(re.findall(r"var\((--md-[a-z0-9-]+)", PAGE_SHELL_CSS))
        defined = set(
            re.findall(
                r"^\s*(--md-[a-z0-9-]+):",
                MarkdownRenderer().stylesheets(),
                re.M,
            )
        )
        assert not used - defined, f"page shell uses undefined: {sorted(used - defined)}"

    def test_structure_stylesheet_contains_no_colour_values(self):
        """The whole point of the split: if a colour leaks into the structural
        sheet, that colour is wrong in at least one palette."""
        css = Path(MarkdownRenderer.structure_css()).read_text(encoding="utf-8")
        css = css.split("@media print")[0]        # print is deliberately mono
        leaks = re.findall(r"^.*#[0-9a-fA-F]{3,8}\b.*$", css, re.M)
        leaks = [line for line in leaks if not line.strip().startswith(("*", "/*"))]
        assert not leaks, f"colour literals in structure: {leaks}"



    @pytest.mark.parametrize("name", sorted(available_palettes()))
    def test_every_palette_covers_all_three_theme_states(self, name):
        css = MarkdownRenderer(RenderOptions(palette=name)).stylesheets()
        assert "prefers-color-scheme: dark" in css
        assert f'[data-palette="{name}"][data-theme="dark"]' in css
        assert ":root:not([data-palette])" in css


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
        assert (tmp_path / STRUCTURE_NAME).exists()
        assert (tmp_path / "palettes" / "github.css").exists()

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
