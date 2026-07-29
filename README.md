# agentknows

**Typed Python SDK + MCP server for internet access across Western + Indian platforms.**
Built on [Agent-Reach](https://github.com/Panniantong/Agent-Reach)'s capability layer.

Agent-Reach is a *capability layer*: it installs, health-checks, and routes the
best current backend per platform (Jina Reader, yt-dlp, gh, Exa, twitter-cli,
OpenCLI, ...). By design it has **no programmatic API** — it expects an agent
with shell access reading `SKILL.md`. agentknows fills that gap and retargets the
platform set at the **English-speaking + Indian internet**:

| Agent-Reach gives you | agentknows adds |
|---|---|
| Installer + doctor + backend routing | One typed facade: `Reach().read(url)` / `.search(q, platform=...)` |
| Per-platform CLIs, each with its own output format | One `ReachResult` JSON shape for everything |
| Shell-only usage | **MCP server** — Claude Desktop, Cursor, any MCP client, no shell needed |
| Fix prescriptions inside doctor text | Machine-readable errors: every failure carries a runnable `.fix` |
| Chinese-platform focus (xiaohongshu, bilibili...) | **Indian channels**: NSE/BSE stocks, ValuePickr, Indian news pack |
| — | Graceful degradation: missing tool → Jina Reader fallback + setup hint |

## Install

```bash
uv venv && uv pip install -e .
# optional upstream tools: gh (GitHub), mcporter+exa (web search), twitter-cli, OpenCLI
# `agentknows doctor` tells you exactly what's missing and how to fix it.
```

## SDK

```python
from agentknows import Reach

reach = Reach()

# read anything
reach.read("https://www.youtube.com/watch?v=...")     # metadata + transcript
reach.read("https://github.com/owner/repo/issues/1")  # issue + comments via gh
reach.read("https://news.ycombinator.com/item?id=1")  # story + comment tree
reach.read("https://forum.valuepickr.com/t/x/3872")   # forum topic + posts
reach.read("https://any-blog.com/post")               # Markdown via Jina Reader
reach.read("RELIANCE", platform="stocks")             # NSE quote (auto .NS/.BO suffix)

# search
reach.search("llm eval frameworks")                   # Exa semantic web search
reach.search("react hooks", platform="github", kind="code")
reach.search("smallcap IT", platform="discourse")     # ValuePickr
reach.search("TCS", platform="stocks")                # symbol lookup

# trending
reach.hot("hackernews")                               # HN front page
reach.hot("news", region="india")                     # ET/Mint/Hindu/TOI/Moneycontrol
reach.hot("discourse", period="weekly")               # top ValuePickr threads

# cross-platform research: one query → parallel fan-out → merged bundle
reach.research("UPI transaction limits", region="india")
reach.research("vector db pricing", report=True)      # + Claude-written synthesis

reach.doctor()                                        # structured health report
```

Every call returns a `ReachResult`:

```python
ReachResult(ok=True, platform="stocks", backend="yfinance", kind="document",
            content="# Reliance Industries...", meta={"price": 1275.9, "currency": "INR", ...})
```

Failures raise `ReachError` subclasses (`SetupRequired`, `UpstreamFailure`,
`UnsupportedOperation`) whose `.fix` is a runnable prescription.

## CLI

```bash
agentknows read https://news.ycombinator.com/item?id=39000000
agentknows read RELIANCE -p stocks
agentknows search "vector databases" -n 5
agentknows search "Tata Motors" -p discourse
agentknows hot news --region india
agentknows hot hackernews
agentknows research "ONDC adoption" --region india        # merged research bundle
agentknows research "rust web frameworks" --report        # + Claude synthesis (needs key)
agentknows doctor
agentknows read <url> --json        # machine output
```

`research` fans one query out in parallel across web (Exa), Hacker News, news,
YouTube, ValuePickr, and Twitter/Reddit when configured, and merges everything
into one Markdown bundle with per-source coverage notes. `--report` adds a
Claude-written synthesis (install `agentknows[research]`, set `ANTHROPIC_API_KEY`
or `ant auth login`; refusal fallbacks are enabled by default).

## Web console

```bash
uv pip install "agentknows[ui]"
agentknows ui          # opens http://127.0.0.1:8787
```

A local one-page console over the same engine: pick a verb (research / search /
read / hot), type a query, watch the research fan-out complete source-by-source
live (SSE), and read the rendered bundle. `doctor` lives in the nav. Local-first
on purpose — the strongest backends (yt-dlp, gh, cookies, OpenCLI) are on your
machine, so the console runs next to them.

## MCP server

```bash
agentknows-mcp     # stdio
```

Claude Desktop / Cursor config:

```json
{"mcpServers": {"agentknows": {"command": "agentknows-mcp"}}}
```

Tools: `reach_read`, `reach_search`, `reach_hot`, `reach_research`, `reach_doctor`, `reach_platforms`. (`reach_research` returns the raw bundle — the calling model does its own synthesis.)

## Platform support

| Platform | read | search | hot | Needs |
|---|---|---|---|---|
| web (any URL) | Jina Reader | Exa via mcporter | — | nothing / mcporter |
| youtube | metadata + transcript | ytsearch | — | yt-dlp (bundled) |
| github | repo / issue / PR | repos, code, issues, prs | — | gh CLI |
| hackernews | story + comments | Algolia | front page | nothing |
| stocks (NSE/BSE/US) | live quote | symbol lookup | — | nothing (yfinance bundled) |
| news (IN + Western) | — | keyword filter | fresh headlines | nothing |
| discourse (ValuePickr + any forum) | topic + posts | forum search | top threads | nothing |
| rss | feed entries | — | — | nothing |
| twitter | tweet | search | — | twitter-cli + cookies (burner account!) |
| reddit / facebook / instagram | via OpenCLI | via OpenCLI | — | OpenCLI + logged-in browser |

**8 of 11 platforms are zero-config.** Chinese channels (bilibili, xiaohongshu,
v2ex, xueqiu, xiaoyuzhou) are intentionally out of scope; their URLs still read
fine through the Jina Reader catch-all.

News pack sources — India: Economic Times, LiveMint, The Hindu, Times of India,
Moneycontrol. Western: BBC, The Guardian, TechCrunch, The Verge, Ars Technica.
Edit `adapters/news.py:FEEDS` to customize.

Login-gated platforms follow Agent-Reach's boundaries: agentknows never automates
logins or reads browser cookies; credentials are injected into child processes
only and never logged. Use burner accounts — cookie-based API access risks bans.

## Layout

```
src/agentknows/
├── client.py        # Reach facade
├── router.py        # URL → platform (native hosts + agent-reach's can_handle)
├── doctor.py        # structured health report
├── models.py        # ReachResult / Item envelope
├── errors.py        # errors with .fix prescriptions
├── proc.py          # upstream CLI runner
├── mcp_server.py    # FastMCP server
├── cli.py           # human CLI
└── adapters/        # one per platform, normalizing upstream output
    ├── stocks.py        # NSE/BSE/US via yfinance
    ├── hackernews.py    # Algolia public API
    ├── discourse.py     # ValuePickr default; works on any Discourse forum
    ├── news.py          # curated IN + Western RSS pack
    └── ...
```
