"""Command-line entry point: ``python -m github_markdown``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .options import RenderOptions
from .renderer import GitHubMarkdown

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="github-markdown",
        description="Render Markdown to HTML styled like GitHub.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Markdown file to render, or '-' for stdin (the default).",
    )
    parser.add_argument(
        "-o", "--output", help="Write here instead of stdout.", default=None
    )
    parser.add_argument(
        "--fragment",
        action="store_true",
        help="Emit only the rendered body, without the surrounding HTML document.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Page title. Defaults to the input filename.",
    )
    parser.add_argument(
        "--theme",
        choices=("auto", "light", "dark"),
        default="auto",
        help="Colour scheme. 'auto' follows the reader's system setting.",
    )
    parser.add_argument(
        "--link-css",
        action="store_true",
        help="Link the stylesheets instead of embedding them. Combine with "
        "--write-assets so the files exist next to the output.",
    )
    parser.add_argument(
        "--write-assets",
        metavar="DIR",
        default=None,
        help="Copy the bundled stylesheets into DIR.",
    )
    parser.add_argument(
        "--breaks",
        action="store_true",
        help="Treat single newlines as line breaks, as GitHub does in comments.",
    )
    parser.add_argument(
        "--no-highlight", action="store_true", help="Skip syntax highlighting."
    )
    parser.add_argument(
        "--unsafe",
        action="store_true",
        help="Do not sanitise HTML. Only for Markdown you wrote yourself.",
    )
    parser.add_argument(
        "--math", action="store_true", help="Enable $...$ math markup (needs KaTeX)."
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Log what is happening to stderr."
    )
    return parser


def _read_source(location: str) -> str:
    """Read Markdown from a path or stdin, with actionable error messages."""
    if location == "-":
        return sys.stdin.read()

    path = Path(location)
    if not path.exists():
        sys.exit(f"Error: file not found: {path}")
    if path.is_dir():
        sys.exit(f"Error: {path} is a directory, not a Markdown file")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        sys.exit(
            f"Error: {path} is not valid UTF-8 ({exc.reason} at byte {exc.start}). "
            f"Convert it to UTF-8 first."
        )
    except OSError as exc:
        sys.exit(f"Error: cannot read {path}: {exc.strerror}")


def _write_output(html: str, destination: str | None) -> None:
    """Write to a file atomically, or to stdout."""
    if destination is None:
        sys.stdout.write(html)
        return

    path = Path(destination)
    if path.parent and not path.parent.exists():
        sys.exit(f"Error: output directory does not exist: {path.parent}")

    # Write beside the target then rename, so an interrupted run cannot leave a
    # half-written file where a complete one used to be.
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(html, encoding="utf-8")
        temp.replace(path)
    except OSError as exc:
        temp.unlink(missing_ok=True)
        sys.exit(f"Error: cannot write {path}: {exc.strerror}")
    print(f"Wrote {path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    options = RenderOptions(
        breaks=args.breaks,
        highlight=not args.no_highlight,
        sanitize=not args.unsafe,
        math=args.math,
    )
    renderer = GitHubMarkdown(options)

    source = _read_source(args.input)

    if args.write_assets:
        for path in renderer.write_assets(args.write_assets):
            print(f"Wrote {path}", file=sys.stderr)

    if args.fragment:
        html = renderer.render(source)
    else:
        title = args.title or (
            "Document" if args.input == "-" else Path(args.input).stem
        )
        html = renderer.render_page(
            source,
            title=title,
            theme=args.theme,
            inline_css=not args.link_css,
        )

    _write_output(html, args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
