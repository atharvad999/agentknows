# -*- coding: utf-8 -*-
from reachkit.router import known_platforms, resolve_platform


def test_youtube():
    assert resolve_platform("https://www.youtube.com/watch?v=abc") == "youtube"
    assert resolve_platform("https://youtu.be/abc") == "youtube"


def test_github():
    assert resolve_platform("https://github.com/o/r/issues/5") == "github"


def test_hackernews():
    assert resolve_platform("https://news.ycombinator.com/item?id=1") == "hackernews"


def test_discourse():
    assert resolve_platform("https://forum.valuepickr.com/t/some-topic/123") == "discourse"


def test_rss_heuristic():
    assert resolve_platform("https://example.com/feed.xml") == "rss"


def test_web_catchall():
    assert resolve_platform("https://example.com/article") == "web"


def test_chinese_platforms_fall_through_to_web():
    assert resolve_platform("https://www.bilibili.com/video/BV1xx411c7mD") == "web"
    assert resolve_platform("https://www.v2ex.com/t/1000000") == "web"
    assert resolve_platform("https://xueqiu.com/S/SH600519") == "web"


def test_platform_list_scope():
    names = known_platforms()
    assert {"web", "youtube", "stocks", "hackernews", "discourse", "news"} <= set(names)
    assert not {"bilibili", "v2ex", "xueqiu", "xiaohongshu", "xiaoyuzhou"} & set(names)
