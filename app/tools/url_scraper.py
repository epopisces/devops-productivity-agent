"""URL Scraper Tool Functions.

Standalone sync functions for fetching and parsing web content.
No agent wrapper — these are registered directly as tools on agents that need them.
"""

import atexit
import logging
from typing import Annotated
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import Field

from app.config import get_config
from app.metrics import track_tool_call

# Logger for URL scraper
logger = logging.getLogger("workflow.url_scraper")

# Connection-pooled HTTP client (lazy initialized)
_http_client: httpx.Client | None = None


def _get_http_client() -> httpx.Client:
    """Get or create a connection-pooled HTTP client.

    Uses HTTP/2 and connection pooling for better performance.
    """
    global _http_client
    if _http_client is None:
        config = get_config()
        _http_client = httpx.Client(
            timeout=config.scraper.timeout,
            follow_redirects=True,
            headers={"User-Agent": config.scraper.user_agent},
            http2=True,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        logger.debug("Created connection-pooled HTTP client with HTTP/2")
    return _http_client


def _close_http_client() -> None:
    """Close the HTTP client on module cleanup."""
    global _http_client
    if _http_client is not None:
        _http_client.close()
        _http_client = None


# Register cleanup on exit
atexit.register(_close_http_client)


@track_tool_call("url_scraper")
def fetch_url(
    url: Annotated[str, Field(description="The URL to fetch and parse content from.")]
) -> str:
    """Fetch and parse web content from a URL.

    Retrieves the HTML content and extracts the main text,
    removing scripts, styles, and navigation elements.

    Args:
        url: The URL to fetch content from.

    Returns:
        Extracted text content from the webpage, or an error message.
    """
    logger.info(f"[TOOL CALL] fetch_url invoked with URL: {url}")
    config = get_config()

    # Validate URL
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            logger.warning(f"Invalid URL format: {url}")
            return f"Error: Invalid URL format: {url}"
    except Exception as e:
        logger.error(f"URL parse error: {e}")
        return f"Error: Could not parse URL: {e}"

    logger.debug(f"Fetching URL: {url}")

    # Fetch content using connection-pooled client
    try:
        client = _get_http_client()
        response = client.get(url)
        response.raise_for_status()
        html_content = response.text
        logger.debug(f"Fetched {len(html_content)} bytes from {url}")
    except httpx.TimeoutException:
        logger.error(f"Request timeout after {config.scraper.timeout}s: {url}")
        return f"Error: Request timed out after {config.scraper.timeout} seconds"
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code}: {url}")
        return f"Error: HTTP {e.response.status_code} - {e.response.reason_phrase}"
    except httpx.RequestError as e:
        logger.error(f"Request error for {url}: {e}")
        return f"Error: Could not fetch URL: {e}"

    # Parse HTML and extract text using lxml for speed
    try:
        soup = BeautifulSoup(html_content, "lxml")

        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            element.decompose()

        # Try to find main content area
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find(class_=["content", "main-content", "post-content"])
            or soup.find("body")
        )

        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # Clean up multiple newlines and whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)

        # Detect JS-only / SPA pages that returned no real content
        js_required_signals = [
            "javascript must be enabled",
            "javascript is required",
            "enable javascript to continue",
            "this app requires javascript",
            "you need to enable javascript",
        ]
        text_lower = text.lower()
        if any(sig in text_lower for sig in js_required_signals) and len(text) < 500:
            logger.warning(f"JS-only page detected (no usable content): {url}")
            title = soup.title.string if soup.title else "No title"
            return (
                f"URL: {url}\nTitle: {title}\n\n"
                f"Error: This page requires JavaScript to render its content "
                f"(e.g. Notion, single-page apps). The scraper cannot execute "
                f"JavaScript, so no meaningful content was extracted. "
                f"Consider pasting the page content directly instead."
            )

        # Truncate if too long
        if len(text) > config.scraper.max_content_length:
            logger.debug(f"Content truncated from {len(text)} to {config.scraper.max_content_length} chars")
            text = text[: config.scraper.max_content_length] + "\n\n[Content truncated...]"

        # Get title
        title = soup.title.string if soup.title else "No title"

        logger.info(f"[TOOL RESULT] fetch_url completed: '{title}' ({len(text)} chars)")
        return f"URL: {url}\nTitle: {title}\n\nContent:\n{text}"

    except Exception as e:
        logger.error(f"HTML parse error for {url}: {e}")
        return f"Error: Could not parse HTML content: {e}"
