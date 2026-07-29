# -*- coding: utf-8 -*-
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentknows.webapp import create_app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_index_serves_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "agentknows console" in resp.text


def test_static_assets(client):
    assert client.get("/app.css").status_code == 200
    assert client.get("/app.js").status_code == 200


def test_platforms_endpoint(client):
    data = client.get("/api/platforms").json()
    assert data["ok"] and "stocks" in data["platforms"]


def test_search_error_shape(client):
    data = client.get("/api/search", params={"q": "x", "platform": "nope"}).json()
    assert data["ok"] is False
    assert "nope" in data["error"]


def test_hot_unsupported_error(client):
    data = client.get("/api/hot", params={"platform": "web"}).json()
    assert data["ok"] is False
