"""``:shortcode:`` to emoji conversion, GitHub-style.

Only text nodes are touched. Code spans, fenced blocks and raw HTML keep their
colons verbatim, because the substitution runs over the parsed token tree
rather than over the source string -- ``` `:smile:` ``` stays literal, which is
what GitHub does too.

The optional ``emoji`` package supplies the name table. Without it this module
is inert and shortcodes pass through unchanged.
"""

from __future__ import annotations

import re
from functools import lru_cache

try:  # pragma: no cover - trivial import shim
    import emoji as _emoji_lib

    HAVE_EMOJI = True
except ImportError:  # pragma: no cover
    _emoji_lib = None  # type: ignore[assignment]
    HAVE_EMOJI = False


#: Shortcode names use only these characters on GitHub.
SHORTCODE_RE = re.compile(r":([a-z0-9_+-]{1,64}):", re.IGNORECASE)

_LOOKUP_CACHE_SIZE = 2048


@lru_cache(maxsize=_LOOKUP_CACHE_SIZE)
def lookup(name: str) -> str | None:
    """Return the emoji for a shortcode name, or ``None`` if unknown."""
    if not HAVE_EMOJI:
        return None
    token = f":{name}:"
    # `emoji` matches aliases case-sensitively and lower-case is the convention.
    replaced = _emoji_lib.emojize(token.lower(), language="alias")
    if replaced != token.lower():
        return replaced
    replaced = _emoji_lib.emojize(token.lower(), language="en")
    return replaced if replaced != token.lower() else None


def replace_shortcodes(text: str) -> str:
    """Expand every known shortcode in ``text``, leaving unknown ones alone."""
    if not HAVE_EMOJI or ":" not in text:
        return text

    def _sub(match: re.Match[str]) -> str:
        return lookup(match.group(1)) or match.group(0)

    return SHORTCODE_RE.sub(_sub, text)
