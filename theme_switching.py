"""Worked example: switching between GitHub's light and dark themes.

Run it::

    python examples/theme_switching.py

It writes ``examples/theme-switching.html``: a self-contained page with a
three-way Auto / Light / Dark switch that retheme's the document instantly,
without re-rendering the Markdown.

The three approaches it demonstrates, in increasing order of flexibility:

1. **Pin the theme when rendering** -- ``render_page(theme="dark")``.
   Simplest, but the choice is baked into the HTML.
2. **Toggle the ``data-theme`` attribute on ``<html>``** -- one line of
   JavaScript, no server round trip. This is what the generated page does.
3. **Set ``data-theme`` on any container** -- lets one page show light and
   dark documents side by side.

All three work because the stylesheets express every colour as a CSS custom
property, and the browser recomputes those instantly when the attribute
changes. The rendered HTML is identical in every theme.
"""

from __future__ import annotations

from pathlib import Path

from github_markdown import GitHubMarkdown

HERE = Path(__file__).parent

# --------------------------------------------------------------------------
# 1. Server-side: pin a theme at render time.
# --------------------------------------------------------------------------


def pinned_examples(renderer: GitHubMarkdown, source: str) -> None:
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
  var stored = null;
  try { stored = localStorage.getItem('gh-theme'); } catch (err) { /* private mode */ }
  if (stored === 'light' || stored === 'dark') {
    document.documentElement.setAttribute('data-theme', stored);
  }
})();
"""

TOGGLE_SCRIPT = """
(function () {
  var root = document.documentElement;
  var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-set-theme]'));
  var readout = document.getElementById('theme-readout');
  var systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)');

  function read() {
    try { return localStorage.getItem('gh-theme') || 'auto'; } catch (err) { return 'auto'; }
  }

  function store(mode) {
    try {
      if (mode === 'auto') { localStorage.removeItem('gh-theme'); }
      else { localStorage.setItem('gh-theme', mode); }
    } catch (err) { /* storage unavailable; the toggle still works this session */ }
  }

  function describe(mode) {
    if (mode !== 'auto') return 'Showing ' + mode + '.';
    return 'Following your system setting, which is currently '
      + (systemPrefersDark.matches ? 'dark' : 'light') + '.';
  }

  function apply(mode) {
    // The single line that does the actual theming:
    if (mode === 'auto') { root.removeAttribute('data-theme'); }
    else { root.setAttribute('data-theme', mode); }

    buttons.forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.dataset.setTheme === mode));
    });
    readout.textContent = describe(mode);
  }

  buttons.forEach(function (button) {
    button.addEventListener('click', function () {
      var mode = button.dataset.setTheme;
      store(mode);
      apply(mode);
    });
  });

  // Keep the readout honest if the OS flips while we are in auto mode.
  systemPrefersDark.addEventListener('change', function () {
    if (read() === 'auto') { apply('auto'); }
  });

  apply(read());
})();
"""

# The switch itself is styled with the same --gh-* variables as the document,
# so the page chrome retheme's along with the content.
TOGGLE_CSS = """
.theme-bar {
  position: sticky; top: 0; z-index: 10;
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 12px 24px;
  background-color: var(--gh-canvas-subtle);
  border-bottom: 1px solid var(--gh-border-default);
  color: var(--gh-fg-default);
  font: 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
.theme-bar h1 { font-size: 14px; font-weight: 600; margin: 0; }
.theme-switch { display: inline-flex; border: 1px solid var(--gh-border-default); border-radius: 6px; overflow: hidden; }
.theme-switch button {
  appearance: none; border: 0; cursor: pointer; padding: 5px 14px;
  font: inherit; color: var(--gh-fg-muted); background-color: var(--gh-canvas-default);
}
.theme-switch button + button { border-left: 1px solid var(--gh-border-default); }
.theme-switch button:hover { color: var(--gh-fg-default); }
.theme-switch button[aria-pressed="true"] {
  background-color: var(--gh-accent-emphasis); color: var(--gh-fg-on-emphasis);
}
.theme-switch button:focus-visible { outline: 2px solid var(--gh-accent-fg); outline-offset: -2px; }
#theme-readout { color: var(--gh-fg-muted); }
body { margin: 0; background-color: var(--gh-canvas-default); }
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
  <h1>Theme</h1>
  <div class="theme-switch" role="group" aria-label="Colour theme">
    <button type="button" data-set-theme="auto" aria-pressed="true">Auto</button>
    <button type="button" data-set-theme="light" aria-pressed="false">Light</button>
    <button type="button" data-set-theme="dark" aria-pressed="false">Dark</button>
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
> The switch sets `data-theme` on `<html>`. That is the whole mechanism.

## What the switch actually does

```javascript
// Follow the operating system:
document.documentElement.removeAttribute('data-theme');

// Or pin a theme:
document.documentElement.setAttribute('data-theme', 'dark');
```

Resolution order is `data-theme` first, then `prefers-color-scheme`, then light.

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


def toggle_example(renderer: GitHubMarkdown, source: str) -> Path:
    """Build the interactive page."""
    destination = HERE / "theme-switching.html"
    destination.write_text(
        PAGE.format(
            no_flash=NO_FLASH_SCRIPT,
            css=GitHubMarkdown.stylesheets(),
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


def side_by_side_example(renderer: GitHubMarkdown, source: str) -> Path:
    """Because ``[data-theme]`` matches *any* element and custom properties
    inherit, a container can override the page theme for its subtree alone."""
    fragment = renderer.render(source)
    destination = HERE / "theme-side-by-side.html"
    destination.write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Both themes at once</title>
<style>
{GitHubMarkdown.stylesheets()}
body {{ margin: 0; display: grid; grid-template-columns: 1fr 1fr; min-height: 100vh; }}
.pane {{ padding: 24px; background-color: var(--gh-canvas-default); overflow: auto; }}
@media (max-width: 900px) {{ body {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="pane" data-theme="light">{fragment}</div>
<div class="pane" data-theme="dark">{fragment}</div>
</body>
</html>
""",
        encoding="utf-8",
    )
    return destination


def main() -> None:
    renderer = GitHubMarkdown()
    pinned_examples(renderer, DEMO_MARKDOWN)
    for path in (
        toggle_example(renderer, DEMO_MARKDOWN),
        side_by_side_example(renderer, DEMO_MARKDOWN),
    ):
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
