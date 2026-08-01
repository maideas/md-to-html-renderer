"""Colour contrast gates for every bundled palette.

A palette is data, so nothing stops a future one from pairing grey text with a
grey background. These tests compute WCAG 2.1 contrast ratios and fail if a
palette drops below the floor the bundled palettes already clear.

Template palettes (``"template": true``) are exempt: their placeholder values
are deliberately unreadable so an unfilled token is obvious.
"""

from __future__ import annotations

import pytest

from md_to_html_renderer.palette import available_palettes, load_palette

#: Body text must be comfortably readable: WCAG AA for normal text.
MIN_BODY_CONTRAST = 4.5

#: Syntax tokens and muted text sit slightly lower. GitHub's own palette floors
#: at 3.74 (dark markup-heading), so 3.5 is the highest bar every bundled
#: palette actually clears.
MIN_ACCENT_CONTRAST = 3.5

REAL_PALETTES = sorted(
    name for name in available_palettes() if not load_palette(name).get("template")
)


def _rgb(value: str, backdrop: tuple[int, int, int] = (255, 255, 255)):
    """Parse #rgb / #rrggbb / #rrggbbaa, compositing alpha over ``backdrop``."""
    digits = value.strip().lstrip("#")
    if len(digits) == 3:
        digits = "".join(char * 2 for char in digits)
    red, green, blue = (int(digits[i : i + 2], 16) for i in (0, 2, 4))
    alpha = int(digits[6:8], 16) / 255 if len(digits) == 8 else 1.0
    return tuple(
        round(channel * alpha + back * (1 - alpha))
        for channel, back in zip((red, green, blue), backdrop)
    )


def _luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        srgb = value / 255
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(v) for v in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(foreground: str, background: tuple[int, int, int]) -> float:
    """WCAG 2.1 contrast ratio, 1.0 (invisible) to 21.0 (black on white)."""
    first, second = _luminance(_rgb(foreground, background)), _luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("name", REAL_PALETTES)
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_body_text_meets_wcag_aa(name, mode):
    tokens = load_palette(name)[mode]
    canvas = _rgb(tokens["canvas-default"])
    ratio = contrast(tokens["fg-default"], canvas)
    assert ratio >= MIN_BODY_CONTRAST, (
        f"{name}/{mode}: body text is {ratio:.2f}:1, below {MIN_BODY_CONTRAST}"
    )


@pytest.mark.parametrize("name", REAL_PALETTES)
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_semantic_foregrounds_are_legible(name, mode):
    tokens = load_palette(name)[mode]
    canvas = _rgb(tokens["canvas-default"])
    for token in ("fg-muted", "accent-fg", "danger-fg", "success-fg",
                  "attention-fg", "done-fg"):
        ratio = contrast(tokens[token], canvas)
        assert ratio >= MIN_ACCENT_CONTRAST, (
            f"{name}/{mode}: {token} is {ratio:.2f}:1, below {MIN_ACCENT_CONTRAST}"
        )


@pytest.mark.parametrize("name", REAL_PALETTES)
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_syntax_tokens_are_legible_on_their_background(name, mode):
    """Most syntax colours sit on the code surface; a few ship their own
    background and are judged against that instead."""
    tokens = load_palette(name)[mode]
    canvas = _rgb(tokens["canvas-default"])
    code_surface = _rgb(tokens["canvas-subtle"], canvas)

    failures = []
    for token, value in tokens.items():
        if not token.startswith("syn-") or token.endswith("-bg"):
            continue
        if "sublimelinter" in token:  # a gutter mark, never text
            continue
        paired = tokens.get(token.replace("-text", "-bg")) if token.endswith("-text") else None
        background = _rgb(paired, canvas) if paired else code_surface
        ratio = contrast(value, background)
        if ratio < MIN_ACCENT_CONTRAST:
            failures.append(f"{token} {ratio:.2f}:1")
    assert not failures, f"{name}/{mode}: illegible syntax tokens: {failures}"


def test_light_and_dark_are_actually_different():
    """A copy-paste slip that leaves both modes identical would otherwise pass
    every other test in the suite."""
    for palette_name in REAL_PALETTES:
        palette = load_palette(palette_name)
        assert palette["light"] != palette["dark"], (
            f"{palette_name}: light and dark are identical"
        )
