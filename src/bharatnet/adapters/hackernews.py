# -*- coding: utf-8 -*-
"""Hacker News — Algolia public API. Zero config."""

from __future__ import annotations

import re
from typing import Any

import requests

from ..errors import UpstreamFailure
from ..models import Item, ReachResult
from .base import Adapter

_API = "https://hn.algolia.com/api/v1"
_ID_RE = re.compile(r"(?:item\?id=|items/)(\d+)")
_MAX_COMMENTS = 40


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    for ent, ch in (("&#x27;", "'"), ("&quot;", '"'), ("&amp;", "&"),
                    ("&lt;", "<"), ("&gt;", ">"), ("&#x2F;", "/")):
        text = text.replace(ent, ch)
    return re.sub(r"\s+", " ", text).strip()


def _get(url: str) -> dict:
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise UpstreamFailure(
            f"Hacker News API failed: {exc}", platform="hackernews", backend="algolia"
        ) from exc


def _flatten_comments(node: dict, depth: int, out: list[str]) -> None:
    if len(out) >= _MAX_COMMENTS:
        return
    text = _strip_html(node.get("text") or "")
    if text:
        indent = "  " * depth
        out.append(f"{indent}- **{node.get('author', '?')}**: {text[:600]}")
    for child in node.get("children") or []:
        _flatten_comments(child, min(depth + 1, 4), out)


class HackerNewsAdapter(Adapter):
    platform = "hackernews"

    def read(self, target: str, **kwargs: Any) -> ReachResult:
        """target: HN item URL or bare numeric id."""
        m = _ID_RE.search(target)
        item_id = m.group(1) if m else target.strip()
        if not item_id.isdigit():
            raise UpstreamFailure(
                f"Cannot parse HN item id from {target!r}.", platform=self.platform
            )
        data = _get(f"{_API}/items/{item_id}")
        comments: list[str] = []
        for child in data.get("children") or []:
            _flatten_comments(child, 0, comments)
        parts = [f"# {data.get('title') or '(comment)'}"]
        if data.get("url"):
            parts.append(f"\nLink: {data['url']}")
        if data.get("text"):
            parts.append("\n" + _strip_html(data["text"]))
        if comments:
            parts.append(f"\n## Comments (top {len(comments)})\n")
            parts.append("\n".join(comments))
        return ReachResult(
            ok=True, platform=self.platform, backend="algolia", kind="document",
            content="\n".join(parts),
            meta={
                "id": data.get("id"),
                "author": data.get("author"),
                "points": data.get("points"),
                "hn_url": f"https://news.ycombinator.com/item?id={item_id}",
            },
        )

    def search(self, query: str, limit: int = 10, *, recent: bool = False, **kwargs: Any) -> ReachResult:
        endpoint = "search_by_date" if recent else "search"
        data = _get(f"{_API}/{endpoint}?query={requests.utils.quote(query)}&hitsPerPage={limit}&tags=story")
        items = [
            Item(
                title=h.get("title") or "",
                url=h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                snippet=_strip_html(h.get("story_text") or "")[:300],
                extra={
                    "points": h.get("points"),
                    "comments": h.get("num_comments"),
                    "hn_id": h.get("objectID"),
                },
            )
            for h in data.get("hits", [])
        ]
        return ReachResult(
            ok=True, platform=self.platform, backend="algolia", kind="items",
            items=items, meta={"query": query},
        )

    def hot(self, *, limit: int = 20, **kwargs: Any) -> ReachResult:
        data = _get(f"{_API}/search?tags=front_page&hitsPerPage={limit}")
        items = [
            Item(
                title=h.get("title") or "",
                url=h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                extra={"points": h.get("points"), "comments": h.get("num_comments"),
                       "hn_id": h.get("objectID")},
            )
            for h in data.get("hits", [])
        ]
        return ReachResult(
            ok=True, platform=self.platform, backend="algolia", kind="items",
            items=items, meta={"list": "front_page"},
        )
