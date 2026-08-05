"""Worked example: switching between GitHub's light and dark themes.

Run it::

    python examples/theme_switching.py

It regenerates all the theme demos: three pinned-theme pages
(``theme-auto/light/dark.html``), per-palette pages (``palette-github.html``,
``palette-cream.html``), a side-by-side grid (``theme-side-by-side.html``) and
the interactive ``theme-switching.html``: a self-contained page with a two-axis
palette / theme switcher that rethemes the document instantly, without
re-rendering the Markdown. The choice persists via ``localStorage``.

The three approaches it demonstrates, in increasing order of flexibility:

1. **Pin the theme when rendering** -- ``render_page(theme="dark")``.
   Simplest, but the choice is baked into the HTML.
2. **Toggle attributes on ``<html>``** -- one line of JavaScript, no server
   round trip. This is what the generated page does, across both axes:
   ``data-palette`` (GitHub or Cream) and ``data-theme`` (light or dark).
3. **Set the attributes on any container** -- lets one page show all four
   combinations at once.

All three work because the stylesheets express every colour as a CSS custom
property, and the browser recomputes those instantly when the attribute
changes. The rendered HTML is identical in every theme.
"""

from __future__ import annotations

from pathlib import Path

from md_to_html_renderer import MarkdownRenderer

HERE = Path(__file__).parent

#: Both palettes are shipped so the page can switch between them at runtime.
#: With a single palette loaded, ``data-palette`` would be unnecessary.
PALETTES = ["github", "cream"]

# --------------------------------------------------------------------------
# 1. Server-side: pin a theme at render time.
# --------------------------------------------------------------------------


def pinned_examples(renderer: MarkdownRenderer, source: str) -> None:
    """Write one file per fixed theme.

    ``theme="light"`` and ``theme="dark"`` put ``data-theme`` on ``<html>``
    and set the matching ``color-scheme`` meta tag. ``theme="auto"`` (the
    default) omits the attribute so the reader's OS setting decides.
    """
    for theme in ("auto", "light", "dark"):
        html = renderer.render_page(
            source, title=f"Theme: {theme}", theme=theme, inline_css=True
        )
        (HERE / f"theme-{theme}.html").write_text(html, encoding="utf-8")


# --------------------------------------------------------------------------
# 2. Client-side: toggle the attribute. This is the interesting one.
# --------------------------------------------------------------------------

# Runs before the first paint so a reader who chose "dark" never sees a white
# flash while the rest of the page loads. It must be inline and in <head>;
# an external script would arrive too late.
NO_FLASH_SCRIPT = """
(function () {
  var root = document.documentElement;
  function stored(key) {
    try { return localStorage.getItem(key); } catch (err) { return null; }  /* private mode */
  }
  var theme = stored('md-theme');
  if (theme === 'light' || theme === 'dark') { root.setAttribute('data-theme', theme); }
  var palette = stored('md-palette');
  if (palette === 'github' || palette === 'cream') { root.setAttribute('data-palette', palette); }
})();
"""

TOGGLE_SCRIPT = """
(function () {
  var root = document.documentElement;
  var readout = document.getElementById('theme-readout');
  var systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)');

  /* Two independent axes. 'auto' on either means "no attribute, inherit the
     default": for mode that is the OS setting, for palette it is whichever
     palette stylesheet was loaded last. */
  var AXES = {
    theme:   { attribute: 'data-theme',   key: 'md-theme'   },
    palette: { attribute: 'data-palette', key: 'md-palette' }
  };

  function read(axis) {
    try { return localStorage.getItem(AXES[axis].key) || 'auto'; }
    catch (err) { return 'auto'; }
  }

  function store(axis, value) {
    try {
      if (value === 'auto') { localStorage.removeItem(AXES[axis].key); }
      else { localStorage.setItem(AXES[axis].key, value); }
    } catch (err) { /* storage unavailable; the switch still works this session */ }
  }

  function apply(axis, value) {
    // The two lines that do all the actual theming:
    if (value === 'auto') { root.removeAttribute(AXES[axis].attribute); }
    else { root.setAttribute(AXES[axis].attribute, value); }

    document.querySelectorAll('[data-set-' + axis + ']').forEach(function (button) {
      button.setAttribute(
        'aria-pressed', String(button.getAttribute('data-set-' + axis) === value)
      );
    });
    describe();
  }

  function describe() {
    var theme = read('theme');
    var palette = read('palette');
    readout.textContent =
      (palette === 'auto' ? 'Default palette' : palette[0].toUpperCase() + palette.slice(1))
      + ', '
      + (theme === 'auto'
          ? 'following your system setting (currently '
            + (systemPrefersDark.matches ? 'dark' : 'light') + ')'
          : 'pinned ' + theme)
      + '.';
  }

  Object.keys(AXES).forEach(function (axis) {
    document.querySelectorAll('[data-set-' + axis + ']').forEach(function (button) {
      button.addEventListener('click', function () {
        var value = button.getAttribute('data-set-' + axis);
        store(axis, value);
        apply(axis, value);
      });
    });
    apply(axis, read(axis));
  });

  // Keep the readout honest if the OS flips while we are following it.
  systemPrefersDark.addEventListener('change', describe);
})();
"""

# The switch itself is styled with the same --md-* variables as the document,
# so the page chrome retheme's along with the content.
TOGGLE_CSS = """
.theme-bar {
  position: sticky; top: 0; z-index: 10;
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 12px 24px;
  background-color: var(--md-canvas-subtle);
  border-bottom: 1px solid var(--md-border-default);
  color: var(--md-fg-default);
  font: 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
.theme-bar h1 { font-size: 14px; font-weight: 600; margin: 0; }
.theme-group { display: inline-flex; align-items: center; gap: 8px; }
.theme-switch { display: inline-flex; border: 1px solid var(--md-border-default); border-radius: 6px; overflow: hidden; }
.theme-switch button {
  appearance: none; border: 0; cursor: pointer; padding: 5px 14px;
  font: inherit; color: var(--md-fg-muted); background-color: var(--md-canvas-default);
}
.theme-switch button + button { border-left: 1px solid var(--md-border-default); }
.theme-switch button:hover { color: var(--md-fg-default); }
.theme-switch button[aria-pressed="true"] {
  background-color: var(--md-accent-emphasis); color: var(--md-fg-on-emphasis);
}
.theme-switch button:focus-visible { outline: 2px solid var(--md-accent-fg); outline-offset: -2px; }
#theme-readout { color: var(--md-fg-muted); }
body { margin: 0; background-color: var(--md-canvas-default); }
.page { max-width: 1012px; margin: 0 auto; padding: 32px 24px 64px; }
@media (prefers-reduced-motion: no-preference) {
  .theme-switch button { transition: background-color 120ms ease, color 120ms ease; }
}
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Theme switching</title>
<script>{no_flash}</script>
<style>
{css}
{toggle_css}
</style>
</head>
<body>
<div class="theme-bar">
  <div class="theme-group">
    <h1>Palette</h1>
    <div class="theme-switch" role="group" aria-label="Colour palette">
      <button type="button" data-set-palette="github" aria-pressed="false">GitHub</button>
      <button type="button" data-set-palette="cream" aria-pressed="false">Cream</button>
    </div>
  </div>
  <div class="theme-group">
    <h1>Mode</h1>
    <div class="theme-switch" role="group" aria-label="Colour mode">
      <button type="button" data-set-theme="auto" aria-pressed="true">Auto</button>
      <button type="button" data-set-theme="light" aria-pressed="false">Light</button>
      <button type="button" data-set-theme="dark" aria-pressed="false">Dark</button>
    </div>
  </div>
  <span id="theme-readout" role="status" aria-live="polite"></span>
</div>
<div class="page">
{body}
</div>
<script>{toggle}</script>
</body>
</html>
"""

DEMO_MARKDOWN = """
# Theme switching

Press **Auto**, **Light** or **Dark** above. The Markdown is rendered once; only
CSS custom properties change. Nothing is re-fetched and nothing re-renders.

> [!NOTE]
> The switches set `data-palette` and `data-theme` on `<html>`. That is the
> whole mechanism -- two attributes, two independent axes.

> [!IMPORTANT]
> The Cream palette matches the cream theme of the pi-web-app chat UI:
> warm cream canvas, terracotta accent, rust links and serif headings.

## What the switch actually does

```javascript
// Pick a palette:
document.documentElement.setAttribute('data-palette', 'cream');

// Pin a mode, or drop the attribute to follow the operating system:
document.documentElement.setAttribute('data-theme', 'dark');
document.documentElement.removeAttribute('data-theme');
```

Resolution order is `data-theme` first, then `prefers-color-scheme`, then light.
The rendered HTML never changes -- only which custom properties are in scope.

## Colours worth checking in both themes

Keywords, strings, numbers, comments and built-ins each map to a separate
Primer token, so it is worth glancing at a real function in both:

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def fibonacci(n: int) -> int:
    \"\"\"Classic recursion, memoised.\"\"\"
    if n < 2:          # base case
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

print(f"{fibonacci(30):,}")  # 832,040
```

Diffs use their own inserted/deleted background tokens:

```diff
-replicas: 1
+replicas: 3
```

Inline `code`, ~~struck text~~, <mark>highlighted text</mark>, and a
[link](https://example.com) all shift too.

| Token | Light | Dark |
|:------|:-----:|-----:|
| Keyword | red | salmon |
| String | navy | pale blue |
| Comment | grey | grey |

- [x] Canvas and borders
- [x] Syntax highlighting
- [ ] Anything you add yourself

> A blockquote, for the muted foreground colour.
"""


def toggle_example(renderer: MarkdownRenderer, source: str) -> Path:
    """Build the interactive page."""
    destination = HERE / "theme-switching.html"
    destination.write_text(
        PAGE.format(
            no_flash=NO_FLASH_SCRIPT,
            css=renderer.stylesheets(palettes=PALETTES),
            toggle_css=TOGGLE_CSS,
            toggle=TOGGLE_SCRIPT,
            body=renderer.render(source),
        ),
        encoding="utf-8",
    )
    return destination


# --------------------------------------------------------------------------
# 3. Per-container: two themes on one page.
# --------------------------------------------------------------------------


def side_by_side_example(renderer: MarkdownRenderer, source: str) -> Path:
    """All four combinations on one page.

    Because ``[data-palette]`` and ``[data-theme]`` match *any* element and
    custom properties inherit, each pane overrides the page for its subtree
    alone. Set both attributes on the same element.
    """
    fragment = renderer.render(source)
    panes = "\n".join(
        f'<section class="pane" data-palette="{palette}" data-theme="{mode}">'
        f'<p class="pane-label">{palette} &middot; {mode}</p>{fragment}</section>'
        for palette in PALETTES
        for mode in ("light", "dark")
    )
    destination = HERE / "theme-side-by-side.html"
    destination.write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Every palette and mode at once</title>
<style>
{renderer.stylesheets(palettes=PALETTES)}
body {{ margin: 0; display: grid; grid-template-columns: 1fr 1fr; }}
.pane {{ padding: 24px; background-color: var(--md-canvas-default);
        color: var(--md-fg-default); border: 1px solid var(--md-border-default);
        overflow: auto; }}
.pane-label {{ margin: 0 0 16px; font: 600 12px/1 var(--md-font-body);
              letter-spacing: 0.08em; text-transform: uppercase;
              color: var(--md-fg-muted); }}
@media (max-width: 900px) {{ body {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
{panes}
</body>
</html>
""",
        encoding="utf-8",
    )
    return destination


def per_palette_pages(renderer: MarkdownRenderer, source: str) -> list[Path]:
    """One standalone page per palette, for a straight visual comparison."""
    written = []
    for palette in PALETTES:
        scoped = MarkdownRenderer(renderer.options.evolve(palette=palette))
        html = scoped.render_page(
            source, title=f"{palette.capitalize()} palette", inline_css=True
        )
        path = HERE / f"palette-{palette}.html"
        path.write_text(html, encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    renderer = MarkdownRenderer()
    pinned_examples(renderer, DEMO_MARKDOWN)
    written = [
        toggle_example(renderer, DEMO_MARKDOWN),
        side_by_side_example(renderer, DEMO_MARKDOWN),
        *per_palette_pages(renderer, DEMO_MARKDOWN),
    ]
    for path in written:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
