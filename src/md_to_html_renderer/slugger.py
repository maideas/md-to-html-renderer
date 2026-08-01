"""Heading slugs that match GitHub's ``github-slugger``.

GitHub's algorithm, reimplemented:

1. Lower-case the heading text.
2. Delete every character that is not a letter, number, combining mark,
   hyphen or underscore. Punctuation, symbols and emoji all disappear.
3. Replace each whitespace character with a single hyphen -- *each*, not each
   run, so ``"a  b"`` becomes ``"a--b"``.
4. If the slug was already used in this document, append ``-1``, ``-2``, ...

Non-ASCII letters survive, so ``"Überschrift"`` becomes ``"überschrift"``.
"""

from __future__ import annotations

import unicodedata

#: Characters kept even though they are punctuation in Unicode's eyes.
_KEPT_PUNCTUATION = frozenset("-_")

#: Unicode general-category initials that survive slugification.
_KEPT_CATEGORIES = ("L", "N", "M")

#: Fallback for headings that slugify to nothing at all (e.g. "## ***").
EMPTY_SLUG_FALLBACK = "section"


def slugify(text: str) -> str:
    """Slugify one heading. Does not deduplicate -- see :class:`Slugger`.

    >>> slugify("Hello, World!")
    'hello-world'
    >>> slugify("C++ vs. Rust")
    'c-vs-rust'
    >>> slugify("Grüße aus Berlin")
    'grüße-aus-berlin'
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a string, got {type(text).__name__}")

    # NFC first so that composed and decomposed spellings of the same heading
    # produce the same slug.
    text = unicodedata.normalize("NFC", text).lower()

    out: list[str] = []
    for char in text:
        if char.isspace():
            out.append("-")
        elif char in _KEPT_PUNCTUATION:
            out.append(char)
        elif unicodedata.category(char)[0] in _KEPT_CATEGORIES:
            out.append(char)
        # Everything else -- punctuation, symbols, emoji, control chars -- is
        # dropped without leaving a separator, exactly as github-slugger does.
    return "".join(out)


class Slugger:
    """Stateful slug generator that keeps ids unique within one document.

    A fresh instance is created per :meth:`~md_to_html_renderer.MarkdownRenderer.render`
    call, which is what keeps the renderer safe to share between threads.
    """

    __slots__ = ("_counts", "_prefix")

    def __init__(self, prefix: str = "") -> None:
        if not isinstance(prefix, str):
            raise TypeError(f"prefix must be a string, got {type(prefix).__name__}")
        self._prefix = prefix
        self._counts: dict[str, int] = {}

    def slug(self, text: str) -> str:
        """Return a document-unique slug for ``text``.

        Repeated headings get ``-1``, ``-2``, ... appended. A heading whose
        literal text collides with a generated suffix is handled too: after
        ``Foo``/``Foo`` produce ``foo``/``foo-1``, a real ``Foo-1`` heading
        becomes ``foo-1-1``.
        """
        base = slugify(text) or EMPTY_SLUG_FALLBACK

        result = base
        while result in self._counts:
            self._counts[base] += 1
            result = f"{base}-{self._counts[base]}"
        self._counts[result] = 0

        return self._prefix + result

    def reset(self) -> None:
        """Forget every slug issued so far."""
        self._counts.clear()
