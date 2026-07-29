# -*- coding: utf-8 -*-
"""Twitter/X — twitter-cli with credentials injected per-call.

agent-reach's boundary: saved cookies (`agent-reach configure twitter-cookies`)
are only *checked* by doctor; the upstream `twitter` command needs
TWITTER_AUTH_TOKEN / TWITTER_CT0 in its own environment. We inject them into
the child process only — never into the parent env, never logged.
"""

from __future__ import annotations

from typing import Any

from ..errors import SetupRequired
from ..models import ReachResult
from ..proc import run
from .base import Adapter

_FIX = (
    "pipx install twitter-cli\n"
    "agent-reach configure twitter-cookies   # guided cookie export (use a burner account)"
)


class TwitterAdapter(Adapter):
    platform = "twitter"

    def _env(self) -> dict[str, str]:
        import os

        auth = os.environ.get("TWITTER_AUTH_TOKEN")
        ct0 = os.environ.get("TWITTER_CT0")
        if not (auth and ct0) and self.config is not None:
            auth = auth or self.config.get("twitter_auth_token")
            ct0 = ct0 or self.config.get("twitter_ct0")
        if not (auth and ct0):
            raise SetupRequired(
                "Twitter needs cookies (auth_token + ct0).",
                platform=self.platform,
                backend="twitter-cli",
                fix=_FIX,
            )
        return {"TWITTER_AUTH_TOKEN": auth, "TWITTER_CT0": ct0}

    def read(self, target: str, **kwargs: Any) -> ReachResult:
        out = run(
            ["twitter", "tweet", target],
            platform=self.platform, env=self._env(), timeout=45, fix=_FIX,
        )
        return ReachResult(
            ok=True, platform=self.platform, backend="twitter-cli", kind="document",
            content=out.strip(), meta={"target": target},
        )

    def search(self, query: str, limit: int = 10, **kwargs: Any) -> ReachResult:
        out = run(
            ["twitter", "search", query, "-n", str(limit)],
            platform=self.platform, env=self._env(), timeout=60, fix=_FIX,
        )
        return ReachResult(
            ok=True, platform=self.platform, backend="twitter-cli", kind="document",
            content=out.strip(), meta={"query": query, "note": "raw twitter-cli output"},
        )
