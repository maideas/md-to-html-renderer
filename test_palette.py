"""The palette system: loading, validation, generation and selector behaviour."""

from __future__ import annotations

import json
import re

import pytest

from github_markdown import GitHubMarkdown, RenderOptions
from github_markdown.palette import (
    TOKEN_PREFIX,
    PaletteError,
    available_palettes,
    build_css,
    load_palette,
    palette_css_path,
    validate_palette,
    write_palette_css,
)


@pytest.fixture
def minimal_palette():
    return {
        "name": "test",
        "label": "Test",
        "base": {"radius": "4px"},
        "light": {"canvas-default": "#ffffff", "fg-default": "#000000"},
        "dark": {"canvas-default": "#000000", "fg-default": "#ffffff"},
    }


class TestBundledPalettes:
    def test_github_and_skeleton_are_available(self):
        assert {"github", "skeleton"} <= set(available_palettes())

    @pytest.mark.parametrize("name", sorted(available_palettes()))
    def test_every_bundled_palette_validates(self, name):
        validate_palette(load_palette(name), origin=name)

    @pytest.mark.parametrize("name", sorted(available_palettes()))
    def test_every_bundled_palette_has_a_compiled_stylesheet(self, name):
        assert palette_css_path(name).exists()

    @pytest.mark.parametrize("name", sorted(available_palettes()))
    def test_compiled_css_is_current(self, name):
        """Catches a JSON edit that was never recompiled -- otherwise the
        stylesheet silently lags behind its source."""
        assert palette_css_path(name).read_text(encoding="utf-8") == build_css(
            load_palette(name)
        )

    def test_all_palettes_define_the_same_token_set(self):
        """A palette missing a token that another defines leaves that element
        unstyled when you switch to it."""
        token_sets = {
            name: set(load_palette(name)["light"]) for name in available_palettes()
        }
        reference_name, reference = next(iter(token_sets.items()))
        for name, tokens in token_sets.items():
            assert tokens == reference, (
                f"{name} differs from {reference_name}: "
                f"missing {sorted(reference - tokens)}, extra {sorted(tokens - reference)}"
            )

    def test_skeleton_covers_every_token_the_structure_uses(self):
        """The skeleton is the template for new palettes, so it must be
        complete or a new palette starts out broken."""
        structure = GitHubMarkdown.structure_css().read_text(encoding="utf-8")
        used = {
            name.removeprefix(TOKEN_PREFIX)
            for name in re.findall(r"var\((--md-[a-z0-9-]+)", structure)
        }
        skeleton = load_palette("skeleton")
        defined = set(skeleton["light"]) | set(skeleton.get("base", {}))
        assert not used - defined, f"skeleton is missing: {sorted(used - defined)}"


class TestValidation:
    def test_accepts_a_minimal_palette(self, minimal_palette):
        validate_palette(minimal_palette)

    def test_rejects_a_non_object(self):
        with pytest.raises(PaletteError, match="JSON object"):
            validate_palette(["not", "a", "dict"])

    @pytest.mark.parametrize("name", ["", "Has Spaces", "UPPER", "9leading", "x" * 40])
    def test_rejects_bad_names(self, minimal_palette, name):
        minimal_palette["name"] = name
        with pytest.raises(PaletteError, match="name"):
            validate_palette(minimal_palette)

    def test_rejects_missing_mode(self, minimal_palette):
        del minimal_palette["dark"]
        with pytest.raises(PaletteError, match="dark"):
            validate_palette(minimal_palette)

    def test_rejects_empty_mode(self, minimal_palette):
        minimal_palette["light"] = {}
        with pytest.raises(PaletteError, match="light"):
            validate_palette(minimal_palette)

    def test_rejects_mismatched_token_sets(self, minimal_palette):
        """The bug this exists to prevent: a token defined only for light keeps
        its light value on a dark background."""
        minimal_palette["dark"].pop("fg-default")
        with pytest.raises(PaletteError, match="same tokens"):
            validate_palette(minimal_palette)

    def test_error_names_the_offending_tokens(self, minimal_palette):
        minimal_palette["dark"].pop("fg-default")
        with pytest.raises(PaletteError, match="fg-default"):
            validate_palette(minimal_palette)

    @pytest.mark.parametrize(
        "value",
        [
            "#fff; } body { display: none",
            "red } .x { color: blue",
            "url(x) /* comment",
            "@import url(evil.css)",
            "expression(alert(1))",
            "<script>",
        ],
    )
    def test_rejects_values_that_could_break_out_of_a_declaration(
        self, minimal_palette, value
    ):
        """Palette files may come from elsewhere; a value is interpolated
        straight into CSS, so it must not be able to close the block."""
        minimal_palette["light"]["canvas-default"] = value
        minimal_palette["dark"]["canvas-default"] = value
        with pytest.raises(PaletteError, match="break out|invalid"):
            validate_palette(minimal_palette)

    def test_rejects_non_string_value(self, minimal_palette):
        minimal_palette["light"]["canvas-default"] = 255
        with pytest.raises(PaletteError, match="non-empty string"):
            validate_palette(minimal_palette)

    def test_rejects_bad_token_name(self, minimal_palette):
        minimal_palette["light"]["Bad Token"] = "#fff"
        minimal_palette["dark"]["Bad Token"] = "#000"
        with pytest.raises(PaletteError, match="invalid token name"):
            validate_palette(minimal_palette)


class TestLoading:
    def test_unknown_name_lists_the_alternatives(self):
        with pytest.raises(PaletteError, match="Bundled palettes"):
            load_palette("nonexistent")

    def test_missing_file_path(self, tmp_path):
        with pytest.raises(PaletteError, match="not found"):
            load_palette(tmp_path / "absent.json")

    def test_malformed_json_is_reported_clearly(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{ not json", encoding="utf-8")
        with pytest.raises(PaletteError, match="not valid JSON"):
            load_palette(path)

    def test_loads_a_palette_from_an_arbitrary_path(self, tmp_path, minimal_palette):
        path = tmp_path / "test.json"
        path.write_text(json.dumps(minimal_palette), encoding="utf-8")
        assert load_palette(path)["name"] == "test"


class TestGeneration:
    def test_emits_all_three_theme_states(self, minimal_palette):
        css = build_css(minimal_palette)
        assert ":root:not([data-palette])" in css
        assert "@media (prefers-color-scheme: dark)" in css
        assert '[data-palette="test"][data-theme="dark"]' in css

    def test_tokens_are_prefixed(self, minimal_palette):
        assert "--md-canvas-default: #ffffff;" in build_css(minimal_palette)

    def test_base_tokens_appear_once(self, minimal_palette):
        assert build_css(minimal_palette).count("--md-radius:") == 1

    def test_dark_values_appear_in_both_dark_blocks(self, minimal_palette):
        """Once for the OS-driven case, once for the pinned case."""
        assert build_css(minimal_palette).count("--md-canvas-default: #000000;") == 2

    def test_explicit_light_survives_an_os_dark_preference(self, minimal_palette):
        """The dark rules must exclude data-theme="light", or pinning light
        would be ignored on a dark-mode machine."""
        media_block = build_css(minimal_palette).split(
            "@media (prefers-color-scheme: dark)"
        )[1]
        assert ':not([data-theme="light"])' in media_block

    def test_default_selector_outranks_a_bare_palette_attribute(self, minimal_palette):
        """:root:not([data-palette]) is (0,2,0) against [data-palette=x] at
        (0,1,0), so an explicit attribute always beats the implicit default
        even when several palettes are loaded."""
        css = build_css(minimal_palette)
        assert ":root:not([data-palette])," in css

    def test_generation_validates_first(self, minimal_palette):
        minimal_palette["dark"].pop("fg-default")
        with pytest.raises(PaletteError):
            build_css(minimal_palette)

    def test_write_is_atomic_and_leaves_no_temp_file(self, tmp_path, minimal_palette):
        source = tmp_path / "test.json"
        source.write_text(json.dumps(minimal_palette), encoding="utf-8")
        written = write_palette_css(source, tmp_path / "test.css")
        assert written.exists()
        assert not list(tmp_path.glob("*.tmp"))


class TestRendererIntegration:
    def test_default_palette_is_github(self):
        assert "github.css" in GitHubMarkdown().css_hrefs()[0]

    def test_selecting_a_palette(self):
        renderer = GitHubMarkdown(RenderOptions(palette="skeleton"))
        assert "skeleton.css" in renderer.css_hrefs()[0]

    def test_unknown_palette_fails_at_construction_not_at_render(self):
        """A typo should surface at startup, not on the first page view."""
        with pytest.raises(ValueError, match="unknown palette"):
            GitHubMarkdown(RenderOptions(palette="typo"))

    def test_palette_choice_does_not_change_the_html(self):
        """The whole point: retheming is CSS only. Identical markup means you
        can switch palette without re-rendering anything."""
        source = "# Title\n\n```python\nx = 1\n```\n"
        github = GitHubMarkdown(RenderOptions(palette="github")).render(source)
        skeleton = GitHubMarkdown(RenderOptions(palette="skeleton")).render(source)
        assert github == skeleton

    def test_data_palette_omitted_for_a_single_palette(self):
        """A lone palette claims :root, so the attribute would be noise."""
        assert "data-palette" not in GitHubMarkdown().render_page("x")

    def test_data_palette_emitted_when_several_are_loaded(self):
        page = GitHubMarkdown().render_page("x", palettes=["github", "skeleton"])
        assert 'data-palette="github"' in page

    def test_data_palette_can_be_forced(self):
        renderer = GitHubMarkdown(RenderOptions(emit_palette_attribute=True))
        assert 'data-palette="github"' in renderer.render_page("x")

    def test_custom_palette_file_end_to_end(self, tmp_path, minimal_palette):
        """A palette living entirely outside the package still works."""
        minimal_palette["light"] = dict(load_palette("github")["light"])
        minimal_palette["dark"] = dict(load_palette("github")["dark"])
        minimal_palette["base"] = dict(load_palette("github")["base"])
        source = tmp_path / "mine.json"
        source.write_text(json.dumps(minimal_palette), encoding="utf-8")
        write_palette_css(source, tmp_path / "mine.css")

        renderer = GitHubMarkdown(RenderOptions(palette=str(source)))
        page = renderer.render_page("# Hi", inline_css=True)
        assert '[data-palette="test"]' in page
        assert "--md-canvas-default" in page
