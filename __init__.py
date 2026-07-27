"""GitHub-flavoured Markdown to HTML rendering with GitHub's exact visual style.

Typical use::

    from github_markdown import GitHubMarkdown

    renderer = GitHubMarkdown()
    fragment = renderer.render("# Hello *world*")
    page = renderer.render_page("# Hello", title="Demo", inline_css=True)

The rendered fragment is wrapped in ``<article class="markdown-body">`` and is
styled by the two bundled stylesheets (see :meth:`GitHubMarkdown.asset_paths`).
"""

from .options import AnchorStyle, RenderOptions, Theme
from .renderer import GitHubMarkdown
from .slugger import Slugger, slugify

__all__ = [
    "AnchorStyle",
    "GitHubMarkdown",
    "RenderOptions",
    "Slugger",
    "Theme",
    "slugify",
    "__version__",
]

__version__ = "1.0.0"
