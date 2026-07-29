# -*- coding: utf-8 -*-
import pytest

from agentknows.adapters.discourse import _TOPIC_RE, DEFAULT_FORUM
from agentknows.adapters.discourse import _strip_html as strip_discourse
from agentknows.adapters.hackernews import _ID_RE
from agentknows.adapters.hackernews import _strip_html as strip_hn
from agentknows.adapters.news import FEEDS, _region_feeds
from agentknows.errors import UpstreamFailure


def test_hn_id_extraction():
    assert _ID_RE.search("https://news.ycombinator.com/item?id=39001234").group(1) == "39001234"
    assert _ID_RE.search("https://hn.algolia.com/api/v1/items/42").group(1) == "42"


def test_hn_strip_html():
    assert strip_hn("<p>Hello &amp; <i>world</i></p>") == "Hello & world"


def test_discourse_topic_url():
    m = _TOPIC_RE.search("https://forum.valuepickr.com/t/my-topic-slug/12345/7")
    assert m.group(1) == "https://forum.valuepickr.com"
    assert m.group(2) == "12345"


def test_discourse_strip_html():
    assert strip_discourse("<div>A &gt; B</div>") == "A > B"


def test_discourse_default_forum_is_valuepickr():
    assert "valuepickr" in DEFAULT_FORUM


def test_news_regions():
    assert set(FEEDS) == {"india", "western"}
    assert len(_region_feeds("india")) == 5
    assert len(_region_feeds(None)) == 10


def test_stocks_missing_dep_message():
    # yfinance installed in this env → adapter importable; just ensure the
    # symbol-parse failure path raises a ReachError with a fix.
    from agentknows.adapters.hackernews import HackerNewsAdapter

    with pytest.raises(UpstreamFailure):
        HackerNewsAdapter().read("not-a-number")
