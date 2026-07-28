Good question — the theming is the part where a bit of explanation saves a lot of guessing. Let me verify the CSS behaves as I'll describe, and build you a working toggle.Confirmed one real bug while checking: `<mark>` references `--gh-attention-muted`, which I never defined — so highlighted text stayed light-yellow in dark mode with near-white text on it. Fixing that, and adding a test so it can't recur.Now let me fix a related rough edge — `render_page` produced an edge-to-edge body with no page background — then build the toggle example.Open **theme-switching.html** — it has a working Auto / Light / Dark switch. **theme-side-by-side.html** shows both themes on one page simultaneously.

## The mechanism

Every colour is a CSS custom property, so switching themes is one attribute change and zero re-rendering:

```javascript
document.documentElement.setAttribute('data-theme', 'dark');   // pin dark
document.documentElement.setAttribute('data-theme', 'light');  // pin light
document.documentElement.removeAttribute('data-theme');        // follow the OS
```

Resolution order is `data-theme` → `prefers-color-scheme` → light.

## Three approaches

**1. Pin it server-side** when you already know the user's preference:

```python
html = renderer.render_page(source, theme="dark", inline_css=True)
```

**2. Toggle client-side** (what the demo does). The full switch is in `theme_switching.py`, but the essential parts are:

```javascript
function applyTheme(mode) {
  if (mode === 'auto') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', mode);
}
```

Two details that matter in production. First, put a tiny **inline** script in `<head>` to apply the stored choice before first paint — an external script arrives too late and a dark-mode user gets a white flash:

```html
<script>
(function () {
  var stored = null;
  try { stored = localStorage.getItem('gh-theme'); } catch (err) {}
  if (stored === 'light' || stored === 'dark') {
    document.documentElement.setAttribute('data-theme', stored);
  }
})();
</script>
```

Second, wrap `localStorage` in `try/catch` — it throws in Safari private mode and in sandboxed iframes. The demo degrades to a session-only toggle there rather than breaking.

**3. Per container.** `[data-theme]` matches *any* element and custom properties inherit, so a `<div data-theme="dark">` themes just its subtree. That's how the side-by-side page works, and it's useful for previewing a document in the opposite theme.

## Two fixes this turned up

Checking the CSS rather than assuming it caught a genuine bug: `<mark>` referenced `--gh-attention-muted`, which I never defined. Highlighted text stayed light-yellow in dark mode with near-white text on it — unreadable. Now defined in both palettes, with a test that fails if any `--gh-*` variable is used without being defined, plus one asserting the dark palette covers every light token. That class of bug is invisible in whichever theme you happen to be looking at.

I also gave `render_page` a themed page shell (canvas background, centred 1012px column at GitHub's README width). Previously standalone pages were edge-to-edge with an unthemed body. This affects `render_page` only — `render()` still returns a bare fragment and imposes no layout, so embedding it never fights your site's CSS.

899 tests pass. If you're wiring this into a server-rendered app, the usual pattern is to store the preference in a cookie and set `data-theme` on `<html>` in your base template, which skips the flash entirely — happy to sketch that for Flask or Django.
