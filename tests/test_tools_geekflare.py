"""Unit tests with the HTTP layer mocked."""

import json
from types import SimpleNamespace
from typing import Any, Dict

import pytest
from geekflare_api.api.api_tool_api import ApiToolApi
from llama_index.core.tools.tool_spec.base import BaseToolSpec

from llama_index.tools.geekflare import GeekflareAPIError, GeekflareToolSpec


class _FakeApi(list):
    """Recorded requests, plus the response the fake API returns next."""

    def __init__(self) -> None:
        super().__init__()
        self.state: Dict[str, Any] = {
            "status": 200,
            "body": {"apiStatus": "success", "apiCode": 200, "data": {"ok": True}},
        }


@pytest.fixture
def fake_api(monkeypatch: pytest.MonkeyPatch) -> _FakeApi:
    calls = _FakeApi()
    for attr in dir(ApiToolApi):
        if not attr.endswith("_without_preload_content"):
            continue

        def fake(self: Any, *args: Any, _attr: str = attr, **kwargs: Any) -> Any:
            request = next(v for k, v in kwargs.items() if k.endswith("_dto"))
            calls.append({"method": _attr, "body": request.to_dict(), "kwargs": kwargs})
            return SimpleNamespace(
                status=calls.state["status"], data=json.dumps(calls.state["body"]).encode()
            )

        monkeypatch.setattr(ApiToolApi, attr, fake)
    return calls


def test_class() -> None:
    assert BaseToolSpec.__name__ in [b.__name__ for b in GeekflareToolSpec.__mro__]


def test_spec_functions_exist() -> None:
    for name in GeekflareToolSpec.spec_functions:
        assert callable(getattr(GeekflareToolSpec, name))


def test_to_tool_list() -> None:
    tools = GeekflareToolSpec(api_key="k").to_tool_list()
    assert len(tools) == 15
    names = {t.metadata.name for t in tools}
    assert {"search", "scrape", "screenshot", "tls_scan", "lighthouse"} <= names
    search = next(t for t in tools if t.metadata.name == "search")
    props = search.metadata.fn_schema.model_json_schema()["properties"]
    assert {"query", "serp", "city", "include_domains"} <= set(props)


def test_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEEKFLARE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key"):
        GeekflareToolSpec()


def test_api_key_from_env(monkeypatch: pytest.MonkeyPatch, fake_api: _FakeApi) -> None:
    monkeypatch.setenv("GEEKFLARE_API_KEY", "env-key")
    GeekflareToolSpec().dnssec("https://example.com")
    assert fake_api[-1]["method"] == "dns_sec_without_preload_content"


def test_search_body(fake_api: _FakeApi) -> None:
    result = GeekflareToolSpec(api_key="k").search(
        "best crm", serp=True, city="London,England,United Kingdom", include_domains=["g2.com"]
    )
    assert result["data"] == {"ok": True}
    body = fake_api[-1]["body"]
    assert body["query"] == "best crm"
    assert body["serp"] is True
    assert body["city"] == "London,England,United Kingdom"
    assert body["includeDomains"] == ["g2.com"]
    assert "excludeDomains" not in body


def test_scrape_template_sets_extraction_mode(fake_api: _FakeApi) -> None:
    GeekflareToolSpec(api_key="k").scrape(
        "https://example.com", formats=["markdown-llm"], render_js=True, template="product"
    )
    body = fake_api[-1]["body"]
    assert body["format"] == ["markdown-llm"]
    assert body["renderJS"] is True
    assert body["extractionMode"] == "template"


def test_url_to_pdf_format(fake_api: _FakeApi) -> None:
    GeekflareToolSpec(api_key="k").url_to_pdf("https://example.com", paper_format="letter")
    assert fake_api[-1]["body"]["format"] == "letter"


def test_dns_records_types_and_timeout(fake_api: _FakeApi) -> None:
    GeekflareToolSpec(api_key="k", timeout=12).dns_records(
        "https://example.com", types=["A", "MX"]
    )
    assert fake_api[-1]["body"] == {"url": "https://example.com", "types": ["A", "MX"]}
    assert fake_api[-1]["kwargs"]["_request_timeout"] == 12


def test_every_tool_calls_the_api(fake_api: _FakeApi) -> None:
    for tool in GeekflareToolSpec(api_key="k").to_tool_list():
        args = {"query": "x"} if tool.metadata.name == "search" else {"url": "https://example.com"}
        tool(**args)
    assert len(fake_api) == 15


def test_http_error(fake_api: _FakeApi) -> None:
    fake_api.state["status"] = 401
    fake_api.state["body"] = {"apiCode": 401, "message": "Invalid x-api-key"}
    with pytest.raises(GeekflareAPIError, match="Invalid x-api-key"):
        GeekflareToolSpec(api_key="bad").search("x")


def test_invalid_arguments() -> None:
    with pytest.raises(ValueError, match="Invalid arguments"):
        GeekflareToolSpec(api_key="k").search("x", limit=500)
