"""Colour palettes.

A palette is a small JSON file naming every design token in two modes. It
carries no rules and no selectors -- ``static/markdown.css`` holds all of those
and is entirely colour-free. Adding a theme therefore means adding one data
file; no Python and no structural CSS changes.

    {
      "name": "claude",
      "label": "Claude",
      "base":  { "radius": "12px", ... },   optional, mode-independent
      "light": { "canvas-default": "#ffffff", ... },
      "dark":  { "canvas-default": "#1a1a1a", ... }
    }

:func:`build_css` turns that into a stylesheet whose selectors handle the two
independent axes -- palette *family* and light/dark *mode*::

    <html data-palette="claude" data-theme="dark">   pinned
    <html data-palette="claude">                     follows the OS
    <html>                                           default palette, follows the OS

Tokens named in ``base`` are emitted once. Because CSS custom properties
cascade per property rather than per block, the dark block only has to restate
the ones that actually change.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

#: Where the bundled palettes live.
PALETTE_DIR = Path(__file__).parent / "static" / "palettes"

#: The colour-free stylesheet every palette is designed against.
STRUCTURE_CSS = Path(__file__).parent / "static" / "markdown.css"

#: Prefix for every custom property. Not GitHub-specific any more.
TOKEN_PREFIX = "--md-"

#: Palette names become part of an attribute selector, so they are restricted
#: to a plain CSS identifier.
_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")

#: Token values are interpolated straight into CSS. Anything that could close a
#: declaration or open a comment would let a palette file inject arbitrary
#: rules, so those characters are rejected outright.
_UNSAFE_VALUE_RE = re.compile(r"[{};<>]|/\*|\*/|@import|expression\s*\(", re.I)

#: A palette must supply both modes; ``base`` is optional.
REQUIRED_SECTIONS = ("light", "dark")


class PaletteError(ValueError):
    """Raised when a palette file is missing, malformed or unsafe."""


def available_palettes() -> dict[str, Path]:
    """Map every bundled palette name to its JSON source path."""
    if not PALETTE_DIR.is_dir():  # pragma: no cover - packaging accident
        return {}
    return {path.stem: path for path in sorted(PALETTE_DIR.glob("*.json"))}


def load_palette(source: str | Path) -> dict[str, Any]:
    """Load and validate a palette.

    :param source: A bundled palette name (``"github"``) or a path to a JSON
        file of your own.
    :raises PaletteError: if the palette is unknown, unparseable or invalid.
    """
    path = _resolve_source(source)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PaletteError(f"{path} is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise PaletteError(f"cannot read palette {path}: {exc}") from exc

    validate_palette(raw, origin=path)
    return raw


def _resolve_source(source: str | Path) -> Path:
    """Turn a name or path into an existing JSON file path."""
    if isinstance(source, Path) or (isinstance(source, str) and (
        "/" in source or "\\" in source or source.endswith(".json")
    )):
        path = Path(source)
        if not path.exists():
            raise PaletteError(f"palette file not found: {path}")
        return path

    if not isinstance(source, str):
        raise PaletteError(
            f"palette must be a name or a path, got {type(source).__name__}"
        )

    bundled = available_palettes()
    if source not in bundled:
        known = ", ".join(sorted(bundled)) or "none"
        raise PaletteError(
            f"unknown palette {source!r}. Bundled palettes: {known}. "
            f"Pass a path to a .json file to use your own."
        )
    return bundled[source]


def validate_palette(palette: Any, *, origin: Path | str = "<memory>") -> None:
    """Check a palette dict, raising :class:`PaletteError` on any problem.

    Enforces the two invariants that actually cause bugs: that both modes
    define exactly the same token names (otherwise a token silently keeps its
    light value on a dark background), and that no value can break out of its
    declaration.
    """
    if not isinstance(palette, dict):
        raise PaletteError(f"{origin}: palette must be a JSON object")

    name = palette.get("name")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise PaletteError(
            f"{origin}: 'name' must be a lower-case CSS identifier "
            f"(letters, digits, hyphens), got {name!r}"
        )

    for section in REQUIRED_SECTIONS:
        if not isinstance(palette.get(section), dict) or not palette[section]:
            raise PaletteError(f"{origin}: missing or empty '{section}' section")

    light_tokens = set(palette["light"])
    dark_tokens = set(palette["dark"])
    if light_tokens != dark_tokens:
        only_light = sorted(light_tokens - dark_tokens)
        only_dark = sorted(dark_tokens - light_tokens)
        raise PaletteError(
            f"{origin}: light and dark must define the same tokens. "
            f"Only in light: {only_light or 'none'}. "
            f"Only in dark: {only_dark or 'none'}."
        )

    for section in ("base", *REQUIRED_SECTIONS):
        for token, value in (palette.get(section) or {}).items():
            _validate_token(token, value, section=section, origin=origin)


def _validate_token(token: Any, value: Any, *, section: str, origin: Path | str) -> None:
    if not isinstance(token, str) or not re.match(r"^[a-z][a-z0-9-]*$", token):
        raise PaletteError(f"{origin}: invalid token name {token!r} in '{section}'")
    if not isinstance(value, str) or not value.strip():
        raise PaletteError(
            f"{origin}: token '{token}' in '{section}' must be a non-empty string"
        )
    if _UNSAFE_VALUE_RE.search(value):
        raise PaletteError(
            f"{origin}: token '{token}' in '{section}' contains characters that "
            f"could break out of a CSS declaration: {value!r}"
        )


def _declarations(tokens: dict[str, str], indent: str) -> str:
    return "".join(
        f"{indent}{TOKEN_PREFIX}{token}: {value.strip()};\n"
        for token, value in tokens.items()
    )


def build_css(palette: dict[str, Any]) -> str:
    """Render a validated palette to a stylesheet.

    The generated selectors mean one palette file works both on its own (where
    it claims ``:root``) and alongside others (where ``data-palette`` picks
    between them). ``:root:not([data-palette])`` is deliberately more specific
    than a bare ``[data-palette="x"]``, so an explicit attribute always wins
    over the implicit default.
    """
    validate_palette(palette)

    name = palette["name"]
    label = palette.get("label", name)
    description = palette.get("description", "")

    default = f':root:not([data-palette]),\n[data-palette="{name}"]'
    auto_dark = (
        f':root:not([data-palette]):not([data-theme="light"]),\n'
        f'  [data-palette="{name}"]:not([data-theme="light"])'
    )
    pinned_dark = (
        f':root:not([data-palette])[data-theme="dark"],\n'
        f'[data-palette="{name}"][data-theme="dark"]'
    )

    base = _declarations(palette.get("base") or {}, "  ")
    light = _declarations(palette["light"], "  ")
    dark_indented = _declarations(palette["dark"], "    ")
    dark = _declarations(palette["dark"], "  ")

    header = f"/* {label} palette"
    if description:
        header += f" -- {description}"
    header += "\n"

    return f"""{header}   Generated from {name}.json by tools/make_palette.py -- edit the JSON, not this file.

   Pair with markdown.css, which holds every rule and no colours.

     <html>                                   this palette, following the OS
     <html data-theme="dark">                 this palette, pinned dark
     <html data-palette="{name}">{" " * max(0, 22 - len(name))}explicit, when several are loaded
     <div  data-palette="{name}" data-theme="light">   one subtree only

   Set data-palette and data-theme on the same element. */

{default} {{
  color-scheme: light;
{base}{light}}}

@media (prefers-color-scheme: dark) {{
  {auto_dark} {{
    color-scheme: dark;
{dark_indented}  }}
}}

{pinned_dark} {{
  color-scheme: dark;
{dark}}}
"""


def write_palette_css(source: str | Path, destination: Path | None = None) -> Path:
    """Generate ``<name>.css`` next to the palette's JSON source."""
    palette = load_palette(source)
    target = destination or (PALETTE_DIR / f"{palette['name']}.css")
    target.parent.mkdir(parents=True, exist_ok=True)

    # Write then rename, so an interrupted run cannot leave a half-written
    # stylesheet where a complete one used to be.
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(build_css(palette), encoding="utf-8")
    temp.replace(target)
    return target


def palette_css_path(source: str | Path) -> Path:
    """Path to the compiled stylesheet for a palette name or JSON path."""
    json_path = _resolve_source(source)
    css_path = json_path.with_suffix(".css")
    if not css_path.exists():
        raise PaletteError(
            f"palette {json_path.stem!r} has no compiled stylesheet at {css_path}. "
            f"Run: python tools/make_palette.py {json_path}"
        )
    return css_path
