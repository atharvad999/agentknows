# -*- coding: utf-8 -*-
"""Exa semantic web search via mcporter (the zero-key MCP route agent-reach sets up)."""

from __future__ import annotations

import json
import re

from ..errors import SetupRequired, UpstreamFailure
from ..models import Item, ReachResult
from ..proc import run, which

_FIX = (
    "npm install -g mcporter\n"
    "mcporter config add exa https://mcp.exa.ai/mcp --scope home"
)


def _parse_results(raw: str, limit: int) -> list[Item]:
    """Best-effort parse of mcporter's output into items.

    mcporter prints the MCP tool result, which for Exa contains a JSON blob
    with a `results` array. Fall back to empty (caller keeps raw text).
    """
    for match in re.finditer(r"\{.*\}", raw, re.DOTALL):
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        results = data.get("results")
        if isinstance(results, list):
            items = []
            for r in results[:limit]:
                if not isinstance(r, dict):
                    continue
                items.append(
                    Item(
                        title=str(r.get("title") or ""),
                        url=str(r.get("url") or ""),
                        snippet=str(r.get("text") or r.get("snippet") or "")[:500],
                        extra={
                            k: r[k]
                            for k in ("publishedDate", "author", "score")
                            if r.get(k) is not None
                        },
                    )
                )
            if items:
                return items
    return []


def _parse_text_blocks(raw: str, limit: int) -> list[Item]:
    """Parse mcporter's rendered 'Title: / URL: / Highlights:' text output."""
    items: list[Item] = []
    current: dict[str, str] | None = None
    snippet_lines: list[str] = []

    def flush():
        if current and current.get("url"):
            items.append(Item(
                title=current.get("title", ""),
                url=current["url"],
                snippet=" ".join(snippet_lines)[:500].strip(),
                extra={k: v for k, v in current.items() if k in ("published", "author")},
            ))

    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("Title:"):
            flush()
            current, snippet_lines = {"title": stripped[6:].strip()}, []
        elif current is not None and stripped.startswith("URL:"):
            current["url"] = stripped[4:].strip()
        elif current is not None and stripped.startswith("Published:"):
            current["published"] = stripped[10:].strip()
        elif current is not None and stripped.startswith("Author:"):
            current["author"] = stripped[7:].strip()
        elif current is not None and stripped and not stripped.startswith(("Highlights:", "...")):
            snippet_lines.append(stripped)
    flush()
    return items[:limit]


def exa_search(query: str, limit: int = 10) -> ReachResult:
    if which("mcporter") is None:
        raise SetupRequired(
            "Exa web search needs mcporter (free, no API key).",
            platform="web",
            backend="exa",
            fix=_FIX,
        )
    escaped = query.replace("\\", "\\\\").replace('"', '\\"')
    call = f'exa.web_search_exa(query: "{escaped}", numResults: {limit})'
    raw = run(
        ["mcporter", "call", call],
        platform="web",
        timeout=90,
        fix=_FIX,
    )
    if not raw.strip():
        raise UpstreamFailure("Exa returned empty output.", platform="web", backend="exa")
    items = _parse_results(raw, limit) or _parse_text_blocks(raw, limit)
    if items:
        return ReachResult(
            ok=True, platform="web", backend="exa", kind="items", items=items,
            meta={"query": query},
        )
    # Unparseable but non-empty: hand the raw text back rather than dropping it.
    return ReachResult(
        ok=True, platform="web", backend="exa", kind="document", content=raw.strip(),
        meta={"query": query, "note": "raw mcporter output; JSON parse failed"},
    )
