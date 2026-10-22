"""Live API tests. Need a real ``GEEKFLARE_API_KEY``."""

import os

import pytest

from llama_index.tools.geekflare import GeekflareToolSpec

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEEKFLARE_API_KEY"), reason="GEEKFLARE_API_KEY not set"
)


def test_search_live() -> None:
    result = GeekflareToolSpec().search("geekflare api", limit=3)
    assert result.get("apiStatus") == "success"


def test_dns_records_live() -> None:
    result = GeekflareToolSpec().dns_records("https://example.com", types=["A"])
    assert result.get("apiStatus") == "success"


def test_tool_list_live() -> None:
    tool = next(
        t for t in GeekflareToolSpec().to_tool_list() if t.metadata.name == "meta_scrape"
    )
    output = tool(url="https://example.com")
    assert not output.is_error
