"""The standalone-page wrapper used by :meth:`MarkdownRenderer.render_page`."""

from __future__ import annotations

from html import escape
from typing import Sequence

_PAGE = """<!DOCTYPE html>
<html lang="{lang}"{palette_attr}{theme_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="{color_scheme}">
<title>{title}</title>
{head}</head>
<body>
<div class="markdown-page">
{body}</div>
</body>
</html>
"""

#: Minimal page shell for standalone documents: a themed canvas and a centred
#: column at GitHub's own README width. Only ``render_page`` uses this --
#: ``render`` returns a bare fragment and imposes no layout, so embedding it in
#: an existing site never fights that site's CSS.
PAGE_SHELL_CSS = """\
body { margin: 0; background-color: var(--md-canvas-default); }
.markdown-page { max-width: 1012px; margin: 0 auto; padding: 32px 24px 64px; }
@media (max-width: 767px) { .markdown-page { padding: 16px 12px 48px; } }
"""

#: Values for the ``color-scheme`` meta tag, which tells the browser how to
#: paint form controls, scrollbars and the canvas before CSS loads.
_COLOR_SCHEMES = {"auto": "light dark", "light": "light", "dark": "dark"}


def render_document(
    *,
    body: str,
    title: str,
    theme: str = "auto",
    palette: str = "",
    lang: str = "en",
    extra_head: str = "",
    styles: str | None = None,
    css_hrefs: Sequence[str] = (),
) -> str:
    """Assemble a complete HTML document.

    :param styles: CSS to inline. When ``None``, ``css_hrefs`` are linked instead.
    :param theme: ``"light"`` or ``"dark"`` pins the mode via a ``data-theme``
        attribute; ``"auto"`` leaves it to ``prefers-color-scheme``.
    :param palette: Emits ``data-palette``. Only needed when several palette
        stylesheets are loaded at once.
    """
    head_parts: list[str] = []
    if styles is not None:
        head_parts.append(f"<style>\n{styles}\n</style>\n")
    else:
        for href in css_hrefs:
            head_parts.append(
                f'<link rel="stylesheet" href="{escape(href, quote=True)}">\n'
            )
    head_parts.append(f"<style>\n{PAGE_SHELL_CSS}</style>\n")
    if extra_head:
        head_parts.append(extra_head.rstrip("\n") + "\n")

    theme_attr = "" if theme == "auto" else f' data-theme="{escape(theme, quote=True)}"'
    palette_attr = f' data-palette="{escape(palette, quote=True)}"' if palette else ""

    return _PAGE.format(
        lang=escape(lang, quote=True),
        palette_attr=palette_attr,
        theme_attr=theme_attr,
        color_scheme=_COLOR_SCHEMES.get(theme, "light dark"),
        title=escape(title),
        head="".join(head_parts),
        body=body if body.endswith("\n") else body + "\n",
    )
