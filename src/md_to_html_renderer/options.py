"""Configuration for :class:`md_to_html_renderer.MarkdownRenderer`."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

#: Where the ``id`` used by heading anchors is placed.
#:
#: ``"heading"``
#:     ``<h2 id="slug"><a class="anchor" href="#slug">…</a>Title</h2>``.
#:     Visually identical to GitHub and works in a standalone page.
#: ``"github"``
#:     ``<h2><a id="user-content-slug" class="anchor" href="#slug">…</a>Title</h2>``.
#:     Byte-for-byte closer to github.com, but in-page links only resolve if the
#:     host page runs GitHub's fragment-rewriting script.
#: ``"none"``
#:     No anchor link, no id.
AnchorStyle = Literal["heading", "github", "none"]

#: Colour scheme baked into a standalone page.
#:
#: ``"auto"`` follows ``prefers-color-scheme``; ``"light"``/``"dark"`` pin it.
Theme = Literal["auto", "light", "dark"]

#: Refuse inputs above this size unless the caller raises the limit.
#: Markdown is superlinear in a few pathological cases, so an explicit ceiling
#: keeps a hostile document from becoming a denial of service.
DEFAULT_MAX_INPUT_BYTES = 8 * 1024 * 1024  # 8 MiB

#: Code blocks larger than this are emitted unhighlighted. Pygments is roughly
#: linear but with a large constant; a 5 MiB minified bundle in a fenced block
#: should not stall the request.
DEFAULT_MAX_HIGHLIGHT_BYTES = 256 * 1024  # 256 KiB


@dataclass(frozen=True)
class RenderOptions:
    """Immutable render configuration.

    Every field maps to one observable behaviour of the renderer. Defaults
    reproduce how GitHub renders a ``.md`` file in a repository.
    """

    # --- Parsing -----------------------------------------------------------
    linkify: bool = True
    """Turn bare URLs and ``www.`` hosts into links, as GFM autolinking does."""

    breaks: bool = False
    """Render a single newline as ``<br>``.

    GitHub does this in *comments* (issues, PRs) but not in ``.md`` files.
    Set ``True`` to match comment rendering.
    """

    typographer: bool = False
    """Smart quotes and dashes. GitHub does not do this; leave ``False``."""

    strikethrough_single_tilde: bool = True
    """Treat ``~x~`` as strikethrough in addition to ``~~x~~`` (GFM does)."""

    tables: bool = True
    tasklists: bool = True
    tasklists_editable: bool = False
    """Leave checkboxes interactive instead of ``disabled``."""

    footnotes: bool = True
    alerts: bool = True
    """Support ``> [!NOTE]`` … ``> [!CAUTION]`` callouts."""

    emoji: bool = True
    """Replace ``:shortcode:`` with the emoji character. Needs the ``emoji``
    package; silently inert if it is not installed."""

    math: bool = False
    """Emit ``$…$`` / ``$$…$$`` as KaTeX-ready markup.

    Off by default because rendering it requires loading KaTeX in the host page.
    """

    strip_front_matter: bool = True
    """Drop a leading YAML ``---`` block instead of rendering it."""

    # --- Output ------------------------------------------------------------
    palette: str = "github"
    """Colour palette: a bundled name (``"github"``) or a path to your own
    palette JSON. See ``static/palettes/skeleton.json`` for a template."""

    emit_palette_attribute: bool = False
    """Add ``data-palette`` to standalone pages. Only needed when more than one
    palette stylesheet is loaded at once; a lone palette claims ``:root``."""

    anchor_style: AnchorStyle = "heading"
    heading_id_prefix: str = ""
    """Prefix for generated heading ids. GitHub uses ``"user-content-"`` to
    avoid collisions with the surrounding page; set it if you embed untrusted
    documents in an app that has its own ids."""

    fragment_id_prefix: str = ""
    """Prefix for footnote ids, which are just as collision-prone as headings.
    Useful when several documents share one page."""

    highlight: bool = True
    """Syntax-highlight fenced code blocks with Pygments."""

    highlight_guess_language: bool = False
    """Guess the language of fences that have no info string. Off by default:
    Pygments' guesser is unreliable on short snippets and GitHub does not guess."""

    wrapper_tag: str = "article"
    """Element wrapped around the output. Set to ``""`` for a bare fragment."""

    wrapper_class: str = "markdown-body"

    link_rel: str = "nofollow noopener noreferrer"
    """``rel`` applied to outbound links, mirroring GitHub's ``nofollow``."""

    absolute_links_only_rel: bool = True
    """Only apply ``link_rel`` to absolute URLs, leaving in-document anchors alone."""

    # --- Safety ------------------------------------------------------------
    allow_html: bool = True
    """Let raw HTML through the parser. When ``False`` it is escaped and shown
    as literal text."""

    sanitize: bool = True
    """Run the output through an HTML sanitiser.

    Leave this on for any content you did not write yourself. Turning it off
    means a document can inject scripts into your page.
    """

    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES
    max_highlight_bytes: int = DEFAULT_MAX_HIGHLIGHT_BYTES

    extra_allowed_tags: frozenset[str] = field(default_factory=frozenset)
    """Additional tags the sanitiser should keep (e.g. ``{"iframe"}``)."""

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.anchor_style not in ("heading", "github", "none"):
            raise ValueError(
                f"anchor_style must be 'heading', 'github' or 'none', "
                f"got {self.anchor_style!r}"
            )
        for name in ("max_input_bytes", "max_highlight_bytes"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an int, got {type(value).__name__}")
            if value < 0:
                raise ValueError(f"{name} must be >= 0, got {value}")
        if not isinstance(self.wrapper_tag, str):
            raise TypeError("wrapper_tag must be a string")
        if self.wrapper_tag and not self.wrapper_tag.isalnum():
            raise ValueError(
                f"wrapper_tag must be a bare alphanumeric tag name, "
                f"got {self.wrapper_tag!r}"
            )
        for name in ("heading_id_prefix", "fragment_id_prefix"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
        if not isinstance(self.palette, (str, Path)):
            raise TypeError(
                f"palette must be a name or path, got {type(self.palette).__name__}"
            )
        if not isinstance(self.extra_allowed_tags, (frozenset, set)):
            raise TypeError("extra_allowed_tags must be a set of tag names")
        object.__setattr__(self, "extra_allowed_tags", frozenset(self.extra_allowed_tags))

    def evolve(self, **changes: object) -> RenderOptions:
        """Return a copy with ``changes`` applied, re-validated."""
        return replace(self, **changes)  # type: ignore[arg-type]


#: Matches how GitHub renders issue/PR comments rather than repository files.
COMMENT_PRESET = RenderOptions(breaks=True, heading_id_prefix="user-content-")

#: Renders with the skeleton palette, which is deliberately garish so that any
#: token you have not filled in is impossible to miss.
SKELETON_PRESET = RenderOptions(palette="skeleton")

#: Trusted-input preset: raw HTML passes through untouched. Only use this on
#: Markdown you control.
TRUSTED_PRESET = RenderOptions(sanitize=False, link_rel="")
