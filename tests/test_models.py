# -*- coding: utf-8 -*-
import json

from reachkit.models import Item, ReachResult


def test_to_dict_drops_empties():
    r = ReachResult(ok=True, platform="web", backend="jina", kind="document", content="hi")
    d = r.to_dict()
    assert d["ok"] is True
    assert "error" not in d and "items" not in d and "fix" not in d
    assert d["content"] == "hi"


def test_failure_carries_fix():
    r = ReachResult.failure("twitter", "no cookies", fix="pipx install twitter-cli")
    d = r.to_dict()
    assert d["ok"] is False
    assert d["fix"].startswith("pipx")


def test_json_roundtrip_unicode():
    r = ReachResult(
        ok=True, platform="bilibili", backend="api", kind="items",
        items=[Item(title="AI 教程", url="https://b23.tv/x")],
    )
    parsed = json.loads(r.to_json())
    assert parsed["items"][0]["title"] == "AI 教程"
