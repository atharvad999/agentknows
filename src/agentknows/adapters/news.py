# -*- coding: utf-8 -*-
"""News — curated Indian + Western RSS pack over feedparser. Zero config.

search() is keyword-filter over fresh headlines (not a search engine — for
deep news search use the web platform / Exa).
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ..models import Item, ReachResult
from .base import Adapter


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()

FEEDS: dict[str, dict[str, str]] = {
    "india": {
        "economic-times": "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
        "livemint": "https://www.livemint.com/rss/news",
        "the-hindu": "https://www.thehindu.com/news/national/feeder/default.rss",
        "times-of-india": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        "moneycontrol": "https://www.moneycontrol.com/rss/MCtopnews.xml",
    },
    "western": {
        "bbc-world": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "guardian-world": "https://www.theguardian.com/world/rss",
        "techcrunch": "https://techcrunch.com/feed/",
        "the-verge": "https://www.theverge.com/rss/index.xml",
        "ars-technica": "https://feeds.arstechnica.com/arstechnica/index",
    },
}


def _fetch_feed(source: str, url: str, per_feed: int) -> list[Item]:
    import feedparser

    try:
        feed = feedparser.parse(url)
    except Exception:
        return []
    return [
        Item(
            title=e.get("title", ""),
            url=e.get("link", ""),
            snippet=_clean(e.get("summary") or "")[:300],
            extra={"source": source, "published": e.get("published") or e.get("updated") or ""},
        )
        for e in feed.entries[:per_feed]
    ]


def _region_feeds(region: str | None) -> dict[str, str]:
    if region in FEEDS:
        return FEEDS[region]
    merged: dict[str, str] = {}
    for group in FEEDS.values():
        merged.update(group)
    return merged


class NewsAdapter(Adapter):
    platform = "news"

    def hot(self, *, region: str | None = None, limit: int = 30, **kwargs: Any) -> ReachResult:
        """Fresh headlines. region: 'india' | 'western' | None (both)."""
        feeds = _region_feeds(region)
        per_feed = max(3, limit // len(feeds))
        items: list[Item] = []
        failed: list[str] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(_fetch_feed, name, url, per_feed): name
                for name, url in feeds.items()
            }
            for fut in as_completed(futures):
                rows = fut.result()
                if rows:
                    items.extend(rows)
                else:
                    failed.append(futures[fut])
        # Interleave sources instead of sorting on inconsistent date formats.
        by_source: dict[str, list[Item]] = {}
        for it in items:
            by_source.setdefault(it.extra["source"], []).append(it)
        mixed: list[Item] = []
        while len(mixed) < limit and any(by_source.values()):
            for rows in by_source.values():
                if rows:
                    mixed.append(rows.pop(0))
        meta: dict[str, Any] = {"region": region or "all", "sources": sorted(feeds)}
        if failed:
            meta["failed_sources"] = sorted(failed)
        return ReachResult(
            ok=True, platform=self.platform, backend="rss-pack", kind="items",
            items=mixed[:limit], meta=meta,
        )

    def search(self, query: str, limit: int = 10, *, region: str | None = None, **kwargs: Any) -> ReachResult:
        headlines = self.hot(region=region, limit=200)
        terms = [t for t in query.lower().split() if t]
        matched = [
            it for it in headlines.items
            if all(t in f"{it.title} {it.snippet}".lower() for t in terms)
        ]
        return ReachResult(
            ok=True, platform=self.platform, backend="rss-pack", kind="items",
            items=matched[:limit],
            meta={
                "query": query,
                "region": region or "all",
                "note": "keyword filter over fresh headlines; use platform=web for deep news search",
            },
        )
