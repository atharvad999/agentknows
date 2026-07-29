# -*- coding: utf-8 -*-
"""Structured health report: agent-reach channel probes + bharatnet-native channels."""

from __future__ import annotations

from typing import Any

from agent_reach.channels import ALL_CHANNELS

from .models import ReachResult
from .router import EXCLUDED_CHANNELS

_TIER_LABELS = {0: "zero-config", 1: "free-key", 2: "login-required"}


def _native_checks() -> list[dict[str, Any]]:
    """Probes for platforms bharatnet adds on top of agent-reach."""
    rows: list[dict[str, Any]] = []

    try:
        import yfinance  # noqa: F401

        rows.append({"platform": "stocks", "status": "ok", "active_backend": "yfinance",
                     "tier": "zero-config", "detail": "NSE/BSE/US quotes + symbol search"})
    except ImportError:
        rows.append({"platform": "stocks", "status": "off", "active_backend": None,
                     "tier": "zero-config", "detail": "pip install yfinance"})

    rows.append({"platform": "hackernews", "status": "ok", "active_backend": "algolia",
                 "tier": "zero-config", "detail": "search/read/front-page via public API"})
    rows.append({"platform": "discourse", "status": "ok", "active_backend": "discourse-api",
                 "tier": "zero-config",
                 "detail": "any Discourse forum; default forum.valuepickr.com (IN stocks)"})
    rows.append({"platform": "news", "status": "ok", "active_backend": "rss-pack",
                 "tier": "zero-config", "detail": "Indian + Western headlines (10 curated feeds)"})
    return rows


def doctor(config: Any = None) -> ReachResult:
    """Probe every channel; report status + which backend serves it right now."""
    report = []
    for channel in ALL_CHANNELS:
        if channel.name in EXCLUDED_CHANNELS:
            continue
        try:
            status, message = channel.check(config)
        except Exception as exc:  # a broken probe must not kill the whole report
            status, message = "error", f"probe crashed: {exc}"
        report.append(
            {
                "platform": channel.name,
                "status": status,  # ok | warn | off | error
                "active_backend": channel.active_backend,
                "tier": _TIER_LABELS.get(channel.tier, str(channel.tier)),
                "detail": message,
            }
        )
    report.extend(_native_checks())
    ok_count = sum(1 for r in report if r["status"] == "ok")
    return ReachResult(
        ok=True,
        platform="*",
        backend="bharatnet",
        kind="status",
        meta={
            "channels": report,
            "summary": f"{ok_count}/{len(report)} channels fully OK",
        },
    )
