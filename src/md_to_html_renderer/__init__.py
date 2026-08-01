"""Extensible Markdown to HTML renderer with pluggable palettes.

Renders GitHub-Flavoured Markdown to sanitised HTML with syntax
highlighting. The visual style is palette-driven: the bundled ``github``
palette matches GitHub's exact look, and additional styles (e.g.
``claude``, or your own) can be added as data, not code.

Typical use::

    from md_to_html_renderer import MarkdownRenderer

    renderer = MarkdownRenderer()
    fragment = renderer.render("# Hello *world*")
    page = renderer.render_page("# Hello", title="Demo", inline_css=True)

The rendered fragment is wrapped in ``<article class="markdown-body">``. Styling
comes from two stylesheets: ``markdown.css``, which holds every rule and no
colours, plus one palette from ``static/palettes/``. Adding a theme is a data
edit, not a code change -- see ``palettes/skeleton.json``.
"""

from .options import AnchorStyle, RenderOptions, Theme
from .palette import (
    PaletteError,
    available_palettes,
    build_css,
    load_palette,
    write_palette_css,
)
from .renderer import MarkdownRenderer
from .slugger import Slugger, slugify

__all__ = [
    "AnchorStyle",
    "MarkdownRenderer",
    "PaletteError",
    "RenderOptions",
    "Slugger",
    "Theme",
    "available_palettes",
    "build_css",
    "load_palette",
    "slugify",
    "write_palette_css",
    "__version__",
]

__version__ = "3.0.0"
