"""Fenced-code highlighting that produces GitHub-shaped markup.

GitHub wraps highlighted code as::

    <div class="highlight highlight-source-python">
      <pre><code class="language-python"><span class="k">def</span> ...</code></pre>
    </div>

Colours are *not* baked in here. Pygments emits its short token classes
(``.k``, ``.nf``, ``.s2`` ...) and ``static/markdown.css`` maps each one to a
``--md-syn-*`` custom property supplied by the active palette. Switching theme
or palette is therefore pure CSS, with no re-render.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from html import escape

from pygments import highlight as _pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexer import Lexer
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.token import STANDARD_TYPES
from pygments.util import ClassNotFound

from markdown_it.common.utils import escapeHtml, unescapeAll

log = logging.getLogger(__name__)

#: Info strings are attacker-controlled and end up inside a class attribute.
#: Everything is escaped on output, so this only has to remove characters that
#: could not appear in a real language name anyway: control characters,
#: whitespace, quotes and markup delimiters. Unicode letters survive, because
#: CommonMark allows them in an info string.
_SAFE_LANG_RE = re.compile(r"""[\x00-\x20\x7f-\x9f"'`<>&]""")

#: Longest language token we will echo into a class attribute.
_MAX_LANG_LENGTH = 64

#: Number of distinct language names whose lexer we keep resident.
_LEXER_CACHE_SIZE = 128

#: GitHub labels the wrapper by Linguist scope. Most languages use
#: ``source``; these use a different top-level scope.
_NON_SOURCE_SCOPES = {
    "html": "text-html-basic",
    "xml": "text-xml",
    "markdown": "text-md",
    "md": "text-md",
    "tex": "text-tex-latex",
    "latex": "text-tex-latex",
    "diff": "source-diff",
    "text": "text-plain",
    "plaintext": "text-plain",
}

#: Rendered once and reused; ``nowrap`` means we own the <pre>/<code> wrapper.
_FORMATTER = HtmlFormatter(nowrap=True, classprefix="")


def normalise_language(info: str) -> str:
    """Extract a safe language token from a fence info string.

    Only the first whitespace-separated word is significant, matching both
    CommonMark and GitHub, so ``python title="demo.py"`` yields ``python``.
    Backslash escapes and character references are resolved first, as
    CommonMark requires: an info string of ``f&ouml;&ouml;`` means ``föö``.
    """
    if not info:
        return ""
    info = unescapeAll(info)
    stripped = info.strip()
    if not stripped:
        return ""
    first_word = stripped.split(None, 1)[0]
    return _SAFE_LANG_RE.sub("", first_word)[:_MAX_LANG_LENGTH]


def linguist_scope(language: str) -> str:
    """Return GitHub's wrapper class suffix for ``language``."""
    lowered = language.lower()
    return _NON_SOURCE_SCOPES.get(lowered, f"source-{lowered}")


@lru_cache(maxsize=_LEXER_CACHE_SIZE)
def _lexer_for(language: str) -> Lexer | None:
    """Look up a lexer by name, or ``None`` when the language is unknown.

    Cached because resolving an alias scans Pygments' full plugin registry,
    which is far too slow to repeat for every fence in a long document.
    ``lru_cache`` is itself thread-safe, so this is safe to share.
    """
    try:
        return get_lexer_by_name(language, stripnl=False, ensurenl=True)
    except ClassNotFound:
        return None


def _guess_lexer(code: str) -> Lexer | None:
    try:
        return guess_lexer(code, stripnl=False, ensurenl=True)
    except ClassNotFound:
        return None


def highlight_code(
    code: str,
    language: str = "",
    *,
    enabled: bool = True,
    guess: bool = False,
    max_bytes: int = 256 * 1024,
) -> str:
    """Return a complete ``<div class="highlight">…</div>`` block.

    Falls back to plain escaped text -- never raises -- when highlighting is
    disabled, the language is unknown, the block is too large, or Pygments
    fails on malformed input.

    :param code: Raw contents of the fence, without the fence markers.
    :param language: Already-normalised language token, possibly empty.
    :param max_bytes: Skip highlighting above this size to bound render time.
    """
    if not isinstance(code, str):
        raise TypeError(f"code must be a string, got {type(code).__name__}")

    language = normalise_language(language)
    body = None

    too_large = max_bytes and len(code.encode("utf-8", "replace")) > max_bytes
    if too_large:
        log.debug("Skipping highlight for %d-char block above size limit", len(code))

    if enabled and code.strip() and not too_large:
        lexer = _lexer_for(language) if language else (_guess_lexer(code) if guess else None)
        if lexer is not None:
            try:
                body = _pygments_highlight(code, lexer, _FORMATTER)
            except Exception:  # noqa: BLE001 - a lexer bug must not break rendering
                log.warning(
                    "Pygments failed on a %r block; emitting plain text",
                    language or "auto",
                    exc_info=True,
                )
                body = None

    highlighted = body is not None
    if body is None:
        # markdown-it's escaper, not html.escape: CommonMark escapes the double
        # quote inside code blocks but leaves the apostrophe alone.
        body = escapeHtml(code)

    code_class = f' class="language-{escape(language, quote=True)}"' if language else ""
    block = f"<pre><code{code_class}>{body}</code></pre>\n"

    if not highlighted:
        # No spans to colour, so no wrapper: this is byte-for-byte the
        # CommonMark reference output, and matches what GitHub emits for a
        # fence whose language it does not recognise.
        return block

    scope = escape(f"highlight highlight-{linguist_scope(language)}", quote=True)
    return f'<div class="{scope}">{block}</div>\n'


def pygments_class_names() -> set[str]:
    """Every CSS class Pygments can emit for a standard token type.

    The test suite asserts the bundled stylesheet covers all of these, so a
    Pygments upgrade that introduces a new token type fails loudly rather than
    silently rendering that token unstyled.
    """
    return {name for name in STANDARD_TYPES.values() if name}
