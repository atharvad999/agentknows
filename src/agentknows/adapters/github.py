# -*- coding: utf-8 -*-
"""GitHub — repos/issues/PRs via gh CLI, normalized to documents/items."""

from __future__ import annotations

import json
import re
from typing import Any

from ..errors import UpstreamFailure
from ..models import Item, ReachResult
from ..proc import run
from .base import Adapter

_FIX = "Install gh: https://cli.github.com — then `gh auth login`."
_URL_RE = re.compile(
    r"github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s#?]+)"
    r"(?:/(?P<type>issues|pull|discussions)/(?P<number>\d+))?"
)


def _parse(target: str) -> tuple[str, str, str | None, str | None]:
    m = _URL_RE.search(target)
    if m:
        return m["owner"], m["repo"], m["type"], m["number"]
    if re.fullmatch(r"[\w.-]+/[\w.-]+", target):  # "owner/repo" shorthand
        owner, repo = target.split("/")
        return owner, repo, None, None
    raise UpstreamFailure(
        f"Cannot parse GitHub target: {target!r}. Use a github.com URL or owner/repo.",
        platform="github",
    )


class GitHubAdapter(Adapter):
    platform = "github"

    def read(self, target: str, **kwargs: Any) -> ReachResult:
        owner, repo, kind, number = _parse(target)
        slug = f"{owner}/{repo}"
        if kind == "issues" and number:
            out = run(
                ["gh", "issue", "view", number, "-R", slug, "--comments"],
                platform=self.platform, fix=_FIX,
            )
            meta = {"repo": slug, "type": "issue", "number": int(number)}
        elif kind == "pull" and number:
            out = run(
                ["gh", "pr", "view", number, "-R", slug, "--comments"],
                platform=self.platform, fix=_FIX,
            )
            meta = {"repo": slug, "type": "pr", "number": int(number)}
        else:
            view = run(["gh", "repo", "view", slug], platform=self.platform, fix=_FIX)
            meta = {"repo": slug, "type": "repo"}
            out = view
        return ReachResult(
            ok=True, platform=self.platform, backend="gh", kind="document",
            content=out.strip(), meta=meta,
        )

    def search(self, query: str, limit: int = 10, *, kind: str = "repos", **kwargs: Any) -> ReachResult:
        """kind: repos | code | issues | prs"""
        fields = {
            "repos": "fullName,description,stargazersCount,url",
            "code": "repository,path,url",
            "issues": "title,repository,url,state",
            "prs": "title,repository,url,state",
        }
        if kind not in fields:
            raise UpstreamFailure(
                f"Unknown GitHub search kind {kind!r} (use repos/code/issues/prs).",
                platform=self.platform,
            )
        cmd = ["gh", "search", kind, query, "--limit", str(limit), "--json", fields[kind]]
        if kind == "repos":
            cmd += ["--sort", "stars"]
        raw = run(cmd, platform=self.platform, timeout=60, fix=_FIX)
        rows = json.loads(raw or "[]")
        items = []
        for r in rows:
            repo_name = (
                r.get("fullName")
                or (r.get("repository") or {}).get("nameWithOwner", "")
            )
            items.append(
                Item(
                    title=r.get("title") or repo_name,
                    url=r.get("url") or "",
                    snippet=r.get("description") or r.get("path") or "",
                    extra={
                        k: v
                        for k, v in (
                            ("stars", r.get("stargazersCount")),
                            ("state", r.get("state")),
                            ("repo", repo_name or None),
                        )
                        if v is not None
                    },
                )
            )
        return ReachResult(
            ok=True, platform=self.platform, backend="gh", kind="items",
            items=items, meta={"query": query, "search_kind": kind},
        )
