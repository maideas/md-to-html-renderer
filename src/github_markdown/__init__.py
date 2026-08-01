"""GitHub-flavoured Markdown to HTML rendering with GitHub's exact visual style.

Typical use::

    from github_markdown import GitHubMarkdown

    renderer = GitHubMarkdown()
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
from .renderer import GitHubMarkdown
from .slugger import Slugger, slugify

__all__ = [
    "AnchorStyle",
    "GitHubMarkdown",
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

__version__ = "2.1.0"
