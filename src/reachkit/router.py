# -*- coding: utf-8 -*-
"""URL → platform resolution.

reachkit-native platforms (Hacker News, Discourse forums) are matched first;
then agent-reach's channel registry handles its platforms (`can_handle`).
Chinese channels are excluded — their URLs fall through to 'web' (Jina Reader
reads anything). Registry order matters: RSS heuristics before the catch-all.
"""

from __future__ import annotations

from urllib.parse import urlparse

from agent_reach.channels import ALL_CHANNELS

from .adapters.discourse import KNOWN_HOSTS as _DISCOURSE_HOSTS

#: agent-reach channels outside reachkit's Western+Indian scope.
EXCLUDED_CHANNELS = {"bilibili", "xiaohongshu", "v2ex", "xueqiu", "xiaoyuzhou"}

_NATIVE_HOSTS = {
    "news.ycombinator.com": "hackernews",
    **{h: "discourse" for h in _DISCOURSE_HOSTS},
}


def _host(url: str) -> str:
    try:
        return (urlparse(url if "://" in url else f"https://{url}").hostname or "").lower()
    except ValueError:
        return ""


def resolve_platform(url: str) -> str:
    """Return the platform name owning this URL ('web' is the catch-all)."""
    host = _host(url)
    if host in _NATIVE_HOSTS:
        return _NATIVE_HOSTS[host]
    for channel in ALL_CHANNELS:
        if channel.name in EXCLUDED_CHANNELS:
            continue
        try:
            if channel.can_handle(url):
                return channel.name
        except Exception:
            continue
    return "web"


def known_platforms() -> list[str]:
    names = [c.name for c in ALL_CHANNELS if c.name not in EXCLUDED_CHANNELS]
    return sorted(set(names) | set(_NATIVE_HOSTS.values()) | {"stocks", "news"})
