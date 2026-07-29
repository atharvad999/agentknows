# -*- coding: utf-8 -*-
"""Login-gated platforms with no stable headless path: OpenCLI if present,
otherwise a SetupRequired carrying agent-reach's prescription.

Covers: reddit, facebook, instagram. These platforms only work through a
real desktop browser session (OpenCLI) or a manual cookie export — reachkit
never automates login or reads browser cookies itself.
"""

from __future__ import annotations

from typing import Any

from ..errors import SetupRequired
from ..models import ReachResult
from ..proc import run, which
from .base import Adapter

_PRESCRIPTIONS = {
    "reddit": (
        "No zero-config path (anonymous API is blocked). Either:\n"
        "  - desktop: install OpenCLI (reuses your Chrome session): agent-reach install --channels opencli\n"
        "  - server: pipx install rdt-cli + cookie config"
    ),
    "facebook": "Desktop OpenCLI only (browser session): agent-reach install --channels opencli",
    "instagram": "Desktop OpenCLI only (browser session): agent-reach install --channels opencli",
}


class OpenCLIAdapter(Adapter):
    """One instance per platform; shells `opencli <platform> ...` when available."""

    def __init__(self, platform: str, config: Any = None):
        super().__init__(config)
        self.platform = platform

    def _require_opencli(self) -> None:
        if which("opencli") is None:
            raise SetupRequired(
                f"{self.platform} needs a logged-in browser session via OpenCLI.",
                platform=self.platform,
                backend="opencli",
                fix=_PRESCRIPTIONS.get(self.platform, "agent-reach install --channels opencli"),
            )

    def read(self, target: str, **kwargs: Any) -> ReachResult:
        self._require_opencli()
        out = run(
            ["opencli", self.platform, "read", target, "-f", "yaml"],
            platform=self.platform, timeout=60,
            fix=_PRESCRIPTIONS.get(self.platform),
        )
        return ReachResult(
            ok=True, platform=self.platform, backend="opencli", kind="document",
            content=out.strip(), meta={"target": target, "note": "raw OpenCLI YAML"},
        )

    def search(self, query: str, limit: int = 10, **kwargs: Any) -> ReachResult:
        self._require_opencli()
        out = run(
            ["opencli", self.platform, "search", query, "-f", "yaml"],
            platform=self.platform, timeout=60,
            fix=_PRESCRIPTIONS.get(self.platform),
        )
        return ReachResult(
            ok=True, platform=self.platform, backend="opencli", kind="document",
            content=out.strip(), meta={"query": query, "note": "raw OpenCLI YAML"},
        )
