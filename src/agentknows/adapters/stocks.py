# -*- coding: utf-8 -*-
"""Stocks — NSE/BSE (India) + US/global quotes via yfinance. Zero config.

Indian tickers use Yahoo suffixes: RELIANCE.NS (NSE), 500325.BO (BSE).
A bare symbol that fails as-is is retried with .NS then .BO, so
`read("RELIANCE")` just works.
"""

from __future__ import annotations

from typing import Any

from ..errors import SetupRequired, UpstreamFailure
from ..models import Item, ReachResult
from .base import Adapter

_FIX = "uv pip install yfinance   # or: pip install yfinance"

_QUOTE_KEYS = (
    ("currentPrice", "price"),
    ("regularMarketPrice", "price"),
    ("currency", "currency"),
    ("marketCap", "market_cap"),
    ("trailingPE", "pe_ttm"),
    ("priceToBook", "pb"),
    ("fiftyTwoWeekHigh", "52w_high"),
    ("fiftyTwoWeekLow", "52w_low"),
    ("regularMarketDayHigh", "day_high"),
    ("regularMarketDayLow", "day_low"),
    ("regularMarketVolume", "volume"),
    ("dividendYield", "dividend_yield"),
    ("exchange", "exchange"),
)


def _yf():
    try:
        import yfinance
    except ImportError as exc:
        raise SetupRequired(
            "Stock quotes need yfinance.", platform="stocks", backend="yfinance", fix=_FIX
        ) from exc
    return yfinance


class StocksAdapter(Adapter):
    platform = "stocks"

    def read(self, target: str, **kwargs: Any) -> ReachResult:
        """target: ticker symbol — RELIANCE.NS, TCS, AAPL, 500325.BO..."""
        yf = _yf()
        symbol = target.strip().upper()
        candidates = [symbol]
        if "." not in symbol:
            candidates += [f"{symbol}.NS", f"{symbol}.BO"]

        info: dict | None = None
        resolved = symbol
        for cand in candidates:
            try:
                data = yf.Ticker(cand).info
            except Exception:
                continue
            # Yahoo returns a near-empty dict for unknown symbols.
            if data and (data.get("regularMarketPrice") or data.get("currentPrice")):
                info, resolved = data, cand
                break
        if info is None:
            raise UpstreamFailure(
                f"No quote found for {target!r} (tried {', '.join(candidates)}).",
                platform=self.platform,
                backend="yfinance",
                fix="Use a Yahoo Finance symbol: RELIANCE.NS / 500325.BO / AAPL.",
            )

        meta: dict[str, Any] = {"symbol": resolved, "name": info.get("longName") or info.get("shortName")}
        for src, dst in _QUOTE_KEYS:
            if info.get(src) is not None and dst not in meta:
                meta[dst] = info[src]
        lines = [f"# {meta.get('name') or resolved} ({resolved})", ""]
        lines += [f"- {k}: {v}" for k, v in meta.items() if k not in ("symbol", "name")]
        return ReachResult(
            ok=True, platform=self.platform, backend="yfinance", kind="document",
            content="\n".join(lines), meta=meta,
        )

    def search(self, query: str, limit: int = 10, **kwargs: Any) -> ReachResult:
        yf = _yf()
        try:
            hits = yf.Search(query, max_results=limit).quotes
        except Exception as exc:
            raise UpstreamFailure(
                f"Yahoo Finance search failed: {exc}", platform=self.platform, backend="yfinance"
            ) from exc
        items = [
            Item(
                title=f"{h.get('shortname') or h.get('longname') or ''} ({h.get('symbol')})",
                url=f"https://finance.yahoo.com/quote/{h.get('symbol')}",
                extra={
                    "exchange": h.get("exchange"),
                    "type": h.get("quoteType"),
                },
            )
            for h in hits[:limit]
            if h.get("symbol")
        ]
        return ReachResult(
            ok=True, platform=self.platform, backend="yfinance", kind="items",
            items=items, meta={"query": query},
        )
