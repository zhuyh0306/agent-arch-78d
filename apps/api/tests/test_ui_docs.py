"""The browser surfaces: /docs, /openapi.json and /ui.

Every protected page gets the same treatment as the API: prove it is closed
before proving it is open. A docs page that is accidentally public is an
endpoint inventory leak, and a status board that is accidentally public leaks
which capabilities exist and which are unfinished.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dataagent.api.app import create_app
from dataagent.domain.auth import ApiKey
from dataagent.infra.container import Container, build_container
from dataagent.infra.settings import Settings

DICTIONARY = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "metrics_dictionary.yaml"
KEY = "docs-test-key-abcdef0123"


def make_client() -> TestClient:
    base = build_container(Settings(metrics_dictionary=DICTIONARY))
    container = Container(
        settings=base.settings,
        llm=base.llm,
        tools=base.tools,
        metrics=base.metrics,
        agent=base.agent,
        api_keys=type(base.api_keys)(keys=(ApiKey(KEY, "tenant-a", "alice"),)),
    )
    return TestClient(create_app(container))


def basic(key: str, user: str = "dev") -> dict[str, str]:
    token = base64.b64encode(f"{user}:{key}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# ------------------------------------------------------------------- /docs


def test_docs_requires_credentials() -> None:
    response = make_client().get("/docs")
    assert response.status_code == 401
    assert "Basic" in response.headers.get("www-authenticate", "")


def test_openapi_requires_credentials() -> None:
    assert make_client().get("/openapi.json").status_code == 401


def test_wrong_basic_password_is_rejected() -> None:
    assert make_client().get("/docs", headers=basic("nope")).status_code == 401


def test_malformed_basic_header_is_rejected() -> None:
    client = make_client()
    assert client.get("/docs", headers={"Authorization": "Basic not-base64!!"}).status_code == 401
    assert client.get("/docs", headers={"Authorization": "Bearer abc"}).status_code == 401


def test_docs_opens_with_valid_key() -> None:
    response = make_client().get("/docs", headers=basic(KEY))
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


def test_key_may_be_in_username_field() -> None:
    """The browser prompt is easier to use when either field is accepted."""
    response = make_client().get("/openapi.json", headers=basic("ignored", user=KEY))
    assert response.status_code == 200


def test_openapi_document_lists_endpoints_but_not_itself() -> None:
    document = make_client().get("/openapi.json", headers=basic(KEY)).json()
    assert "/healthz" in document["paths"]
    assert "/metrics/{metric_id}" in document["paths"]
    # The docs routes are deliberately excluded from the schema they serve.
    assert "/docs" not in document["paths"]
    assert "/openapi.json" not in document["paths"]


# --------------------------------------------------------------------- /ui


def test_status_page_requires_key() -> None:
    assert make_client().get("/ui").status_code == 401


def test_metrics_page_requires_key() -> None:
    assert make_client().get("/ui/metrics").status_code == 401


def test_status_page_renders_with_key() -> None:
    response = make_client().get(f"/ui?key={KEY}")
    assert response.status_code == 200
    body = response.text
    assert "工程进度" in body
    assert "Day 15" in body or "模块化单体" in body
    # It must be reading the real plan, not a stub.
    assert "整日完成" in body


def test_metrics_page_lists_all_dictionary_entries() -> None:
    response = make_client().get(f"/ui/metrics?key={KEY}")
    assert response.status_code == 200
    body = response.text
    for metric_id in ("gmv", "net_sales", "aov", "gross_margin", "sell_through_rate"):
        assert f"<code>{metric_id}</code>" in body
    assert "高算错风险" in body
    assert "20" in body  # the metric count tile


def test_metrics_page_escapes_html_from_the_dictionary() -> None:
    """The page renders YAML text; a stray tag must not become markup."""
    body = make_client().get(f"/ui/metrics?key={KEY}").text
    assert "<script>alert" not in body


@pytest.mark.parametrize("path", ["/ui", "/ui/", "/ui/metrics"])
def test_ui_paths_never_500(path: str) -> None:
    response = make_client().get(f"{path}?key={KEY}")
    assert response.status_code == 200, response.text[:300]