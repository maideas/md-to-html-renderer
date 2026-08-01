#!/usr/bin/env python3
"""Compile a palette JSON file into its stylesheet.

    python tools/make_palette.py                        # rebuild all bundled palettes
    python tools/make_palette.py path/to/claude.json    # compile one
    python tools/make_palette.py claude.json -o out.css

Adding a theme is a data edit: copy palettes/skeleton.json, fill in the values,
run this. No Python and no structural CSS changes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from md_to_html_renderer.palette import (  # noqa: E402
    PALETTE_DIR,
    PaletteError,
    available_palettes,
    write_palette_css,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "palettes",
        nargs="*",
        help="Palette names or .json paths. Default: every bundled palette.",
    )
    parser.add_argument("-o", "--output", help="Output path (single palette only).")
    args = parser.parse_args(argv)

    sources = args.palettes or sorted(available_palettes())
    if args.output and len(sources) != 1:
        sys.exit("Error: --output takes exactly one palette")
    if not sources:
        sys.exit(f"Error: no palettes found in {PALETTE_DIR}")

    for source in sources:
        try:
            written = write_palette_css(
                source, Path(args.output) if args.output else None
            )
        except PaletteError as exc:
            sys.exit(f"Error: {exc}")
        print(f"Wrote {written}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
