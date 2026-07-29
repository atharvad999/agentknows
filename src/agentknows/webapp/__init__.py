# -*- coding: utf-8 -*-
"""Local web console for agentknows — FastAPI + static single page.

Run: `agentknows ui` (opens http://127.0.0.1:8787). Local-first by design:
the strongest backends (yt-dlp, gh CLI, cookies, OpenCLI) live on this
machine, so the console runs next to them rather than on a server.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..client import Reach
from ..errors import ReachError
from ..models import ReachResult
from ..research import _SOURCE_ORDER, _region_sources, bundle_to_markdown, gather_iter

_STATIC = Path(__file__).parent / "static"


def _err_payload(exc: Exception) -> dict:
    if isinstance(exc, ReachError):
        return ReachResult.failure(
            exc.platform or "unknown", str(exc), backend=exc.backend or "", fix=exc.fix
        ).to_dict()
    return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def create_app():
    try:
        from fastapi import FastAPI
        from fastapi.responses import FileResponse, StreamingResponse
    except ImportError as exc:  # pragma: no cover
        raise ReachError(
            "The web console needs fastapi + uvicorn.",
            fix='uv pip install "agentknows[ui]"',
        ) from exc

    app = FastAPI(title="agentknows console")
    reach = Reach()

    @app.get("/")
    def index():
        return FileResponse(_STATIC / "index.html")

    @app.get("/app.css")
    def css():
        return FileResponse(_STATIC / "app.css")

    @app.get("/app.js")
    def js():
        return FileResponse(_STATIC / "app.js")

    @app.get("/api/platforms")
    def platforms():
        return {"ok": True, "platforms": reach.platforms()}

    @app.get("/api/doctor")
    def doctor():
        return reach.doctor().to_dict()

    @app.get("/api/read")
    def read(url: str, platform: str | None = None):
        try:
            return reach.read(url, platform=platform or None).to_dict()
        except Exception as exc:
            return _err_payload(exc)

    @app.get("/api/search")
    def search(q: str, platform: str = "web", limit: int = 10, kind: str | None = None):
        kwargs = {"kind": kind} if kind else {}
        try:
            return reach.search(q, platform=platform, limit=limit, **kwargs).to_dict()
        except Exception as exc:
            return _err_payload(exc)

    @app.get("/api/hot")
    def hot(platform: str, region: str | None = None, limit: int = 20):
        kwargs = {"region": region} if region else {}
        try:
            return reach.hot(platform, limit=limit, **kwargs).to_dict()
        except Exception as exc:
            return _err_payload(exc)

    @app.get("/api/research/stream")
    def research_stream(q: str, region: str | None = None, limit: int = 8):
        """SSE: `source` events as each channel completes, then one `bundle`."""

        def events():
            planned = _region_sources(region or None)
            yield f"event: plan\ndata: {json.dumps({'sources': planned})}\n\n"
            bundle = {}
            for name, entry in gather_iter(reach, q, region=region or None, limit=limit):
                bundle[name] = entry
                payload = {"source": name, "ok": entry["ok"]}
                if entry["ok"]:
                    result: ReachResult = entry["result"]
                    payload["count"] = len(result.items)
                    payload["backend"] = result.backend
                else:
                    payload["error"] = entry.get("error")
                    payload["fix"] = entry.get("fix")
                yield f"event: source\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            ordered = {k: bundle[k] for k in _SOURCE_ORDER if k in bundle}
            md = bundle_to_markdown(q, ordered, region=region or None)
            yield f"event: bundle\ndata: {json.dumps({'markdown': md}, ensure_ascii=False)}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    return app


def main(port: int = 8787, open_browser: bool = True) -> None:
    import threading
    import webbrowser

    import uvicorn

    app = create_app()
    url = f"http://127.0.0.1:{port}"
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"agentknows console → {url}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
