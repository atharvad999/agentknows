# -*- coding: utf-8 -*-
"""Adapter registry: platform name → adapter instance.

Scope: Western + Indian platforms. Chinese channels (bilibili, xiaohongshu,
v2ex, xueqiu, xiaoyuzhou) are intentionally excluded; their URLs fall through
to the web (Jina Reader) catch-all.
"""

from __future__ import annotations

from typing import Any

from .base import Adapter
from .discourse import DiscourseAdapter
from .github import GitHubAdapter
from .guided import OpenCLIAdapter
from .hackernews import HackerNewsAdapter
from .news import NewsAdapter
from .rss import RSSAdapter
from .stocks import StocksAdapter
from .twitter import TwitterAdapter
from .web import WebAdapter
from .youtube import YouTubeAdapter


def build_registry(config: Any = None) -> dict[str, Adapter]:
    registry: dict[str, Adapter] = {
        "web": WebAdapter(config),
        "youtube": YouTubeAdapter(config),
        "github": GitHubAdapter(config),
        "rss": RSSAdapter(config),
        "twitter": TwitterAdapter(config),
        "stocks": StocksAdapter(config),
        "hackernews": HackerNewsAdapter(config),
        "discourse": DiscourseAdapter(config),
        "news": NewsAdapter(config),
    }
    for platform in ("reddit", "facebook", "instagram"):
        registry[platform] = OpenCLIAdapter(platform, config)
    return registry


__all__ = ["Adapter", "build_registry"]
