# -*- coding: utf-8 -*-
import pytest

from reachkit.adapters.base import Adapter
from reachkit.client import Reach
from reachkit.errors import SetupRequired, UnsupportedOperation
from reachkit.models import ReachResult


def make_reach(**kwargs):
    # config=False sentinel avoids touching ~/.agent-reach in tests
    return Reach(config=False, **kwargs)


def test_read_falls_back_to_web(monkeypatch):
    reach = make_reach(fallback_to_web=True)

    def boom(url, **kw):
        raise SetupRequired("tool missing", platform="twitter", fix="pipx install twitter-cli")

    def fake_web(url, **kw):
        return ReachResult(ok=True, platform="web", backend="jina-reader",
                           kind="document", content="page text")

    monkeypatch.setattr(reach._registry["twitter"], "read", boom)
    monkeypatch.setattr(reach._registry["web"], "read", fake_web)

    result = reach.read("https://x.com/user/status/1")
    assert result.ok
    assert result.meta["fallback"] is True
    assert "twitter-cli" in result.meta["setup_hint"]


def test_read_no_fallback_raises(monkeypatch):
    reach = make_reach(fallback_to_web=False)

    def boom(url, **kw):
        raise SetupRequired("tool missing", platform="twitter")

    monkeypatch.setattr(reach._registry["twitter"], "read", boom)
    with pytest.raises(SetupRequired):
        reach.read("https://x.com/user/status/1")


def test_unknown_search_platform():
    with pytest.raises(Exception) as exc:
        make_reach().search("q", platform="myspace")
    assert "myspace" in str(exc.value)


def test_hot_unsupported():
    with pytest.raises(UnsupportedOperation):
        make_reach().hot("web")


def test_platforms_capability_map():
    caps = make_reach().platforms()
    assert caps["web"]["read"] and caps["web"]["search"]
    assert caps["hackernews"]["hot"] and caps["news"]["hot"] and caps["discourse"]["hot"]
    assert caps["stocks"]["read"] and caps["stocks"]["search"]
    assert not caps["rss"]["search"]
    assert "v2ex" not in caps and "bilibili" not in caps and "xueqiu" not in caps
    # base-class methods must not count as support
    assert type(Adapter.read) is type(Adapter.search)
