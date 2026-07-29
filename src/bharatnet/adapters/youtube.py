# -*- coding: utf-8 -*-
"""YouTube — metadata + transcript + search via yt-dlp (never used for Bilibili)."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

from ..errors import UpstreamFailure
from ..models import Item, ReachResult
from ..proc import run
from .base import Adapter

_FIX = 'python -m pip install -U "yt-dlp[default]"'
_SUB_LANGS = "en.*,zh.*,-live_chat"


def parse_vtt(text: str) -> str:
    """WebVTT → plain transcript: drop headers/timestamps/tags, dedupe lines."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if (
            not line
            or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE"))
            or "-->" in line
            or line.isdigit()
        ):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return "\n".join(lines)


class YouTubeAdapter(Adapter):
    platform = "youtube"

    def read(self, target: str, *, transcript: bool = True, **kwargs: Any) -> ReachResult:
        raw = run(
            ["yt-dlp", "-J", "--skip-download", "--no-warnings", target],
            platform=self.platform,
            timeout=120,
            fix=_FIX,
        )
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise UpstreamFailure(
                "yt-dlp returned non-JSON metadata.", platform=self.platform, backend="yt-dlp"
            ) from exc

        meta = {
            "id": info.get("id"),
            "title": info.get("title"),
            "channel": info.get("channel") or info.get("uploader"),
            "duration_s": info.get("duration"),
            "view_count": info.get("view_count"),
            "upload_date": info.get("upload_date"),
            "url": info.get("webpage_url") or target,
        }
        parts = [f"# {meta['title']}\n", info.get("description") or ""]

        transcript_text = ""
        if transcript:
            transcript_text = self._fetch_transcript(target)
            if transcript_text:
                parts.append("\n## Transcript\n\n" + transcript_text)
        meta["has_transcript"] = bool(transcript_text)

        return ReachResult(
            ok=True,
            platform=self.platform,
            backend="yt-dlp",
            kind="document",
            content="\n".join(p for p in parts if p),
            meta=meta,
        )

    def _fetch_transcript(self, url: str) -> str:
        with tempfile.TemporaryDirectory(prefix="bharatnet-yt-") as tmp:
            try:
                run(
                    [
                        "yt-dlp", "--skip-download", "--no-warnings",
                        "--write-subs", "--write-auto-subs",
                        "--sub-langs", _SUB_LANGS, "--sub-format", "vtt",
                        "-o", f"{tmp}/%(id)s", url,
                    ],
                    platform=self.platform,
                    timeout=180,
                    fix=_FIX,
                )
            except UpstreamFailure:
                return ""  # No subtitles is not an error; metadata alone is useful.
            vtts = sorted(Path(tmp).glob("*.vtt"))
            if not vtts:
                return ""
            # Prefer manually-authored subs (shorter filename sorts first is not
            # a signal; pick .en.vtt over .en-orig auto if both exist → first works).
            return parse_vtt(vtts[0].read_text(encoding="utf-8", errors="replace"))

    def search(self, query: str, limit: int = 10, **kwargs: Any) -> ReachResult:
        raw = run(
            ["yt-dlp", f"ytsearch{limit}:{query}", "--flat-playlist", "-J", "--no-warnings"],
            platform=self.platform,
            timeout=90,
            fix=_FIX,
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise UpstreamFailure(
                "yt-dlp search returned non-JSON.", platform=self.platform, backend="yt-dlp"
            ) from exc
        items = [
            Item(
                title=e.get("title") or "",
                url=e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
                snippet="",
                extra={
                    "channel": e.get("channel") or e.get("uploader"),
                    "duration_s": e.get("duration"),
                    "view_count": e.get("view_count"),
                },
            )
            for e in (data.get("entries") or [])
        ]
        return ReachResult(
            ok=True, platform=self.platform, backend="yt-dlp", kind="items",
            items=items, meta={"query": query},
        )
