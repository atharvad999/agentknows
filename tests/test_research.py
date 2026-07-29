# -*- coding: utf-8 -*-
from reachkit.models import Item, ReachResult
from reachkit.research import _region_sources, bundle_to_markdown


def _ok(platform, items):
    return {
        "ok": True,
        "result": ReachResult(ok=True, platform=platform, backend="test",
                              kind="items", items=items),
    }


def test_region_source_selection():
    assert "discourse" in _region_sources("india")
    assert "hackernews" not in _region_sources("india")
    assert "hackernews" in _region_sources("western")
    assert "discourse" not in _region_sources("western")
    assert set(_region_sources(None)) >= {"web", "hackernews", "news", "discourse"}


def test_bundle_markdown_covers_and_flags_missing():
    bundle = {
        "web": _ok("web", [Item(title="A result", url="https://x.com", snippet="snip")]),
        "twitter": {"ok": False, "error": "needs cookies", "fix": "pipx install twitter-cli"},
    }
    md = bundle_to_markdown("test query", bundle, region="india")
    assert "# Research bundle: test query" in md
    assert "Region focus: india" in md
    assert "A result" in md and "https://x.com" in md
    assert "Sources unavailable: twitter" in md
    assert "pipx install twitter-cli" in md


def test_bundle_markdown_empty_source():
    bundle = {"web": _ok("web", [])}
    md = bundle_to_markdown("q", bundle)
    assert "(no results)" in md
