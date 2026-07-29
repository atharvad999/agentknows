# -*- coding: utf-8 -*-
"""Discourse forums — public JSON API, zero config.

Default forum: ValuePickr (India's best long-form stock-discussion forum).
Works against ANY Discourse instance via the `forum` kwarg — every Discourse
site exposes /search.json, /t/<id>.json and /top.json publicly.
"""

from __future__ import annotations

import re
from typing import Any

import requests

from ..errors import UpstreamFailure
from ..models import Item, ReachResult
from .base import Adapter

DEFAULT_FORUM = "https://forum.valuepickr.com"

#: Hosts routed here automatically by the URL router.
KNOWN_HOSTS = ("forum.valuepickr.com",)

_TOPIC_RE = re.compile(r"(https?://[^/]+)/t/(?:[^/]+/)?(\d+)")
_UA = "bharatnet/0.1 (+https://github.com/Panniantong/Agent-Reach)"
_MAX_POSTS = 30


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    for ent, ch in (("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"),
                    ("&gt;", ">"), ("&#39;", "'"), ("&nbsp;", " ")):
        text = text.replace(ent, ch)
    return re.sub(r"[ \t]+", " ", text).strip()


def _get(url: str) -> dict:
    try:
        resp = requests.get(url, headers={"User-Agent": _UA, "Accept": "application/json"}, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise UpstreamFailure(
            f"Discourse API failed for {url}: {exc}", platform="discourse", backend="discourse-api"
        ) from exc


class DiscourseAdapter(Adapter):
    platform = "discourse"

    def read(self, target: str, **kwargs: Any) -> ReachResult:
        """target: a Discourse topic URL, e.g. https://forum.valuepickr.com/t/slug/12345"""
        m = _TOPIC_RE.search(target)
        if not m:
            raise UpstreamFailure(
                f"Not a Discourse topic URL: {target!r} (expected .../t/<slug>/<id>).",
                platform=self.platform,
            )
        base, topic_id = m.group(1), m.group(2)
        data = _get(f"{base}/t/{topic_id}.json")
        posts = (data.get("post_stream") or {}).get("posts") or []
        body = [f"# {data.get('title', '')}\n"]
        for p in posts[:_MAX_POSTS]:
            text = _strip_html(p.get("cooked") or "")
            if text:
                body.append(f"**{p.get('username', '?')}**: {text[:1500]}\n")
        return ReachResult(
            ok=True, platform=self.platform, backend="discourse-api", kind="document",
            content="\n".join(body),
            meta={
                "forum": base,
                "topic_id": int(topic_id),
                "posts_count": data.get("posts_count"),
                "views": data.get("views"),
                "url": f"{base}/t/{topic_id}",
                "posts_shown": min(len(posts), _MAX_POSTS),
                "truncated": (data.get("posts_count") or 0) > min(len(posts), _MAX_POSTS),
            },
        )

    def search(self, query: str, limit: int = 10, *, forum: str = DEFAULT_FORUM, **kwargs: Any) -> ReachResult:
        base = forum.rstrip("/")
        data = _get(f"{base}/search.json?q={requests.utils.quote(query)}")
        topics = {t["id"]: t for t in data.get("topics", [])}
        blurbs: dict[int, str] = {}
        for p in data.get("posts", []):
            tid = p.get("topic_id")
            if tid is not None and tid not in blurbs:
                blurbs[tid] = _strip_html(p.get("blurb") or "")
        items = [
            Item(
                title=t.get("title", ""),
                url=f"{base}/t/{t.get('slug', '')}/{tid}",
                snippet=blurbs.get(tid, "")[:300],
                extra={"posts_count": t.get("posts_count")},
            )
            for tid, t in list(topics.items())[:limit]
        ]
        return ReachResult(
            ok=True, platform=self.platform, backend="discourse-api", kind="items",
            items=items, meta={"query": query, "forum": base},
        )

    def hot(self, *, limit: int = 20, forum: str = DEFAULT_FORUM, period: str = "weekly", **kwargs: Any) -> ReachResult:
        base = forum.rstrip("/")
        data = _get(f"{base}/top.json?period={period}")
        topics = (data.get("topic_list") or {}).get("topics") or []
        items = [
            Item(
                title=t.get("title", ""),
                url=f"{base}/t/{t.get('slug', '')}/{t.get('id')}",
                extra={"posts_count": t.get("posts_count"), "views": t.get("views"),
                       "likes": t.get("like_count")},
            )
            for t in topics[:limit]
        ]
        return ReachResult(
            ok=True, platform=self.platform, backend="discourse-api", kind="items",
            items=items, meta={"forum": base, "period": period},
        )
