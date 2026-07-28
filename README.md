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

```bash
pip install markdown-it-py>=4.1 mdit-py-plugins>=0.6 Pygments nh3
pip install linkify-it-py emoji        # optional: autolinks and :shortcodes:
pip install -e .
```

## Use

```python
from github_markdown import GitHubMarkdown

renderer = GitHubMarkdown()                      # build once, reuse
html = renderer.render(markdown_text)            # -> <article class="markdown-body">…
```

Drop the fragment into your own template and link the two stylesheets:

```python
GitHubMarkdown.write_assets("myapp/static/")     # copies both .css files
```

```html
<link rel="stylesheet" href="/static/github-markdown.css">
<link rel="stylesheet" href="/static/github-syntax.css">
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

## Theming

Colours come from CSS custom properties, so light and dark switch without
re-rendering. Resolution order:

1. `data-theme="light"` or `data-theme="dark"` on any ancestor
2. the reader's `prefers-color-scheme`
3. light

Both stylesheets are plain CSS with no build step. Override any
`--gh-*` variable to retheme.

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
these tuned to a specific language, they are single-line changes in
`static/github-syntax.css`.

**Empty blockquotes.** markdown-it collapses `<blockquote></blockquote>`; the
CommonMark reference keeps a newline. This renderer restores the newline so the
spec suite passes outright. No visual difference.

## Tests

```bash
python -m pytest tests/ -q        # 897 tests
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

The stylesheet is tested too: `test_every_pygments_token_class_is_styled` fails
if a Pygments upgrade introduces a token type the CSS does not cover, so no
token can silently render unstyled.

## Licence

MIT. The colour values reproduce GitHub's Primer design tokens; the octicon
paths are from GitHub's Octicons (MIT).
