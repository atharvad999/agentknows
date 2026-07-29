# -*- coding: utf-8 -*-
"""bharatnet — typed SDK + MCP server over Agent-Reach's internet capability layer."""

from .client import Reach
from .errors import ReachError, SetupRequired, UnsupportedOperation, UpstreamFailure
from .models import Item, ReachResult

__version__ = "0.1.0"
__all__ = [
    "Reach",
    "ReachResult",
    "Item",
    "ReachError",
    "SetupRequired",
    "UnsupportedOperation",
    "UpstreamFailure",
]
