# -*- coding: utf-8 -*-
"""reachkit CLI — human-friendly front door to the SDK.

    reachkit read <url>
    reachkit search "query" [-p youtube] [-n 10]
    reachkit hot hackernews
    reachkit hot news --region india
    reachkit doctor
    reachkit platforms
    reachkit serve            # start the MCP server (stdio)

Add --json anywhere for machine output.
"""

from __future__ import annotations

import argparse
import sys

from .client import Reach
from .errors import ReachError
from .models import ReachResult


def _print(result: ReachResult, as_json: bool) -> None:
    if as_json:
        print(result.to_json())
        return
    if result.kind == "document":
        print(result.content or "")
        if result.meta:
            interesting = {k: v for k, v in result.meta.items() if k != "url"}
            if interesting:
                print(f"\n--- meta: {interesting}", file=sys.stderr)
    elif result.kind == "items":
        for i, item in enumerate(result.items, 1):
            line = f"{i:2}. {item.title}"
            if item.url:
                line += f"\n    {item.url}"
            if item.snippet:
                line += f"\n    {item.snippet[:200]}"
            print(line)
        if not result.items:
            print("(no results)")
    else:  # status
        channels = result.meta.get("channels")
        if channels:
            for ch in channels:
                mark = {"ok": "+", "warn": "~", "off": "-", "error": "!"}[ch["status"]]
                backend = f" via {ch['active_backend']}" if ch["active_backend"] else ""
                print(f" {mark} {ch['platform']:<12} {ch['status']:<5}{backend}")
            print(f"\n{result.meta.get('summary', '')}")
        else:
            print(result.to_json())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reachkit", description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="JSON output")
    sub = parser.add_subparsers(dest="command", required=True)

    p_read = sub.add_parser("read", help="Read any URL", parents=[common])
    p_read.add_argument("url")
    p_read.add_argument("-p", "--platform", default=None,
                        help="Bypass URL routing (e.g. -p stocks with a ticker symbol)")
    p_read.add_argument("--no-fallback", action="store_true",
                        help="Fail instead of degrading to Jina Reader")

    p_search = sub.add_parser("search", help="Search a platform", parents=[common])
    p_search.add_argument("query")
    p_search.add_argument("-p", "--platform", default="web")
    p_search.add_argument("-n", "--limit", type=int, default=10)
    p_search.add_argument("-k", "--kind", default=None,
                          help="GitHub only: repos/code/issues/prs")

    p_research = sub.add_parser(
        "research",
        help="One query → parallel fan-out across all sources → merged bundle or report",
        parents=[common],
    )
    p_research.add_argument("query")
    p_research.add_argument("--region", default=None, help="india | western (default: both)")
    p_research.add_argument("-n", "--limit", type=int, default=8, help="results per source")
    p_research.add_argument("--report", action="store_true",
                            help="Synthesize a Claude-written report (needs anthropic SDK + key)")

    p_hot = sub.add_parser("hot", help="Trending listings (hackernews, news, discourse)", parents=[common])
    p_hot.add_argument("platform")
    p_hot.add_argument("-n", "--limit", type=int, default=20)
    p_hot.add_argument("--region", default=None, help="news only: india | western")

    sub.add_parser("doctor", help="Channel health report", parents=[common])
    sub.add_parser("platforms", help="List platforms and capabilities", parents=[common])
    sub.add_parser("serve", help="Run the MCP server (stdio)", parents=[common])

    args = parser.parse_args(argv)

    if args.command == "serve":
        from .mcp_server import main as serve_main

        serve_main()
        return 0

    try:
        if args.command == "read":
            reach = Reach(fallback_to_web=not args.no_fallback)
            _print(reach.read(args.url, platform=args.platform), args.json)
        elif args.command == "search":
            kwargs = {"kind": args.kind} if args.kind else {}
            _print(
                Reach().search(args.query, platform=args.platform, limit=args.limit, **kwargs),
                args.json,
            )
        elif args.command == "research":
            _print(
                Reach().research(args.query, region=args.region,
                                 limit=args.limit, report=args.report),
                args.json,
            )
        elif args.command == "hot":
            hot_kwargs = {"region": args.region} if args.region else {}
            _print(Reach().hot(args.platform, limit=args.limit, **hot_kwargs), args.json)
        elif args.command == "doctor":
            _print(Reach().doctor(), args.json)
        elif args.command == "platforms":
            import json as _json

            print(_json.dumps(Reach().platforms(), indent=2))
    except ReachError as exc:
        print(f"error [{exc.platform or '?'}]: {exc}", file=sys.stderr)
        if exc.fix:
            print(f"\nfix:\n{exc.fix}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
