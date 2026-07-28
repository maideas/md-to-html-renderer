# Changelog

## 2.1.0

- Added the `claude` palette: an **approximate reconstruction** of Claude's
  chat rendering, built from the published brand palette with the remaining
  tokens derived. Not extracted from the app, not an official Anthropic theme.
- Added `tests/test_contrast.py`: WCAG 2.1 contrast gates for every
  non-template palette, in both modes. Body text must clear 4.5:1, syntax
  colours 3.5:1 against the surface they sit on.
- Palettes may set `"template": true` to opt out of the contrast gates.
- Examples rebuilt around both palettes: two-axis switcher, a four-pane
  comparison grid, and per-palette kitchen sinks.

## 2.0.0

Colour and structure separated so a theme is a data file, not a code change.

**Breaking**

- `asset_paths()`, `stylesheets()` and `write_assets()` are now instance
  methods, because the palette is per-renderer.
- CSS custom properties renamed `--gh-*` to `--md-*`.
- `static/github-markdown.css` and `static/github-syntax.css` are replaced by
  `static/markdown.css` plus a palette from `static/palettes/`.

**Added**

- `RenderOptions.palette`, accepting a bundled name or a path to your own JSON.
- `github_markdown.palette`: loading, validation and CSS generation.
- `tools/make_palette.py` to compile a palette JSON into its stylesheet.
- `renderer.css_hrefs()`, matching the layout `write_assets()` writes.
- `data-palette` as a second theming axis, independent of `data-theme`.
- Typography and shape tokens (`font-body`, `radius`, `space-block`, ...), so a
  palette can change more than colour.
- A themed page shell for `render_page`: canvas background and a centred column.

**Fixed**

- `<mark>` referenced an undefined `--gh-attention-muted`, leaving highlighted
  text light-yellow with near-white text on it in dark mode.

## 1.0.0

- Initial release. 652/652 CommonMark spec examples pass byte for byte.
- GFM: tables, task lists, strikethrough, autolinks, footnotes, alerts,
  emoji shortcodes, front matter.
- Sanitised by default via `nh3`, failing closed when it is unavailable.
- Pygments highlighting mapped onto GitHub's syntax palette.
