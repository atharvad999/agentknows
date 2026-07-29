# -*- coding: utf-8 -*-
"""Unified result shapes returned by every reachkit adapter.

Agent-Reach routes each platform to a different upstream tool with a
different output format; reachkit normalizes all of them into ReachResult
so callers (SDK users, MCP clients) parse exactly one shape.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class Item:
    """One search hit / feed entry / listing row."""

    title: str = ""
    url: str = ""
    snippet: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReachResult:
    """Envelope for every read/search/doctor call.

    kind:
      - "document": full-text content in `content`
      - "items": list results in `items`
      - "status": doctor / capability report in `meta`
    """

    ok: bool
    platform: str
    backend: str
    kind: str
    content: Optional[str] = None
    items: list[Item] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    fix: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Drop empty optionals so MCP/JSON output stays lean.
        return {k: v for k, v in d.items() if v not in (None, [], {})} | {"ok": self.ok}

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def failure(
        cls,
        platform: str,
        error: str,
        *,
        backend: str = "",
        fix: str | None = None,
    ) -> "ReachResult":
        return cls(
            ok=False,
            platform=platform,
            backend=backend,
            kind="status",
            error=error,
            fix=fix,
        )
