"""Geekflare tool spec."""

import json
import os
from typing import Any, Dict, List, Literal, Optional, Tuple

from llama_index.core.tools.tool_spec.base import BaseToolSpec

DEFAULT_BASE_URL = "https://api.geekflare.com"
DEFAULT_TIMEOUT = 180.0

ScrapeFormat = Literal[
    "markdown", "markdown-llm", "html", "html-llm", "text", "text-llm", "json"
]
DnsType = Literal["A", "AAAA", "CNAME", "MX", "NS", "SOA", "TXT", "CAA", "SRV"]
Device = Literal["desktop", "mobile"]

# endpoint -> (SDK model class name, request kwarg name)
_ENDPOINTS: Dict[str, Tuple[str, str]] = {
    "search": ("SearchRequestDto", "search_request_dto"),
    "web_scrape": ("WebScrapeDto", "web_scrape_dto"),
    "meta_scrape": ("MetaScrapeDto", "meta_scrape_dto"),
    "brand": ("BrandDto", "brand_dto"),
    "screenshot": ("ScreenshotDto", "screenshot_dto"),
    "url2_pdf": ("Url2PdfDto", "url2_pdf_dto"),
    "site_status": ("SiteStatusDto", "site_status_dto"),
    "dns_record": ("DnsRecordDto", "dns_record_dto"),
    "dns_sec": ("DnsSecDto", "dns_sec_dto"),
    "tls_scan": ("TlsScanDto", "tls_scan_dto"),
    "redirect_check": ("RedirectCheckDto", "redirect_check_dto"),
    "broken_link": ("BrokenLinkDto", "broken_link_dto"),
    "load_time": ("LoadTimeDto", "load_time_dto"),
    "mixed_content": ("MixedContentDto", "mixed_content_dto"),
    "lighthouse": ("LighthouseDto", "lighthouse_dto"),
}


class GeekflareAPIError(RuntimeError):
    """Raised when the Geekflare API returns an error or can't be reached."""


class GeekflareToolSpec(BaseToolSpec):
    """
    Geekflare tool spec: web search (incl. Google SERP), scraping, metadata,
    brand data, screenshots, URL-to-PDF, and website diagnostics.

    Every tool returns the API's JSON response as a dict.
    """

    spec_functions = [
        "search",
        "scrape",
        "meta_scrape",
        "brand",
        "screenshot",
        "url_to_pdf",
        "site_status",
        "dns_records",
        "dnssec",
        "tls_scan",
        "redirect_check",
        "broken_links",
        "load_time",
        "mixed_content",
        "lighthouse",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Initialize with parameters.

        Args:
            api_key: Geekflare API key. Defaults to the GEEKFLARE_API_KEY
                environment variable. Get one at https://dash.geekflare.com.
            base_url: API base URL.
            timeout: Request timeout in seconds.

        """
        api_key = api_key or os.environ.get("GEEKFLARE_API_KEY")
        if not api_key:
            raise ValueError(
                "A Geekflare API key is required: pass api_key or set GEEKFLARE_API_KEY."
            )
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout

    def _call(self, endpoint: str, body: Dict[str, Any]) -> Dict[str, Any]:
        import geekflare_api
        from geekflare_api import models
        from geekflare_api.api.api_tool_api import ApiToolApi

        model_name, kwarg = _ENDPOINTS[endpoint]
        body = {k: v for k, v in body.items() if v is not None}
        try:
            request = getattr(models, model_name).from_dict(body)
        except Exception as e:
            raise ValueError(f"Invalid arguments for Geekflare {endpoint}: {e}") from e

        configuration = geekflare_api.Configuration(host=self._base_url)
        configuration.api_key["x-api-key"] = self._api_key
        client = geekflare_api.ApiClient(configuration)
        try:
            method = getattr(ApiToolApi(client), f"{endpoint}_without_preload_content")
            response = method(**{kwarg: request}, _request_timeout=self._timeout)
            status, raw = response.status, response.data
        except Exception as e:
            raise GeekflareAPIError(f"Geekflare {endpoint} request failed: {e}") from e
        finally:
            client.rest_client.pool_manager.clear()

        try:
            data = json.loads(raw)
        except ValueError:
            data = {"message": raw.decode("utf-8", errors="replace")}

        if status >= 400 or (
            isinstance(data, dict) and data.get("apiStatus") == "failure"
        ):
            message = data.get("message") if isinstance(data, dict) else None
            raise GeekflareAPIError(
                f"Geekflare {endpoint} returned HTTP {status}: {message or data}"
            )
        return data

    # ── Search and content ────────────────────────────────────────────────

    def search(
        self,
        query: str,
        limit: int = 10,
        source: Literal["web", "news", "images"] = "web",
        time: Optional[str] = None,
        location: Optional[str] = None,
        city: Optional[str] = None,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        serp: bool = False,
        scrape: bool = False,
        grounded_answer: bool = False,
    ) -> Dict[str, Any]:
        """
        Search the live web, news, or images and return titles, URLs, and snippets.
        Set serp=True to get the full Google results page (rankings, AI Overview,
        People Also Ask) for a country or city. Cite the returned URLs.

        Args:
            query: Search query.
            limit: Number of results, 1-100.
            source: web, news, or images.
            time: Recency filter: any, h, d, w, m, y, or with a count such as d7.
            location: Country code (ISO alpha-2) for results, e.g. us.
            city: City for localized results, e.g. 'London,England,United Kingdom'.
            include_domains: Only return results from these domains.
            exclude_domains: Exclude results from these domains.
            serp: Return the full Google results page.
            scrape: Also fetch page content of the top results (ignored with serp).
            grounded_answer: Add an AI answer grounded in the results (ignored with serp).

        """
        return self._call(
            "search",
            {
                "query": query,
                "limit": limit,
                "source": source,
                "time": time,
                "location": location,
                "city": city,
                "includeDomains": include_domains,
                "excludeDomains": exclude_domains,
                "serp": serp,
                "scrape": scrape,
                "groundedAnswer": grounded_answer,
            },
        )

    def scrape(
        self,
        url: str,
        formats: Optional[List[ScrapeFormat]] = None,
        render_js: Optional[bool] = None,
        wait_time: Optional[float] = None,
        device: Device = "desktop",
        template: Optional[Literal["product", "contact"]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a public web page and return its content as clean Markdown (default),
        text, HTML, or JSON. Only for publicly accessible pages.

        Args:
            url: Full URL of the page.
            formats: Output format(s), up to 3. Defaults to markdown.
                The *-llm variants strip boilerplate.
            render_js: Force JavaScript rendering on or off. Omit to decide automatically.
            wait_time: Seconds to wait after load before capturing.
            device: Device to emulate.
            template: Structured JSON template: product (title, price, availability,
                images, ratings) or contact (emails, phones, social profiles).

        """
        return self._call(
            "web_scrape",
            {
                "url": url,
                "format": formats,
                "renderJS": render_js,
                "waitTime": wait_time,
                "device": device,
                "template": template,
                "extractionMode": "template" if template else None,
            },
        )

    def meta_scrape(self, url: str) -> Dict[str, Any]:
        """
        Get a page's metadata only: title, description, canonical URL, Open Graph
        and Twitter Card tags. Cheaper than a full scrape.

        Args:
            url: Full URL of the page.

        """
        return self._call("meta_scrape", {"url": url})

    def brand(
        self, url: str, mode: Literal["standard", "enriched"] = "standard"
    ) -> Dict[str, Any]:
        """
        Get a company's brand identity from its website: name, logos, brand colors,
        fonts, and social profiles. Fields the site doesn't publish are omitted.

        Args:
            url: Website URL or domain, e.g. https://stripe.com.
            mode: enriched adds company intelligence.

        """
        return self._call("brand", {"url": url, "mode": mode})

    def screenshot(
        self,
        url: str,
        full_page: bool = False,
        device: Device = "desktop",
        image_type: Literal["png", "jpeg", "webp"] = "png",
        selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Take a screenshot of a web page (viewport, full page, or one element) and
        return a hosted image URL.

        Args:
            url: Full URL of the page.
            full_page: Capture the whole page instead of the viewport.
            device: Device to emulate.
            image_type: Image format.
            selector: CSS selector of a single element to capture.

        """
        return self._call(
            "screenshot",
            {
                "url": url,
                "fullPage": full_page,
                "device": device,
                "type": image_type,
                "selector": selector,
            },
        )

    def url_to_pdf(
        self,
        url: str,
        paper_format: Literal[
            "a4", "letter", "legal", "a0", "a1", "a2", "a3", "a5", "a6"
        ] = "a4",
        orientation: Literal["portrait", "landscape"] = "portrait",
    ) -> Dict[str, Any]:
        """
        Convert a web page to a PDF and return a hosted download URL.

        Args:
            url: Full URL of the page.
            paper_format: Paper size.
            orientation: Page orientation.

        """
        return self._call(
            "url2_pdf", {"url": url, "format": paper_format, "orientation": orientation}
        )

    # ── Website diagnostics ───────────────────────────────────────────────

    def site_status(self, url: str, follow_redirect: bool = False) -> Dict[str, Any]:
        """
        Check whether a website is up or down and return its HTTP status.

        Args:
            url: Website URL or domain.
            follow_redirect: Follow redirects before checking.

        """
        return self._call("site_status", {"url": url, "followRedirect": follow_redirect})

    def dns_records(
        self, url: str, types: Optional[List[DnsType]] = None
    ) -> Dict[str, Any]:
        """
        Look up DNS records (A, AAAA, CNAME, MX, NS, SOA, TXT, CAA, SRV) for a domain.

        Args:
            url: Website URL or domain.
            types: Record types to return. Defaults to all.

        """
        return self._call("dns_record", {"url": url, "types": types})

    def dnssec(self, url: str) -> Dict[str, Any]:
        """
        Check whether DNSSEC is enabled and validating for a domain.

        Args:
            url: Website URL or domain.

        """
        return self._call("dns_sec", {"url": url})

    def tls_scan(self, url: str) -> Dict[str, Any]:
        """
        Inspect a domain's TLS/SSL setup: certificate details and expiry, and which
        protocol versions (SSLv2 to TLS 1.3) are supported.

        Args:
            url: Website URL or domain.

        """
        return self._call("tls_scan", {"url": url})

    def redirect_check(self, url: str) -> Dict[str, Any]:
        """
        Trace every redirect hop of a URL with status codes.

        Args:
            url: Full URL.

        """
        return self._call("redirect_check", {"url": url})

    def broken_links(self, url: str, follow_redirect: bool = False) -> Dict[str, Any]:
        """
        Find broken links on a web page.

        Args:
            url: Full URL of the page.
            follow_redirect: Follow redirects before checking.

        """
        return self._call("broken_link", {"url": url, "followRedirect": follow_redirect})

    def load_time(self, url: str, follow_redirect: bool = False) -> Dict[str, Any]:
        """
        Measure a page's load time, including DNS, connect, TLS, and first byte.

        Args:
            url: Full URL of the page.
            follow_redirect: Follow redirects before measuring.

        """
        return self._call("load_time", {"url": url, "followRedirect": follow_redirect})

    def mixed_content(self, url: str, follow_redirect: bool = False) -> Dict[str, Any]:
        """
        Find insecure HTTP resources loaded on an HTTPS page.

        Args:
            url: Full URL of the page.
            follow_redirect: Follow redirects before checking.

        """
        return self._call(
            "mixed_content", {"url": url, "followRedirect": follow_redirect}
        )

    def lighthouse(self, url: str, device: Device = "desktop") -> Dict[str, Any]:
        """
        Run a Google Lighthouse audit and return performance, SEO, accessibility,
        and best-practices scores. Slow: can take a minute or more.

        Args:
            url: Full URL of the page.
            device: Audit as desktop or mobile.

        """
        return self._call("lighthouse", {"url": url, "device": device})
