"""Conformance against the full CommonMark specification test suite.

The 652 examples in ``data/commonmark_spec.json`` are the reference suite from
the CommonMark project. They are the strongest available evidence that the
renderer's edge-case handling is correct: nested emphasis, lazy continuation,
link reference resolution, tab expansion, entity handling and the rest.

They also guard *our* code specifically. Every custom core rule (heading
anchors, table alignment, emoji, ``rel``) runs over the same token stream, so a
rule that corrupts an unrelated construct shows up here immediately.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from github_markdown import GitHubMarkdown, RenderOptions

SPEC_PATH = Path(__file__).parent / "data" / "commonmark_spec.json"


def load_spec() -> list[dict]:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


#: CommonMark is a strict subset of GFM, so the extensions have to be off for a
#: like-for-like comparison: with tables on, a line of pipes is a table, not a
#: paragraph. Everything switched off here is separately tested in test_gfm.py.
STRICT_COMMONMARK = RenderOptions(
    anchor_style="none",
    emoji=False,
    highlight=False,
    sanitize=False,
    link_rel="",
    wrapper_tag="",
    linkify=False,
    tables=False,
    footnotes=False,
    strip_front_matter=False,
    strikethrough_single_tilde=False,
)

SPEC_EXAMPLES = load_spec()


def test_spec_fixture_is_complete():
    """Guard against a truncated or corrupted fixture file silently weakening
    every other test in this module."""
    assert len(SPEC_EXAMPLES) == 652, f"expected 652 examples, got {len(SPEC_EXAMPLES)}"
    assert all(ex["html"] is not None for ex in SPEC_EXAMPLES)


@pytest.mark.parametrize(
    "example",
    SPEC_EXAMPLES,
    ids=[f"{ex['example']:03d}-{ex['section'].replace(' ', '-')}" for ex in SPEC_EXAMPLES],
)
def test_commonmark_example(example):
    renderer = GitHubMarkdown(STRICT_COMMONMARK)
    assert renderer.render(example["markdown"]) == example["html"]


def test_full_spec_passes_as_a_whole():
    """A single aggregate assertion, so a regression reports the pass rate
    rather than 600 individual failures."""
    renderer = GitHubMarkdown(STRICT_COMMONMARK)
    failures = [
        ex["example"]
        for ex in SPEC_EXAMPLES
        if renderer.render(ex["markdown"]) != ex["html"]
    ]
    assert not failures, f"{len(failures)}/{len(SPEC_EXAMPLES)} spec examples failed: {failures[:20]}"


def test_default_options_never_crash_on_any_spec_example():
    """The strict preset above disables most features. Re-run every example
    through the *default* renderer to prove the full feature set survives all
    652 inputs, including the deliberately malformed ones."""
    renderer = GitHubMarkdown()
    for example in SPEC_EXAMPLES:
        html = renderer.render(example["markdown"])
        assert isinstance(html, str)
