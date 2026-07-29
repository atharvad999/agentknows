# -*- coding: utf-8 -*-
"""Subprocess helper for shelling out to upstream CLIs (yt-dlp, gh, bili, twitter...)."""

from __future__ import annotations

import os
import shutil
import subprocess

from .errors import SetupRequired, UpstreamFailure


def which(binary: str) -> str | None:
    return shutil.which(binary)


def run(
    cmd: list[str],
    *,
    platform: str,
    timeout: int = 60,
    env: dict[str, str] | None = None,
    fix: str | None = None,
) -> str:
    """Run a CLI command, return stdout. Raises with a fix prescription on failure."""
    binary = cmd[0]
    if which(binary) is None:
        raise SetupRequired(
            f"`{binary}` is not installed (needed for {platform}).",
            platform=platform,
            backend=binary,
            fix=fix or f"Install `{binary}`, then re-run. `agent-reach doctor` shows the exact prescription.",
        )
    full_env = {**os.environ, **(env or {})}
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=full_env,
        )
    except subprocess.TimeoutExpired as exc:
        raise UpstreamFailure(
            f"`{binary}` timed out after {timeout}s.",
            platform=platform,
            backend=binary,
        ) from exc
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "").strip()
        raise UpstreamFailure(
            f"`{' '.join(cmd[:2])}` failed (exit {proc.returncode}): {stderr[:800]}",
            platform=platform,
            backend=binary,
            fix=fix,
        )
    return proc.stdout
