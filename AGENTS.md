# AGENTS.md — Python Markdown to HTML Renderer

`md-to-html-renderer`: renders GitHub-Flavoured Markdown to sanitised HTML
with syntax highlighting. The visual style is palette-driven — the bundled
`github` palette matches GitHub exactly, further palettes can be added as
data. Pure Python 3.9+, `src/` layout, setuptools build backend, no Makefile.

## Build / test / run

```bash
pip install -e ".[all]"          # dev install (all optional extras)
python -m pytest tests/ -q       # ~977 tests; CommonMark spec vendored in tests/data/
python -m md_to_html_renderer README.md -o out.html   # CLI
python -m build                  # wheel lands in dist/ (gitignored)
```

Per global rules, put generated artifacts in `build/` (already gitignored);
the existing wheel in `dist/` is also gitignored and not committed.

## Dependencies

- Required: `markdown-it-py>=4.1`, `mdit-py-plugins>=0.6`, `Pygments>=2.17`,
  `nh3>=0.2`.
- Optional extras `linkify` / `emoji` / `all`: `linkify-it-py` (bare-URL
  autolinking), `emoji` (`:shortcode:` expansion). Both must degrade
  silently when missing — code is written to work without them.

## Project layout

```
src/md_to_html_renderer/
├── renderer.py          # MarkdownRenderer class — main public API (render, render_page, table_of_contents, write_assets)
├── options.py           # RenderOptions dataclass, Theme enum
├── sanitizer.py         # nh3-based sanitisation; fails closed (escapes raw HTML if nh3 missing)
├── highlight.py         # Pygments code-block highlighting, language normalisation
├── slugger.py           # GitHub-compatible heading-slug generation
├── palette.py           # Palette loading/validation; STRUCTURE_CSS
├── templates.py         # HTML document wrapper
├── icons.py             # Inline SVG icons
├── emoji_shortcodes.py  # :shortcode: expansion (optional emoji dep)
├── cli.py / __main__.py # argparse CLI: python -m md_to_html_renderer
└── static/
    ├── markdown.css     # structural stylesheet
    └── palettes/        # github + cream + pi-web-app palettes (.css + .json metadata, skeleton.* template)
tests/                   # pytest; commonmark_spec.json is the vendored 652-example spec
tools/make_palette.py    # generate a new palette from static/palettes/skeleton.*
examples/                # kitchen-sink + theme demo scripts and HTML output
```

## Conventions and invariants

- **Public API**: `from md_to_html_renderer import MarkdownRenderer`. Renderer
  instances are thread-safe and meant to be built once and reused.
- **Sanitising is on by default and must fail closed**: never emit raw HTML
  when the sanitiser is unavailable; escape instead
  (`SanitizerUnavailableError` path in `sanitizer.py`).
- **Slug rule**: heading ids are derived from rendered text only — inline
  tokens `text` and `code_inline` contribute; HTML/emphasis markers do not.
  `table_of_contents()` ids must always match rendered heading ids.
- **Spec compliance**: the CommonMark suite (652/652) must keep passing byte
  for byte; run `python -m pytest tests/test_commonmark_spec.py` after any
  renderer change.
- **Palettes**: colours live in palettes; `markdown.css` is structure only.
  Add new palettes via `tools/make_palette.py` (JSON metadata + CSS), plus
  the contrast test in `tests/test_contrast.py`.
- **Optional deps**: guard every use of `linkify-it-py` / `emoji` so missing
  packages leave features inert, not broken.
- Type hints throughout (`from __future__ import annotations`); keep new
  modules consistent with that style.
