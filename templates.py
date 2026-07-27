"""The standalone-page wrapper used by :meth:`GitHubMarkdown.render_page`."""

from __future__ import annotations

from html import escape
from typing import Sequence

_PAGE = """<!DOCTYPE html>
<html lang="{lang}"{theme_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="{color_scheme}">
<title>{title}</title>
{head}</head>
<body>
{body}</body>
</html>
"""

#: Values for the ``color-scheme`` meta tag, which tells the browser how to
#: paint form controls, scrollbars and the canvas before CSS loads.
_COLOR_SCHEMES = {"auto": "light dark", "light": "light", "dark": "dark"}


def render_document(
    *,
    body: str,
    title: str,
    theme: str = "auto",
    lang: str = "en",
    extra_head: str = "",
    styles: str | None = None,
    css_hrefs: Sequence[str] = (),
) -> str:
    """Assemble a complete HTML document.

    :param styles: CSS to inline. When ``None``, ``css_hrefs`` are linked instead.
    :param theme: ``"light"`` or ``"dark"`` pins the palette via a
        ``data-theme`` attribute; ``"auto"`` leaves it to ``prefers-color-scheme``.
    """
    head_parts: list[str] = []
    if styles is not None:
        head_parts.append(f"<style>\n{styles}\n</style>\n")
    else:
        for href in css_hrefs:
            head_parts.append(
                f'<link rel="stylesheet" href="{escape(href, quote=True)}">\n'
            )
    if extra_head:
        head_parts.append(extra_head.rstrip("\n") + "\n")

    theme_attr = "" if theme == "auto" else f' data-theme="{escape(theme, quote=True)}"'

    return _PAGE.format(
        lang=escape(lang, quote=True),
        theme_attr=theme_attr,
        color_scheme=_COLOR_SCHEMES.get(theme, "light dark"),
        title=escape(title),
        head="".join(head_parts),
        body=body if body.endswith("\n") else body + "\n",
    )
