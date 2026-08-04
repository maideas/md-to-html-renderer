"""HTML sanitisation for rendered Markdown.

Markdown permits raw HTML, so any document you did not write yourself is an
XSS vector. GitHub solves this by running the rendered HTML through an
allowlist filter; this module does the same using `nh3`_ (Rust ``ammonia``
bindings).

The allowlist is GitHub's, extended with the few elements this renderer itself
generates: the anchor/alert ``<svg>`` icons and the ``<span>`` wrappers Pygments
emits.

If ``nh3`` is not installed, :func:`sanitize` raises. The renderer catches that
at construction time and degrades to *escaping* all raw HTML, which is safe --
never to passing it through.

.. _nh3: https://pypi.org/project/nh3/
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

try:  # pragma: no cover - trivial import shim
    import nh3

    HAVE_NH3 = True
except ImportError:  # pragma: no cover
    nh3 = None  # type: ignore[assignment]
    HAVE_NH3 = False


#: Elements GitHub keeps in user content, plus the SVG subset used by our icons.
ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        # Sectioning and text
        "h1", "h2", "h3", "h4", "h5", "h6",
        "p", "div", "span", "blockquote", "pre", "code", "br", "hr",
        "article", "section", "details", "summary",
        # Inline formatting
        "a", "b", "i", "strong", "em", "s", "del", "ins", "mark", "small",
        "sub", "sup", "abbr", "cite", "q", "dfn", "kbd", "samp", "var",
        "time", "ruby", "rt", "rp", "bdi", "bdo", "wbr",
        # Lists
        "ul", "ol", "li", "dl", "dt", "dd",
        # Tables
        "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
        "colgroup", "col",
        # Media
        "img", "picture", "source", "video", "audio", "track",
        # Form controls: only the disabled checkboxes of task lists survive,
        # thanks to the attribute allowlist below.
        "input",
        # Icons we generate for heading anchors and alerts
        "svg", "path", "g", "circle", "rect", "polygon", "line", "polyline",
    }
)

#: Tags whose *contents* are discarded as well as the tag itself.
CLEAN_CONTENT_TAGS: frozenset[str] = frozenset(
    {"script", "style", "title", "textarea", "iframe", "noscript",
     "noembed", "noframes", "plaintext", "xmp", "template", "object", "embed"}
)

#: Per-tag attribute allowlist. Nothing here can execute JavaScript: no
#: ``on*`` handlers, no ``style``, no ``href`` on anything but ``<a>``.
ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "*": {"class", "id", "title", "dir", "lang", "role", "aria-hidden",
          "aria-label", "aria-labelledby", "aria-describedby", "tabindex"},
    # ``target`` is deliberately absent: without it a document cannot open a
    # new tab, which removes the reverse-tabnabbing vector entirely.
    "a": {"href", "rel", "name"},
    "img": {"src", "srcset", "alt", "width", "height", "loading", "decoding",
            "align"},
    "source": {"src", "srcset", "type", "media", "sizes"},
    "video": {"src", "poster", "controls", "width", "height", "muted",
              "loop", "playsinline"},
    "audio": {"src", "controls", "loop", "muted"},
    "track": {"src", "kind", "srclang", "label", "default"},
    "input": {"type", "checked", "disabled"},
    "th": {"align", "colspan", "rowspan", "scope", "headers"},
    "td": {"align", "colspan", "rowspan", "headers"},
    "col": {"align", "span", "width"},
    "colgroup": {"align", "span", "width"},
    "ol": {"start", "reversed", "type"},
    "li": {"value"},
    "blockquote": {"cite"},
    "q": {"cite"},
    "ins": {"cite", "datetime"},
    "del": {"cite", "datetime"},
    "time": {"datetime"},
    "abbr": {"title"},
    "bdo": {"dir"},
    "details": {"open"},
    # Feeds the language label on highlighted code blocks.
    "pre": {"data-lang"},
    # The icon markup we emit ourselves.
    "svg": {"viewBox", "viewbox", "width", "height", "version", "fill",
            "xmlns", "focusable", "preserveAspectRatio"},
    "path": {"d", "fill", "fill-rule", "clip-rule"},
    "g": {"fill", "transform"},
    "circle": {"cx", "cy", "r", "fill"},
    "rect": {"x", "y", "width", "height", "rx", "ry", "fill"},
    "line": {"x1", "y1", "x2", "y2", "stroke"},
    "polygon": {"points", "fill"},
    "polyline": {"points", "fill", "stroke"},
}

#: URL schemes permitted in ``href``/``src``. Deliberately excludes
#: ``javascript:``, ``vbscript:``, ``data:`` and ``file:``.
ALLOWED_URL_SCHEMES: frozenset[str] = frozenset(
    {"http", "https", "mailto", "tel", "ftp", "ftps", "irc", "ircs", "news",
     "nntp", "sms", "xmpp", "matrix", "magnet", "bitcoin", "geo", "sip", "sips"}
)


class SanitizerUnavailableError(RuntimeError):
    """Raised when sanitisation is requested but ``nh3`` is not installed."""


def _attribute_allowlist(extra_tags: frozenset[str]) -> dict[str, set[str]]:
    """Copy the attribute map, giving caller-added tags a conservative default."""
    attributes = {tag: set(attrs) for tag, attrs in ALLOWED_ATTRIBUTES.items()}
    for tag in extra_tags:
        attributes.setdefault(tag, {"class", "id", "title"})
    return attributes


def sanitize(
    html: str,
    *,
    force_link_rel: str | None = None,
    extra_tags: frozenset[str] = frozenset(),
) -> str:
    """Strip everything not on the allowlist from ``html``.

    :param force_link_rel: When set, the sanitiser overwrites ``rel`` on every
        ``<a href>`` with this value and forbids the attribute otherwise. When
        ``None`` (the renderer's default) ``rel`` is passed through, because the
        renderer has already applied it selectively at the token level.
    :raises SanitizerUnavailableError: if ``nh3`` is missing.
    """
    if not isinstance(html, str):
        raise TypeError(f"html must be a string, got {type(html).__name__}")
    if not HAVE_NH3:
        raise SanitizerUnavailableError(
            "HTML sanitisation requires the 'nh3' package (pip install nh3). "
            "Either install it, or construct MarkdownRenderer with "
            "RenderOptions(sanitize=False) for trusted input only."
        )

    attributes = _attribute_allowlist(extra_tags)
    if force_link_rel:
        # nh3 refuses to both manage rel and allow it as an attribute.
        attributes["a"] = attributes["a"] - {"rel"}

    kwargs: dict[str, Any] = {
        "tags": set(ALLOWED_TAGS | extra_tags),
        "clean_content_tags": set(CLEAN_CONTENT_TAGS - extra_tags),
        "attributes": attributes,
        "url_schemes": set(ALLOWED_URL_SCHEMES),
        "strip_comments": True,
        "link_rel": force_link_rel,
    }
    return nh3.clean(html, **kwargs)
