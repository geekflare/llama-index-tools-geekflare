# LlamaIndex Tools Integration: Geekflare

LlamaIndex tools for the [Geekflare API](https://geekflare.com): live web search (including full Google SERP results), scraping public pages to Markdown or structured JSON, page metadata, brand data, screenshots, URL-to-PDF, and website diagnostics (uptime, DNS, DNSSEC, TLS, redirects, broken links, load time, mixed content, Lighthouse).

Built on the official Python SDK, [`geekflare-api`](https://pypi.org/project/geekflare-api/).

## Installation

```bash
pip install llama-index-tools-geekflare
```

## Setup

Get an API key at [dash.geekflare.com](https://dash.geekflare.com) (free tier available) and set it as an environment variable:

```bash
export GEEKFLARE_API_KEY="your-api-key"
```

You can also pass it directly: `GeekflareToolSpec(api_key="...")`.

## Usage

### With an agent

```python
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.anthropic import Anthropic
from llama_index.tools.geekflare import GeekflareToolSpec

tools = GeekflareToolSpec().to_tool_list()

agent = FunctionAgent(
    tools=tools,
    llm=Anthropic(model="claude-sonnet-5-5"),
)

response = await agent.run("Is the TLS certificate on example.com close to expiring?")
print(response)
```

Give the agent only the tools it needs, for example:

```python
spec = GeekflareToolSpec()
tools = [t for t in spec.to_tool_list() if t.metadata.name in {"search", "scrape"}]
```

### Call a tool directly

```python
from llama_index.tools.geekflare import GeekflareToolSpec

geekflare = GeekflareToolSpec()

geekflare.search("latest stable python release", limit=5)

# Full Google results page for a city
geekflare.search(
    "best project management software",
    serp=True,
    city="London,England,United Kingdom",
)

geekflare.scrape("https://example.com", formats=["markdown"])
```

## Tools

| Tool | What it does |
| --- | --- |
| `search` | Web, news, or image search; `serp=True` returns the full Google results page (AI Overview, People Also Ask) by country or city |
| `scrape` | Page content as Markdown, text, HTML, or JSON; `template="product"` or `"contact"` for structured data |
| `meta_scrape` | Title, description, canonical, Open Graph, Twitter Card tags |
| `brand` | Logos, brand colors, fonts, social profiles |
| `screenshot` | Viewport, full-page, or element screenshot (hosted image URL) |
| `url_to_pdf` | Page as PDF (hosted file URL) |
| `site_status` | Is the site up, and its HTTP status |
| `dns_records` | A, AAAA, CNAME, MX, NS, SOA, TXT, CAA, SRV records |
| `dnssec` | DNSSEC configured and validating |
| `tls_scan` | Certificate details and expiry, supported TLS versions |
| `redirect_check` | Redirect chain with status codes |
| `broken_links` | Broken links on a page |
| `load_time` | Page load timing |
| `mixed_content` | HTTP resources on HTTPS pages |
| `lighthouse` | Lighthouse performance, SEO, accessibility, best-practices scores |

Each tool returns the API's JSON response as a dict. API errors raise `GeekflareAPIError`, which LlamaIndex agents receive as a tool error.

## Notes

- Every call spends Geekflare credits on your account; see [pricing](https://geekflare.com/pricing/).
- Use the tools for publicly accessible pages only.
- The tools send the URLs, queries, and options you pass to `api.geekflare.com`. See the [Geekflare privacy policy](https://geekflare.com/privacy/).

## Development

```bash
uv venv --python 3.12 && uv pip install -e . --group test
pytest --disable-socket --allow-unix-socket tests/test_tools_geekflare.py
GEEKFLARE_API_KEY=... pytest tests/test_integration.py
```

## Links

- API docs: <https://docs.geekflare.com>
- Python SDK: <https://github.com/geekflare/geekflare-api-python>
- LangChain tools: <https://github.com/geekflare/langchain-geekflare>
- MCP server: <https://docs.geekflare.com/mcp/overview>
