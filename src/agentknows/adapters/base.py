# -*- coding: utf-8 -*-
"""Adapter interface: one adapter per platform, normalizing upstream output."""

from __future__ import annotations

from typing import Any

from ..errors import UnsupportedOperation
from ..models import ReachResult


class Adapter:
    platform: str = ""

    def __init__(self, config: Any = None):
        # agent_reach.config.Config, shared across adapters (cookies/tokens).
        self.config = config

    def read(self, target: str, **kwargs: Any) -> ReachResult:
        raise UnsupportedOperation(
            f"{self.platform} does not support read()", platform=self.platform
        )

    def search(self, query: str, limit: int = 10, **kwargs: Any) -> ReachResult:
        raise UnsupportedOperation(
            f"{self.platform} does not support search()", platform=self.platform
        )
