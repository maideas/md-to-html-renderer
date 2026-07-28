# github-markdown

Render GitHub-Flavoured Markdown to HTML that looks like GitHub — including the
syntax highlighting — from a reusable Python class.

- **652/652 CommonMark spec examples pass**, byte for byte. The reference suite
  is vendored into `tests/data/`, so edge cases are verified against the spec
  itself rather than against hand-picked examples.
- **GFM extensions**: tables, task lists, strikethrough, autolinks, footnotes,
  alerts (`> [!NOTE]`), emoji shortcodes, YAML front matter.
- **Sanitised by default**, and it fails *closed* — if the sanitiser is
  unavailable, raw HTML is escaped rather than trusted.
- **Thread-safe.** One renderer instance can be shared across requests.

## Install

From the built wheel:

```bash
pip install dist/github_markdown-2.1.0-py3-none-any.whl
pip install dist/github_markdown-2.1.0-py3-none-any.whl[all]   # + autolinks and emoji
```

Or from source, for development:

```bash
pip install -e ".[all]"
python -m pytest tests/ -q        # 967 tests
```

Required: `markdown-it-py>=4.1`, `mdit-py-plugins>=0.6`, `Pygments`, `nh3`.
Optional: `linkify-it-py` (bare-URL autolinking) and `emoji` (`:shortcode:`
expansion). Both degrade silently -- without them those two features are
simply inert, and everything else works unchanged.

## Use

```python
from github_markdown import GitHubMarkdown

renderer = GitHubMarkdown()                      # build once, reuse
html = renderer.render(markdown_text)            # -> <article class="markdown-body">…
```

Drop the fragment into your own template and link the stylesheets:

```python
renderer.write_assets("myapp/static/")           # structure + active palette
print(renderer.css_hrefs())                      # ['palettes/github.css', 'markdown.css']
```

```html
<link rel="stylesheet" href="/static/palettes/github.css">
<link rel="stylesheet" href="/static/markdown.css">
```

Or get a complete standalone page with the CSS embedded:

```python
page = renderer.render_page(markdown_text, title="Docs", inline_css=True)
```

Build a table of contents whose ids are guaranteed to match the rendered
headings:

```python
for entry in renderer.table_of_contents(markdown_text, max_level=3):
    print(entry["level"], entry["id"], entry["text"])
```

### Command line

```bash
python -m github_markdown README.md -o readme.html
python -m github_markdown README.md --fragment          # body only
python -m github_markdown README.md --theme dark -o out.html
cat notes.md | python -m github_markdown - --fragment
```

## Options

Everything is configured through one immutable dataclass:

```python
from github_markdown import GitHubMarkdown, RenderOptions

renderer = GitHubMarkdown(RenderOptions(
    breaks=True,                        # newline -> <br>, as in GitHub comments
    heading_id_prefix="user-content-",  # avoid id collisions with your own page
))
```

| Option | Default | Effect |
|---|---|---|
| `linkify` | `True` | Autolink bare URLs, `www.` hosts and emails |
| `breaks` | `False` | Single newline becomes `<br>` (GitHub does this in comments, not in files) |
| `tables`, `tasklists`, `footnotes`, `alerts` | `True` | GFM extensions |
| `emoji` | `True` | Expand `:shortcode:`; needs the `emoji` package |
| `math` | `False` | Emit `$…$` as KaTeX-ready markup |
| `strip_front_matter` | `True` | Drop a leading YAML block |
| `anchor_style` | `"heading"` | `"heading"`, `"github"` or `"none"` |
| `heading_id_prefix` / `fragment_id_prefix` | `""` | Namespace heading and footnote ids |
| `highlight` | `True` | Syntax-highlight fenced code |
| `highlight_guess_language` | `False` | Guess the language of unlabelled fences |
| `palette` | `"github"` | Bundled palette name, or a path to your own |
| `emit_palette_attribute` | `False` | Force `data-palette` onto standalone pages |
| `wrapper_tag` / `wrapper_class` | `"article"` / `"markdown-body"` | Output wrapper; `""` for a bare fragment |
| `link_rel` | `"nofollow noopener noreferrer"` | `rel` on outbound links |
| `absolute_links_only_rel` | `True` | Leave in-document anchors without `rel` |
| `allow_html` | `True` | Let raw HTML through the parser |
| `sanitize` | `True` | Run output through the allowlist sanitiser |
| `max_input_bytes` | 8 MiB | Reject larger documents |
| `max_highlight_bytes` | 256 KiB | Skip highlighting for larger code blocks |
| `extra_allowed_tags` | `frozenset()` | Additional tags the sanitiser keeps |

Two presets are provided: `COMMENT_PRESET` (matches issue/PR comment rendering)
and `TRUSTED_PRESET` (no sanitising — only for Markdown you wrote yourself).

## Security

Markdown permits raw HTML, so any document you did not author is an XSS vector.
By default the rendered HTML goes through [`nh3`](https://pypi.org/project/nh3/)
with a GitHub-derived allowlist:

- `<script>`, `<style>`, `<iframe>`, `<object>` and `<embed>` are removed along
  with their contents.
- All `on*` event handlers and `style` attributes are stripped.
- Only known-safe URL schemes survive; `javascript:`, `vbscript:`, `data:` and
  `file:` do not.
- `target` is **not** allowed on links, which removes the reverse-tabnabbing
  vector entirely.
- HTML comments are dropped.

If `nh3` is not installed, the renderer logs a warning and escapes all raw HTML
instead of passing it through. It never silently trusts input.

Set `sanitize=False` only for content you control.

## Theming and palettes

Colour lives in **palettes**; structure lives in one colour-free stylesheet.

```
static/
  markdown.css            ~950 lines of rules, zero colour values
  palettes/github.json    the token values          <- edit this
  palettes/github.css     compiled from the JSON    <- generated
  palettes/claude.json    approximate Claude theme  (see caveat below)
  palettes/skeleton.json  template for a new palette
```

### Bundled palettes

| Name | Notes |
|---|---|
| `github` | GitHub's Primer tokens, as used on github.com. |
| `claude` | **Approximate reconstruction**, not extracted from the Claude app and not an official Anthropic theme. Built from the published brand palette (warm cream canvas, clay accent); remaining tokens derived for contrast and harmony. Replace with real values when you have them. |
| `skeleton` | Template. Placeholders are magenta and cyan so an unfilled token is obvious. Marked `"template": true`, which exempts it from the contrast tests. |

Every colour, font size and radius in `markdown.css` is a `--md-*` custom
property. Adding a theme is therefore a **data edit, not a code change**.

### Adding a palette

```bash
cp src/github_markdown/static/palettes/skeleton.json  .../palettes/mytheme.json
# fill in the 53 colour tokens for light and dark, set "name": "mytheme"
python tools/make_palette.py src/github_markdown/static/palettes/mytheme.json
```

To replace the approximate Claude palette with extracted values, edit
`palettes/claude.json` and re-run the same command. No code changes.

```python
GitHubMarkdown(RenderOptions(palette="claude"))
GitHubMarkdown(RenderOptions(palette="/path/to/mytheme.json"))  # outside the package
```

The skeleton's placeholder values are magenta and cyan on purpose: a token you
have not filled in is impossible to miss. `tools/make_palette.py` refuses to
compile a palette whose light and dark sections define different token sets,
which is the failure mode that otherwise leaves one element keeping its
light-mode colour on a dark background.

### The two axes

Palette *family* and light/dark *mode* are independent:

| Markup | Result |
|---|---|
| `<html>` | default palette, follows the OS |
| `<html data-theme="dark">` | default palette, pinned dark |
| `<html data-palette="claude">` | Claude palette, follows the OS |
| `<html data-palette="claude" data-theme="light">` | Claude palette, pinned light |
| `<div data-palette="claude" data-theme="dark">` | that subtree only |

Set both attributes on the same element. Switching either is one line of
JavaScript and no re-render:

```javascript
document.documentElement.setAttribute('data-theme', 'dark');
document.documentElement.setAttribute('data-palette', 'claude');
document.documentElement.removeAttribute('data-theme');   // back to following the OS
```

A single palette claims `:root`, so `data-palette` is only needed when you load
more than one. To ship several and switch at runtime:

```python
renderer.write_assets("static/", palettes=["github", "claude"])
page = renderer.render_page(source, palettes=["github", "claude"])
```

`:root:not([data-palette])` is deliberately more specific than a bare
`[data-palette="x"]`, so an explicit attribute always beats the implicit
default however the stylesheets are ordered.

### Token groups

| Group | Count | Examples |
|---|---|---|
| Surfaces and text | 9 | `canvas-default`, `fg-muted`, `border-default` |
| Semantic roles | 13 | `accent-fg`, `danger-emphasis`, `attention-muted` |
| Diff backgrounds | 2 | `diff-add-bg`, `diff-del-bg` |
| Syntax highlighting | 29 | `syn-keyword`, `syn-string`, `syn-comment` |
| Typography and shape (`base`) | 14 | `font-body`, `radius`, `space-block` |

The `base` group is mode-independent and only needs defining once, so a palette
that changes typography or corner radius — not just colour — needs no extra
machinery.

## Documented deviations from github.com

These are deliberate, and each is a judgement call worth knowing about.

**Heading anchor ids.** GitHub puts `id="user-content-slug"` on the anchor
`<a>` and points `href` at the unprefixed `#slug`; only their client-side script
makes those links resolve. Copied verbatim into your own page, in-document links
would silently do nothing. The default therefore puts the id on the heading
itself, which is visually identical and actually works. Set
`anchor_style="github"` for their exact markup.

**Unrecognised code tokens.** Pygments emits an "error" token fairly freely for
valid-but-unsupported syntax. GitHub never paints code red, so `.err` renders as
plain text rather than as an error highlight.

**Highlighting engine.** GitHub uses Linguist/tree-sitter; this uses Pygments.
The palette and markup structure match, but for a given language the two
tokenisers will occasionally disagree about what counts as a keyword. A few
mappings are informed guesses — notably that operators (`=`, `+`) take the
keyword colour and that Python's `self` takes the variable colour. If you want
these tuned to a specific language, they are single-value changes in
`static/palettes/github.json`.

**Empty blockquotes.** markdown-it collapses `<blockquote></blockquote>`; the
CommonMark reference keeps a newline. This renderer restores the newline so the
spec suite passes outright. No visual difference.

## Tests

```bash
python -m pytest tests/ -q
```

The suite is organised as:

| File | Covers |
|---|---|
| `test_commonmark_spec.py` | All 652 spec examples, plus a crash-free run of every example through the default (full-feature) renderer |
| `test_slugger.py` | Slug characters, Unicode, deduplication, collisions between literal and generated suffixes |
| `test_gfm.py` | Tables, task lists, alerts, strikethrough, autolinks, footnotes, emoji, front matter |
| `test_sanitizer.py` | Script injection, event handlers, dangerous URL schemes — and that benign markup survives |
| `test_edge_cases.py` | Degenerate input, limits, and feature *combinations* (table-in-list-in-blockquote, footnote-in-heading, emoji-in-code-span) |
| `test_renderer_api.py` | Options validation, assets, page rendering, stylesheet coverage, CLI |
| `test_palette.py` | Palette loading, validation, CSS generation, selector specificity, custom palettes end to end |
| `test_contrast.py` | WCAG contrast floors for every non-template palette, in both modes |

The stylesheets are tested too. `test_every_pygments_token_class_is_styled`
fails if a Pygments upgrade introduces a token type the CSS does not cover;
`test_structure_stylesheet_contains_no_colour_values` fails if a colour leaks
back into the structural sheet; `test_compiled_css_is_current` fails if a
palette JSON was edited without recompiling; and
`test_all_palettes_define_the_same_token_set` fails if one palette is missing a
token another defines. `test_contrast.py` computes WCAG 2.1 ratios and fails a
palette whose body text drops below 4.5:1 or whose syntax colours drop below
3.5:1 against the surface they sit on.

## Examples

Run `python examples/theme_switching.py` to regenerate these.

| File | Shows |
|---|---|
| `theme-switching.html` | Live two-axis switcher: palette × mode, with no-flash preload |
| `theme-side-by-side.html` | All four combinations on one page, via per-container attributes |
| `palette-github.html` / `palette-claude.html` | The same document in each palette |
| `kitchen-sink-github.html` / `kitchen-sink-claude.html` | Every supported construct, in each palette |

## Licence

MIT. The colour values reproduce GitHub's Primer design tokens; the octicon
paths are from GitHub's Octicons (MIT).
