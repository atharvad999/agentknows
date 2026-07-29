# -*- coding: utf-8 -*-
"""Vercel entry for the hosted agentknows console demo.

Hosted mode is the honest degraded tier: pure-HTTP channels (hackernews,
discourse, news, stocks, rss, Jina web reads) work fully; channels that need
local CLIs or logged-in sessions surface their usual .fix prescriptions. The
full-power console runs locally via `agentknows ui`.
"""

import os

os.environ.setdefault("AGENTKNOWS_HOSTED", "1")

from agentknows.webapp import create_app  # noqa: E402

app = create_app()
