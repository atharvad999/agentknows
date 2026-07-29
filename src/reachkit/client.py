# -*- coding: utf-8 -*-
"""Reach — the single facade over all platforms.

    from reachkit import Reach

    reach = Reach()
    reach.read("https://youtube.com/watch?v=...")   # transcript + metadata
    reach.read("https://github.com/o/r/issues/1")   # issue + comments
    reach.read("RELIANCE", platform="stocks")       # NSE quote via yfinance
    reach.search("llm eval frameworks")             # Exa semantic web search
    reach.search("smallcap IT", platform="discourse")  # ValuePickr forum
    reach.hot("news", region="india")               # fresh headlines
    reach.doctor()                                  # structured health report

Every call returns a ReachResult; errors raise ReachError subclasses whose
`.fix` field carries the runnable prescription. With fallback_to_web=True
(default), a read on a platform whose tool is missing degrades to Jina Reader
instead of failing.
"""

from __future__ import annotations

from typing import Any

from .adapters import Adapter, build_registry
from .doctor import doctor as _doctor
from .errors import ReachError, SetupRequired, UnsupportedOperation
from .models import ReachResult
from .router import known_platforms, resolve_platform


def _load_config() -> Any:
    """agent-reach's config (cookies/tokens), read-only. None if unreadable."""
    try:
        from agent_reach.config import Config

        return Config(read_only=True)
    except Exception:
        return None


class Reach:
    def __init__(self, *, config: Any = None, fallback_to_web: bool = True):
        self.config = config if config is not None else _load_config()
        self.fallback_to_web = fallback_to_web
        self._registry = build_registry(self.config)

    # -- capabilities ------------------------------------------------------

    def platforms(self) -> dict[str, dict[str, bool]]:
        """Platform → supported operations."""
        out: dict[str, dict[str, bool]] = {}
        for name, adapter in self._registry.items():
            out[name] = {
                "read": type(adapter).read is not Adapter.read,
                "search": type(adapter).search is not Adapter.search,
                "hot": hasattr(adapter, "hot"),
            }
        return out

    def doctor(self) -> ReachResult:
        return _doctor(self.config)

    # -- core operations ---------------------------------------------------

    def read(self, url: str, *, platform: str | None = None, **kwargs: Any) -> ReachResult:
        """Read any URL; routes to the owning platform's best backend.

        Pass `platform` to bypass URL routing (e.g. platform="xueqiu" with a
        bare stock symbol like "AAPL").
        """
        if platform is not None and platform not in self._registry:
            raise ReachError(
                f"Unknown platform {platform!r}. Known: {sorted(self._registry)}",
                platform=platform,
            )
        platform = platform or resolve_platform(url)
        adapter = self._registry.get(platform)
        if adapter is None:
            adapter = self._registry["web"]
            platform = "web"
        try:
            return adapter.read(url, **kwargs)
        except (SetupRequired, UnsupportedOperation) as exc:
            if not (self.fallback_to_web and platform != "web" and url.startswith("http")):
                raise
            result = self._registry["web"].read(url)
            result.meta["fallback"] = True
            result.meta["fallback_reason"] = str(exc)
            if exc.fix:
                result.meta["setup_hint"] = exc.fix
            return result

    def search(self, query: str, *, platform: str = "web", limit: int = 10, **kwargs: Any) -> ReachResult:
        adapter = self._registry.get(platform)
        if adapter is None:
            raise ReachError(
                f"Unknown platform {platform!r}. Known: {sorted(self._registry)}",
                platform=platform,
            )
        return adapter.search(query, limit=limit, **kwargs)

    def hot(self, platform: str, **kwargs: Any) -> ReachResult:
        """Trending/hot listings (hackernews, news, discourse)."""
        adapter = self._registry.get(platform)
        if adapter is None or not hasattr(adapter, "hot"):
            supported = [n for n, a in self._registry.items() if hasattr(a, "hot")]
            raise UnsupportedOperation(
                f"{platform!r} has no hot/trending listing. Supported: {supported}",
                platform=platform,
            )
        return adapter.hot(**kwargs)

    def research(
        self,
        query: str,
        *,
        region: str | None = None,
        limit: int = 8,
        report: bool = False,
    ) -> ReachResult:
        """One query → parallel fan-out across sources → merged bundle.

        region: 'india' | 'western' | None (both). report=True additionally
        synthesizes a Claude-written report (needs anthropic SDK + credentials).
        """
        from .research import research as _research

        return _research(self, query, region=region, limit=limit, report=report)

    def transcribe(self, url: str, *, provider: str = "auto") -> ReachResult:
        """Audio → text via agent-reach's Whisper integration (Groq/OpenAI key)."""
        try:
            from agent_reach.transcribe import transcribe as _transcribe

            text = _transcribe(url, provider=provider, config=self.config)
        except ReachError:
            raise
        except Exception as exc:
            raise ReachError(
                f"Transcription failed: {exc}",
                platform="transcribe",
                fix=(
                    "Needs ffmpeg + a Whisper key: agent-reach configure groq-key "
                    "(free) or openai-key. Check `agent-reach doctor`."
                ),
            ) from exc
        return ReachResult(
            ok=True, platform="transcribe", backend=f"whisper-{provider}",
            kind="document", content=text, meta={"url": url},
        )

    @staticmethod
    def known_platforms() -> list[str]:
        return known_platforms()
