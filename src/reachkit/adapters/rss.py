# -*- coding: utf-8 -*-
"""RSS/Atom — feedparser, normalized to items."""

from __future__ import annotations

from typing import Any

from ..errors import UpstreamFailure
from ..models import Item, ReachResult
from .base import Adapter


class RSSAdapter(Adapter):
    platform = "rss"

    def read(self, target: str, *, limit: int = 20, **kwargs: Any) -> ReachResult:
        import feedparser  # deferred: keeps import cheap when RSS unused

        feed = feedparser.parse(target)
        if getattr(feed, "bozo", False) and not feed.entries:
            raise UpstreamFailure(
                f"Not a parseable feed: {target} ({feed.get('bozo_exception', '')})",
                platform=self.platform,
                backend="feedparser",
            )
        items = [
            Item(
                title=e.get("title", ""),
                url=e.get("link", ""),
                snippet=(e.get("summary") or "")[:500],
                extra={"published": e.get("published") or e.get("updated") or ""},
            )
            for e in feed.entries[:limit]
        ]
        return ReachResult(
            ok=True, platform=self.platform, backend="feedparser", kind="items",
            items=items,
            meta={
                "feed_title": feed.feed.get("title", ""),
                "feed_url": target,
                "entry_count": len(feed.entries),
            },
        )
