# -*- coding: utf-8 -*-
"""MCP server exposing agentknows to any MCP client (Claude Desktop, Cursor, ...).

Run:  agentknows-mcp          (stdio transport)

Claude Desktop config:
    {"mcpServers": {"agentknows": {"command": "agentknows-mcp"}}}
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import Reach
from .errors import ReachError
from .models import ReachResult

mcp = FastMCP(
    "agentknows",
    instructions=(
        "Unified internet access across Western + Indian platforms: web, YouTube, "
        "GitHub, RSS, Twitter/X, Hacker News, Reddit, NSE/BSE/US stocks, Indian + "
        "Western news, Discourse forums (ValuePickr...). Start with reach_platforms "
        "to see capabilities; reach_doctor diagnoses broken channels and returns "
        "fix prescriptions."
    ),
)

_reach: Reach | None = None


def _client() -> Reach:
    global _reach
    if _reach is None:
        _reach = Reach()
    return _reach


def _safe(fn, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        result: ReachResult = fn(*args, **kwargs)
        return result.to_dict()
    except ReachError as exc:
        return ReachResult.failure(
            exc.platform or "unknown", str(exc), backend=exc.backend or "", fix=exc.fix
        ).to_dict()


@mcp.tool()
def reach_read(url: str, max_chars: int = 40000) -> dict:
    """Read any URL as clean text/Markdown. Routes automatically:
    YouTube → transcript+metadata, GitHub → repo/issue/PR via gh, Hacker News →
    story+comments, Discourse forums → topic+posts, RSS feeds → entries,
    anything else → Jina Reader. Also reads stock tickers (pass a symbol like
    RELIANCE or AAPL to reach_search with platform=stocks, or a plain URL here).
    If a platform's tool is missing, degrades to Jina Reader and includes the
    setup hint in meta.setup_hint."""
    result = _safe(_client().read, url)
    content = result.get("content")
    if content and len(content) > max_chars:
        result["content"] = content[:max_chars] + f"\n\n[truncated at {max_chars} chars]"
        result.setdefault("meta", {})["truncated"] = True
    return result


@mcp.tool()
def reach_search(query: str, platform: str = "web", limit: int = 10) -> dict:
    """Search a platform. platform: web (Exa semantic search), youtube, github,
    hackernews, twitter, stocks (NSE/BSE/US symbol lookup), news (Indian+Western
    headlines), discourse (ValuePickr by default, any forum via kwargs),
    reddit/facebook/instagram (need OpenCLI + logged-in browser session)."""
    return _safe(_client().search, query, platform=platform, limit=limit)


@mcp.tool()
def reach_hot(platform: str, limit: int = 20, region: str = "") -> dict:
    """Trending listings: hackernews (front page), news (fresh Indian/Western
    headlines; region: india | western), discourse (top forum topics)."""
    kwargs = {"region": region} if region else {}
    return _safe(_client().hot, platform, limit=limit, **kwargs)


@mcp.tool()
def reach_research(query: str, region: str = "", limit: int = 8) -> dict:
    """Cross-platform research: fans the query out in parallel across web (Exa),
    Hacker News, Indian+Western news, YouTube, ValuePickr, and Twitter/Reddit if
    configured. Returns one merged Markdown bundle with per-source coverage notes
    — synthesize it yourself. region: "india" | "western" | "" (both)."""
    return _safe(
        _client().research, query,
        region=region or None, limit=limit, report=False,
    )


@mcp.tool()
def reach_doctor() -> dict:
    """Health-check every channel: status (ok/warn/off/error), the backend
    currently serving it, and a runnable fix prescription when broken."""
    return _safe(_client().doctor)


@mcp.tool()
def reach_platforms() -> dict:
    """List every platform and which operations (read/search/hot) it supports."""
    return {"ok": True, "platforms": _client().platforms()}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
