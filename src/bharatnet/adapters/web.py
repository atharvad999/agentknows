# -*- coding: utf-8 -*-
"""Web — read any URL as Markdown via Jina Reader; search via Exa (mcporter)."""

from __future__ import annotations

import os
import time
from typing import Any

import requests

from ..errors import UpstreamFailure
from ..models import ReachResult
from .base import Adapter
from .exa import exa_search

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
_RETRIES = 2


class WebAdapter(Adapter):
    platform = "web"

    def read(self, target: str, **kwargs: Any) -> ReachResult:
        url = target if target.startswith(("http://", "https://")) else f"https://{target}"
        headers = {"User-Agent": _UA, "Accept": "text/plain"}
        # Optional key raises Jina's rate limit; works fine without one.
        api_key = os.environ.get("JINA_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        last_error: Exception | None = None
        for attempt in range(_RETRIES + 1):
            try:
                resp = requests.get(
                    f"https://r.jina.ai/{url}", headers=headers, timeout=60
                )
                resp.raise_for_status()
                return ReachResult(
                    ok=True,
                    platform=self.platform,
                    backend="jina-reader",
                    kind="document",
                    content=resp.text,
                    meta={"url": url},
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < _RETRIES:
                    time.sleep(1.5 * (attempt + 1))
        raise UpstreamFailure(
            f"Jina Reader failed for {url}: {last_error}",
            platform=self.platform,
            backend="jina-reader",
            fix="Retry later, or set JINA_API_KEY for a higher rate limit.",
        )

    def search(self, query: str, limit: int = 10, **kwargs: Any) -> ReachResult:
        return exa_search(query, limit=limit)
