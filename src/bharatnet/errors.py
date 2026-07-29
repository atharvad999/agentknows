# -*- coding: utf-8 -*-
"""Errors carrying an actionable fix prescription, mirroring agent-reach doctor."""

from __future__ import annotations


class ReachError(RuntimeError):
    """Base error. `fix` is a human/agent-runnable prescription when known."""

    def __init__(
        self,
        message: str,
        *,
        platform: str | None = None,
        backend: str | None = None,
        fix: str | None = None,
    ):
        super().__init__(message)
        self.platform = platform
        self.backend = backend
        self.fix = fix


class SetupRequired(ReachError):
    """The upstream tool for this platform is missing or unconfigured."""


class UnsupportedOperation(ReachError):
    """This platform does not support the requested operation (read/search)."""


class UpstreamFailure(ReachError):
    """The upstream tool ran but failed (network, rate limit, ban, parse)."""
