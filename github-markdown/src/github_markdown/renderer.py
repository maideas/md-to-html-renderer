"""The :class:`GitHubMarkdown` renderer."""

from __future__ import annotations

import logging
from html import escape
from pathlib import Path
from typing import Any, Iterable, Sequence

from markdown_it import MarkdownIt
from markdown_it.token import Token

from . import icons
from .emoji_shortcodes import replace_shortcodes
from .highlight import highlight_code, normalise_language
from .options import RenderOptions, Theme
from .palette import STRUCTURE_CSS, PaletteError, palette_css_path
from .sanitizer import HAVE_NH3, SanitizerUnavailableError, sanitize
from .slugger import Slugger
from .templates import render_document

log = logging.getLogger(__name__)

#: Directory holding the stylesheets shipped with the package.
STATIC_DIR = Path(__file__).parent / "static"

#: Structural stylesheet filename. Colours come from a palette alongside it.
STRUCTURE_NAME = "markdown.css"

#: Inline tokens whose ``content`` contributes to a heading's slug. Anything
#: else (raw HTML, emphasis markers) contributes nothing, matching how GitHub
#: slugifies the *rendered* text rather than the Markdown source.
_TEXT_BEARING_TOKENS = frozenset({"text", "code_inline"})

#: Schemes that make a link "outbound" for the purposes of ``rel``.
_ABSOLUTE_PREFIXES = ("http://", "https://", "//", "mailto:", "ftp://", "ftps://")


class GitHubMarkdown:
    """Render GitHub-Flavoured Markdown to GitHub-styled HTML.

    One instance is a reusable, thread-safe renderer::

        renderer = GitHubMarkdown()
        html = renderer.render(source)

    All per-document state (heading slug counters, footnote numbering) lives in
    the parser ``env`` created fresh on each call, so a single instance can be
    shared across requests or worker threads without locking.

    :param options: A :class:`~github_markdown.RenderOptions`. Omit for
        defaults that match how GitHub renders a repository ``.md`` file.
    """

    def __init__(self, options: RenderOptions | None = None) -> None:
        if options is not None and not isinstance(options, RenderOptions):
            raise TypeError(
                f"options must be a RenderOptions, got {type(options).__name__}"
            )
        self.options = options or RenderOptions()
        # Fail at construction, not at the first render_page call, so a typo in
        # the palette name surfaces at startup.
        try:
            palette_css_path(self.options.palette)
        except PaletteError as exc:
            raise ValueError(str(exc)) from exc
        self._sanitize_enabled = self._resolve_sanitizer()
        self._md = self._build_parser()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _resolve_sanitizer(self) -> bool:
        """Decide whether sanitisation runs, degrading safely if nh3 is absent."""
        if not self.options.sanitize:
            return False
        if HAVE_NH3:
            return True
        # Failing closed: raw HTML gets escaped rather than trusted. Escaping is
        # handled by the parser, configured in _build_parser.
        log.warning(
            "nh3 is not installed, so HTML sanitisation is unavailable. "
            "Raw HTML in the Markdown will be escaped and shown as text. "
            "Install nh3 to allow safe inline HTML."
        )
        return False

    @property
    def _raw_html_allowed(self) -> bool:
        """Raw HTML may only reach the output if we can clean it, or if the
        caller has explicitly declared the input trusted."""
        if not self.options.allow_html:
            return False
        if self.options.sanitize:
            return self._sanitize_enabled
        return True

    def _build_parser(self) -> MarkdownIt:
        opts = self.options
        md = MarkdownIt(
            "commonmark",
            {
                "html": self._raw_html_allowed,
                "linkify": opts.linkify,
                "breaks": opts.breaks,
                "typographer": opts.typographer,
                "highlight": None,
            },
        )

        if opts.tables:
            md.enable("table")
        else:
            md.disable("table")
        md.enable("strikethrough")
        md.options["strikethrough_single_tilde"] = opts.strikethrough_single_tilde
        md.options["tasklists"] = opts.tasklists
        md.options["tasklists_editable"] = opts.tasklists_editable
        md.options["alerts"] = opts.alerts

        if opts.linkify:
            # GFM's extended autolinking (bare URLs, www. hosts, emails). Gated
            # on the same option as markdown-it's own linkifier so that
            # linkify=False really does leave bare URLs as plain text.
            from mdit_py_plugins.gfm_autolink import gfm_autolink_plugin

            md.use(gfm_autolink_plugin)

        if opts.footnotes:
            from mdit_py_plugins.footnote import footnote_plugin

            md.use(footnote_plugin, inline=False)

        if opts.math:
            from mdit_py_plugins.dollarmath import dollarmath_plugin

            md.use(dollarmath_plugin, allow_blank_lines=False)

        if opts.strip_front_matter:
            from mdit_py_plugins.front_matter import front_matter_plugin

            md.use(front_matter_plugin)
            md.add_render_rule("front_matter", lambda *_a, **_k: "")

        # Token-tree transformations. Order matters: emoji must be expanded
        # before heading slugs are computed, or a ":tada:" shortcode would end
        # up in the id instead of the emoji character it stands for (which the
        # slugger then drops, exactly as GitHub does).
        md.core.ruler.push("gh_use_del", self._rule_strikethrough_tag)
        md.core.ruler.push("gh_table_align", self._rule_table_align)
        if opts.emoji:
            md.core.ruler.push("gh_emoji", self._rule_emoji)
        md.core.ruler.push("gh_heading_anchors", self._rule_heading_anchors)
        md.core.ruler.push("gh_alert_icons", self._rule_alert_icons)
        md.core.ruler.push("gh_link_rel", self._rule_link_rel)

        # Registered directly rather than via ``md.add_render_rule``: that helper
        # rebinds the callable to the *renderer* instance, which would hide our
        # own ``self``. A plain closure keeps both objects reachable.
        rules = md.renderer.rules
        rules["fence"] = lambda tokens, idx, opts, env: self._render_fence(tokens, idx)
        rules["code_block"] = lambda tokens, idx, opts, env: self._render_code_block(
            tokens, idx
        )
        rules["heading_open"] = lambda tokens, idx, opts, env: self._render_heading_open(
            tokens, idx
        )
        rules["alert_title_open"] = (
            lambda tokens, idx, opts, env: self._render_alert_title_open(tokens, idx)
        )
        rules["blockquote_close"] = (
            lambda tokens, idx, opts, env: self._render_blockquote_close(tokens, idx)
        )

        return md

    # ------------------------------------------------------------------
    # Core rules (token-tree transformations)
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_strikethrough_tag(state: Any) -> None:
        """GFM specifies ``<del>``; markdown-it emits ``<s>``."""
        for token in state.tokens:
            if token.type != "inline" or not token.children:
                continue
            for child in token.children:
                if child.type in ("s_open", "s_close"):
                    child.tag = "del"

    @staticmethod
    def _rule_table_align(state: Any) -> None:
        """Convert ``style="text-align:left"`` to ``align="left"``.

        GitHub emits the ``align`` attribute, and unlike inline ``style`` it
        survives sanitisation without having to allow style attributes at all.
        """
        for token in state.tokens:
            if token.type not in ("th_open", "td_open"):
                continue
            style = token.attrGet("style")
            if not style or "text-align" not in style:
                continue
            alignment = style.split("text-align:", 1)[1].strip().rstrip(";").strip()
            if alignment in ("left", "center", "right"):
                token.attrSet("align", alignment)
            attrs = dict(token.attrs)
            attrs.pop("style", None)
            token.attrs = attrs

    def _rule_heading_anchors(self, state: Any) -> None:
        """Assign a unique slug to every heading and record it for rendering."""
        if self.options.anchor_style == "none":
            return

        slugger: Slugger = state.env.setdefault(
            "gh_slugger", Slugger(self.options.heading_id_prefix)
        )
        headings: list[dict[str, str]] = state.env.setdefault("gh_headings", [])

        tokens: Sequence[Token] = state.tokens
        for index, token in enumerate(tokens):
            if token.type != "heading_open":
                continue
            inline = tokens[index + 1] if index + 1 < len(tokens) else None
            text = _inline_plain_text(inline) if inline is not None else ""
            slug = slugger.slug(text)
            token.meta = dict(token.meta or {})
            token.meta["gh_slug"] = slug
            headings.append({"level": token.tag, "text": text, "id": slug})

    @staticmethod
    def _rule_alert_icons(state: Any) -> None:
        """Copy each alert's kind onto its title token so the icon can be drawn."""
        current_kind = ""
        for token in state.tokens:
            if token.type == "alert_open":
                current_kind = str((token.meta or {}).get("kind", "")).lower()
            elif token.type == "alert_title_open":
                token.meta = dict(token.meta or {})
                token.meta["gh_kind"] = current_kind

    def _rule_link_rel(self, state: Any) -> None:
        """Apply ``rel`` to outbound links, as GitHub does with ``nofollow``."""
        rel = self.options.link_rel
        if not rel:
            return
        for token in state.tokens:
            if token.type != "inline" or not token.children:
                continue
            for child in token.children:
                if child.type != "link_open":
                    continue
                href = child.attrGet("href") or ""
                if self.options.absolute_links_only_rel and not _is_absolute(href):
                    continue
                child.attrSet("rel", rel)

    @staticmethod
    def _rule_emoji(state: Any) -> None:
        """Expand ``:shortcode:`` in text nodes only."""
        for token in state.tokens:
            if token.type != "inline" or not token.children:
                continue
            for child in token.children:
                if child.type == "text" and ":" in child.content:
                    child.content = replace_shortcodes(child.content)

    # ------------------------------------------------------------------
    # Render rules
    # ------------------------------------------------------------------

    def _render_fence(self, tokens: Sequence[Token], idx: int) -> str:
        token = tokens[idx]
        language = normalise_language(token.info or "")
        return highlight_code(
            token.content,
            language,
            enabled=self.options.highlight,
            guess=self.options.highlight_guess_language,
            max_bytes=self.options.max_highlight_bytes,
        )

    def _render_code_block(self, tokens: Sequence[Token], idx: int) -> str:
        """Indented code blocks carry no language, so they are never highlighted."""
        return highlight_code(tokens[idx].content, "", enabled=False)

    def _render_heading_open(self, tokens: Sequence[Token], idx: int) -> str:
        token = tokens[idx]
        slug = (token.meta or {}).get("gh_slug")
        if not slug:
            return f"<{token.tag}>"

        escaped = escape(slug, quote=True)
        if self.options.anchor_style == "github":
            # id lives on the anchor, mirroring github.com byte for byte.
            anchor = (
                f'<a id="{escaped}" class="anchor" aria-hidden="true" tabindex="-1" '
                f'href="#{escaped}">{icons.LINK_ICON}</a>'
            )
            return f"<{token.tag}>{anchor}"

        anchor = (
            f'<a class="anchor" aria-hidden="true" tabindex="-1" '
            f'href="#{escaped}">{icons.LINK_ICON}</a>'
        )
        return f'<{token.tag} id="{escaped}">{anchor}'

    @staticmethod
    def _render_blockquote_close(tokens: Sequence[Token], idx: int) -> str:
        """Emit ``<blockquote>\\n</blockquote>`` for a blockquote with no content.

        markdown-it collapses the empty case to ``<blockquote></blockquote>``;
        the CommonMark reference keeps the newline. Visually identical, but
        matching it exactly means the spec suite passes outright.
        """
        if idx > 0 and tokens[idx - 1].type == "blockquote_open":
            return "\n</blockquote>\n"
        return "</blockquote>\n"

    @staticmethod
    def _render_alert_title_open(tokens: Sequence[Token], idx: int) -> str:
        kind = (tokens[idx].meta or {}).get("gh_kind", "")
        icon = icons.ALERT_ICONS.get(kind, "")
        return f'<p class="markdown-alert-title">{icon}'

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, source: str, *, env: dict[str, Any] | None = None) -> str:
        """Render Markdown to an HTML fragment.

        :param source: Markdown text. ``bytes`` are rejected -- decode first so
            that the encoding is your decision, not a guess.
        :param env: Optional dict that receives per-document metadata. After the
            call it contains ``gh_headings``: a list of
            ``{"level", "text", "id"}`` entries you can use to build a table of
            contents.
        :returns: HTML wrapped in ``<article class="markdown-body">`` unless
            ``wrapper_tag`` is empty.
        :raises TypeError: if ``source`` is not a ``str``.
        :raises ValueError: if ``source`` exceeds ``max_input_bytes``.
        """
        source = self._validate_source(source)
        render_env: dict[str, Any] = env if env is not None else {}
        if self.options.fragment_id_prefix:
            # The footnote plugin namespaces its ids with env["docId"].
            render_env.setdefault("docId", self.options.fragment_id_prefix)

        html = self._md.render(source, render_env)

        if self._sanitize_enabled:
            html = self._sanitize(html)

        return self._wrap(html)

    def render_page(
        self,
        source: str,
        *,
        title: str = "Document",
        theme: Theme = "auto",
        inline_css: bool = False,
        css_hrefs: Iterable[str] | None = None,
        palettes: Iterable[str] | None = None,
        lang: str = "en",
        extra_head: str = "",
        env: dict[str, Any] | None = None,
    ) -> str:
        """Render a complete, standalone HTML document.

        :param inline_css: Embed the stylesheets in a ``<style>`` block, giving
            a single self-contained file. Otherwise the page links to
            ``css_hrefs`` (defaulting to the two bundled filenames, which you
            must serve yourself -- see :meth:`write_assets`).
        :param theme: ``"auto"`` follows the reader's OS setting.
        :param extra_head: Raw HTML injected into ``<head>``. Never pass
            untrusted input here; it is not sanitised.
        """
        if theme not in ("auto", "light", "dark"):
            raise ValueError(f"theme must be 'auto', 'light' or 'dark', got {theme!r}")

        body = self.render(source, env=env)
        # data-palette is only meaningful when more than one palette is present;
        # a single palette already claims :root.
        multiple = palettes is not None and len(list(palettes)) > 1
        emit_palette = self.options.emit_palette_attribute or multiple

        return render_document(
            body=body,
            title=title,
            theme=theme,
            palette=str(self.options.palette) if emit_palette else "",
            lang=lang,
            extra_head=extra_head,
            styles=self.stylesheets(palettes=palettes) if inline_css else None,
            css_hrefs=(
                list(css_hrefs)
                if css_hrefs is not None
                else self.css_hrefs(palettes=palettes)
            ),
        )

    def table_of_contents(self, source: str, *, max_level: int = 3) -> list[dict[str, str]]:
        """Return heading metadata without keeping the rendered HTML.

        Each entry is ``{"level": "h2", "text": "...", "id": "..."}`` with ids
        identical to those :meth:`render` produces for the same source.
        """
        if not isinstance(max_level, int) or not 1 <= max_level <= 6:
            raise ValueError(f"max_level must be between 1 and 6, got {max_level!r}")
        env: dict[str, Any] = {}
        self.render(source, env=env)
        return [
            heading
            for heading in env.get("gh_headings", [])
            if int(heading["level"][1]) <= max_level
        ]

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    @classmethod
    def structure_css(cls) -> Path:
        """Path to the colour-free structural stylesheet."""
        return STRUCTURE_CSS

    @staticmethod
    def available_palettes() -> list[str]:
        """Names of the bundled palettes."""
        from .palette import available_palettes as _available

        return sorted(_available())

    def asset_paths(self, *, palettes: Iterable[str] | None = None) -> list[Path]:
        """Stylesheets needed to display this renderer's output.

        The palette comes first so the structural sheet can rely on its tokens
        being defined, though CSS custom properties make the order cosmetic.

        :param palettes: Ship these palettes instead of just the active one.
            Load several to switch between them at runtime with
            ``data-palette``.
        """
        names = list(palettes) if palettes is not None else [self.options.palette]
        return [palette_css_path(name) for name in names] + [STRUCTURE_CSS]

    def stylesheets(self, *, palettes: Iterable[str] | None = None) -> str:
        """The CSS, concatenated, ready to inline in a ``<style>``."""
        return "\n".join(
            path.read_text(encoding="utf-8")
            for path in self.asset_paths(palettes=palettes)
        )

    def write_assets(
        self,
        directory: str | Path,
        *,
        palettes: Iterable[str] | None = None,
        overwrite: bool = True,
    ) -> list[Path]:
        """Copy the stylesheets into ``directory`` (created if needed).

        Palettes land in a ``palettes/`` subdirectory, mirroring the layout the
        package uses, so relative links keep working.

        :param overwrite: When ``False``, existing files are left untouched
            rather than replaced -- useful if you have edited them.
        :returns: The destination paths, whether or not they were rewritten.
        """
        target = Path(directory)
        written: list[Path] = []

        for source_path in self.asset_paths(palettes=palettes):
            in_palettes = source_path.parent.name == "palettes"
            destination = target / ("palettes" if in_palettes else "") / source_path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            written.append(destination)
            if destination.exists() and not overwrite:
                log.info("Keeping existing %s", destination)
                continue
            # Write to a sibling temp file then replace, so an interrupted copy
            # cannot leave a truncated stylesheet behind.
            temp = destination.with_name(destination.name + ".tmp")
            temp.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
            temp.replace(destination)
        return written

    def css_hrefs(self, *, palettes: Iterable[str] | None = None) -> list[str]:
        """Relative hrefs matching what :meth:`write_assets` lays down."""
        return [
            f"palettes/{path.name}" if path.parent.name == "palettes" else path.name
            for path in self.asset_paths(palettes=palettes)
        ]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _validate_source(self, source: str) -> str:
        if isinstance(source, bytes):
            raise TypeError(
                "source must be str, not bytes -- decode it first, e.g. "
                "source.decode('utf-8')"
            )
        if not isinstance(source, str):
            raise TypeError(f"source must be a string, got {type(source).__name__}")

        limit = self.options.max_input_bytes
        if limit:
            size = len(source.encode("utf-8", "surrogatepass"))
            if size > limit:
                raise ValueError(
                    f"Markdown input is {size} bytes, above the "
                    f"max_input_bytes limit of {limit}. Raise the limit in "
                    f"RenderOptions if this document is expected."
                )

        # A leading BOM would otherwise be parsed as paragraph text.
        return source.lstrip("\ufeff")

    def _sanitize(self, html: str) -> str:
        try:
            # rel is applied at the token level by _rule_link_rel, so the
            # sanitiser passes it through rather than overwriting it.
            return sanitize(
                html,
                force_link_rel=None,
                extra_tags=self.options.extra_allowed_tags,
            )
        except SanitizerUnavailableError:  # pragma: no cover - guarded at init
            raise

    def _wrap(self, html: str) -> str:
        tag = self.options.wrapper_tag
        if not tag:
            return html
        css_class = escape(self.options.wrapper_class, quote=True)
        return f'<{tag} class="{css_class}">\n{html}</{tag}>\n'


def _inline_plain_text(inline_token: Token | None) -> str:
    """Flatten an inline token to the text GitHub would slugify.

    Emphasis markers and raw HTML tags contribute nothing; link text, code
    spans and image alt text all count.
    """
    if inline_token is None or not inline_token.children:
        return inline_token.content if inline_token is not None else ""

    parts: list[str] = []
    for child in inline_token.children:
        if child.type in _TEXT_BEARING_TOKENS:
            parts.append(child.content)
        elif child.type == "image":
            parts.append(_inline_plain_text_from_children(child.children))
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts)


def _inline_plain_text_from_children(children: Sequence[Token] | None) -> str:
    if not children:
        return ""
    return "".join(
        child.content for child in children if child.type in _TEXT_BEARING_TOKENS
    )


def _is_absolute(href: str) -> bool:
    """True for links that leave the current document."""
    lowered = href.strip().lower()
    return lowered.startswith(_ABSOLUTE_PREFIXES)
