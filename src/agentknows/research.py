# -*- coding: utf-8 -*-
"""Cross-platform research: one query → parallel fan-out → bundle → optional LLM report.

Two output modes:
  - bundle (default): merged, structured Markdown of everything found, ready for
    any LLM (or human) to synthesize. This is what the MCP tool returns — the
    calling model does its own synthesis.
  - report (--report / synthesize=True): a Claude-written synthesis of the
    bundle. Needs the `anthropic` package and credentials (ANTHROPIC_API_KEY
    or an `ant auth login` profile).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from .errors import ReachError, SetupRequired
from .models import ReachResult

SYNTHESIS_MODEL = "claude-opus-5"

#: source name → (needs_setup_note, runner factory). Runners raise ReachError freely;
#: gather() converts failures into per-source status instead of dying.
_SOURCE_ORDER = ["web", "hackernews", "news", "youtube", "discourse", "twitter", "reddit"]


def _region_sources(region: str | None) -> list[str]:
    if region == "india":
        return ["web", "news", "discourse", "youtube", "twitter", "reddit"]
    if region == "western":
        return ["web", "hackernews", "news", "youtube", "twitter", "reddit"]
    return _SOURCE_ORDER


def _expand_query(query: str, source: str, region: str | None) -> str:
    # Light region steering — synthesis handles languages; search needs a hint.
    if region == "india" and source == "web":
        return f"{query} India"
    return query


def gather_iter(
    reach: Any,
    query: str,
    *,
    region: str | None = None,
    limit: int = 8,
):
    """Fan out the query across sources in parallel, yielding (source, entry)
    as each completes. Never raises for a single source — each entry carries
    ok/items/error/fix so callers see exactly what was and wasn't covered."""
    registry = reach._registry
    news_kwargs = {"region": region} if region in ("india", "western") else {}

    runners: dict[str, Callable[[], ReachResult]] = {}
    for source in _region_sources(region):
        q = _expand_query(query, source, region)
        if source == "web":
            runners["web"] = lambda q=q: registry["web"].search(q, limit=limit)
        elif source == "news":
            runners["news"] = lambda q=q: registry["news"].search(q, limit=limit, **news_kwargs)
        elif source in registry:
            runners[source] = lambda q=q, s=source: registry[s].search(q, limit=limit)

    with ThreadPoolExecutor(max_workers=len(runners)) as pool:
        futures = {pool.submit(fn): name for name, fn in runners.items()}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                yield name, {"ok": True, "result": fut.result()}
            except ReachError as exc:
                yield name, {"ok": False, "error": str(exc), "fix": exc.fix}
            except Exception as exc:
                yield name, {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def gather(
    reach: Any,
    query: str,
    *,
    region: str | None = None,
    limit: int = 8,
) -> dict[str, dict[str, Any]]:
    bundle = dict(gather_iter(reach, query, region=region, limit=limit))
    # Keep deterministic source order for the reader.
    return {k: bundle[k] for k in _SOURCE_ORDER if k in bundle}


def bundle_to_markdown(query: str, bundle: dict[str, dict[str, Any]], *, region: str | None = None) -> str:
    lines = [f"# Research bundle: {query}", ""]
    if region:
        lines.append(f"Region focus: {region}\n")
    covered = [s for s, v in bundle.items() if v["ok"]]
    missing = [s for s, v in bundle.items() if not v["ok"]]
    lines.append(f"Sources covered: {', '.join(covered) or 'none'}")
    if missing:
        lines.append(f"Sources unavailable: {', '.join(missing)} (details at bottom)")
    lines.append("")

    for source, entry in bundle.items():
        if not entry["ok"]:
            continue
        result: ReachResult = entry["result"]
        lines.append(f"## {source} (via {result.backend})")
        if result.kind == "items":
            if not result.items:
                lines.append("(no results)")
            for item in result.items:
                lines.append(f"- **{item.title}**")
                if item.url:
                    lines.append(f"  {item.url}")
                if item.snippet:
                    lines.append(f"  {item.snippet}")
                extras = {k: v for k, v in item.extra.items() if v not in (None, "")}
                if extras:
                    lines.append(f"  ({', '.join(f'{k}: {v}' for k, v in extras.items())})")
        elif result.content:
            lines.append(result.content[:4000])
        lines.append("")

    unavailable = [(s, e) for s, e in bundle.items() if not e["ok"]]
    if unavailable:
        lines.append("## Unavailable sources")
        for source, entry in unavailable:
            lines.append(f"- **{source}**: {entry['error']}")
            if entry.get("fix"):
                lines.append(f"  fix: {entry['fix']}")
    return "\n".join(lines)


_REPORT_PROMPT = """You are a research analyst. Below is a raw multi-platform research bundle \
for the query: {query!r}.{region_note}

Write a synthesis report in Markdown:
1. Lead with a 3-5 sentence executive summary answering the query.
2. Key findings, grouped by theme (not by platform). Cite the source URL inline for each claim.
3. Where perspectives differ across platforms or regions, say so explicitly.
4. End with a short "coverage notes" section: which sources were unavailable and how that limits the picture.

Be concrete and selective — drop filler. If the bundle is thin, say so honestly rather than padding.

{bundle}"""


def synthesize(query: str, bundle_md: str, *, region: str | None = None) -> str:
    """Claude-written report over the bundle. Streaming; refusal fallbacks enabled."""
    try:
        import anthropic
    except ImportError as exc:
        raise SetupRequired(
            "Report synthesis needs the anthropic SDK.",
            platform="research",
            fix='uv pip install "agentknows[research]"   # or: pip install anthropic',
        ) from exc

    region_note = f" The user cares about the {region} internet's perspective." if region else ""
    try:
        client = anthropic.Anthropic()  # env key or `ant auth login` profile
    except TypeError as exc:  # SDK raises TypeError when no credential source resolves
        raise SetupRequired(
            "No Anthropic credentials found for synthesis.",
            platform="research",
            fix="export ANTHROPIC_API_KEY=...   # or: ant auth login",
        ) from exc
    try:
        with client.beta.messages.stream(
            model=SYNTHESIS_MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{
                "role": "user",
                "content": _REPORT_PROMPT.format(
                    query=query, region_note=region_note, bundle=bundle_md
                ),
            }],
        ) as stream:
            response = stream.get_final_message()
    except (anthropic.AuthenticationError, TypeError) as exc:
        # TypeError: the SDK raises it at request time when no credential resolves.
        raise SetupRequired(
            "No Anthropic credentials found for synthesis.",
            platform="research",
            fix="export ANTHROPIC_API_KEY=...   # or: ant auth login",
        ) from exc

    if response.stop_reason == "refusal":
        raise ReachError(
            "Synthesis was declined by safety classifiers (whole fallback chain refused).",
            platform="research",
        )
    return "".join(b.text for b in response.content if b.type == "text")


def research(
    reach: Any,
    query: str,
    *,
    region: str | None = None,
    limit: int = 8,
    report: bool = False,
) -> ReachResult:
    bundle = gather(reach, query, region=region, limit=limit)
    bundle_md = bundle_to_markdown(query, bundle, region=region)
    sources_meta = {
        s: ("ok" if e["ok"] else f"unavailable: {e['error'][:120]}")
        for s, e in bundle.items()
    }
    content = bundle_md
    backend = "fan-out"
    if report:
        content = synthesize(query, bundle_md, region=region)
        backend = f"fan-out+{SYNTHESIS_MODEL}"
    return ReachResult(
        ok=True,
        platform="research",
        backend=backend,
        kind="document",
        content=content,
        meta={"query": query, "region": region or "all", "sources": sources_meta},
    )
