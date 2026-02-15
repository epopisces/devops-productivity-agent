"""Tests for URL Scraper tool function."""

import pytest
from unittest.mock import patch, MagicMock

import httpx

from app.tools.url_scraper import fetch_url


def _make_mock_client(get_return=None, get_side_effect=None):
    """Create a mock HTTP client with configurable .get()."""
    mock_client = MagicMock()
    if get_side_effect:
        mock_client.get = MagicMock(side_effect=get_side_effect)
    else:
        mock_client.get = MagicMock(return_value=get_return)
    return mock_client


class TestFetchUrl:
    """Tests for the fetch_url tool function."""

    def test_fetch_url_invalid_url(self, mock_get_config):
        """Test handling of invalid URL format."""
        result = fetch_url("not-a-valid-url")
        assert "Error: Invalid URL format" in result

    def test_fetch_url_empty_url(self, mock_get_config):
        """Test handling of empty URL."""
        result = fetch_url("")
        assert "Error" in result

    def test_fetch_url_success(self, mock_get_config, mock_html_response):
        """Test successful URL fetch and parse."""
        mock_response = MagicMock()
        mock_response.text = mock_html_response
        mock_response.raise_for_status = MagicMock()
        client = _make_mock_client(get_return=mock_response)

        with patch("app.tools.url_scraper._get_http_client", return_value=client):
            result = fetch_url("https://example.com/test")

        assert "URL: https://example.com/test" in result
        assert "Title: Test Page - DevOps Guide" in result
        assert "Kubernetes Best Practices" in result
        # Nav and footer should be removed
        assert "Navigation menu" not in result
        assert "Footer content" not in result

    def test_fetch_url_timeout(self, mock_get_config):
        """Test handling of timeout errors."""
        client = _make_mock_client(get_side_effect=httpx.TimeoutException("Timeout"))

        with patch("app.tools.url_scraper._get_http_client", return_value=client):
            result = fetch_url("https://example.com/slow")

        assert "Error: Request timed out" in result

    def test_fetch_url_http_error(self, mock_get_config):
        """Test handling of HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"
        client = _make_mock_client(
            get_side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=mock_response,
            )
        )

        with patch("app.tools.url_scraper._get_http_client", return_value=client):
            result = fetch_url("https://example.com/notfound")

        assert "Error: HTTP 404" in result

    def test_fetch_url_content_truncation(self, mock_get_config):
        """Test that long content is truncated."""
        long_content = (
            "<!DOCTYPE html><html><head><title>Long Page</title></head>"
            f"<body><main>{'x' * 2000}</main></body></html>"
        )
        mock_response = MagicMock()
        mock_response.text = long_content
        mock_response.raise_for_status = MagicMock()
        client = _make_mock_client(get_return=mock_response)

        # Patch get_config at the call site so max_content_length=1000 is used
        with patch("app.tools.url_scraper.get_config", return_value=mock_get_config):
            with patch("app.tools.url_scraper._get_http_client", return_value=client):
                result = fetch_url("https://example.com/long")

        assert "[Content truncated...]" in result

    def test_fetch_url_extracts_main_content(self, mock_get_config):
        """Test that main content area is preferred."""
        html_with_main = """
        <!DOCTYPE html>
        <html><head><title>Test</title></head>
        <body>
        <div>Sidebar content</div>
        <main><p>This is the main content.</p></main>
        <div>Other content</div>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.text = html_with_main
        mock_response.raise_for_status = MagicMock()
        client = _make_mock_client(get_return=mock_response)

        with patch("app.tools.url_scraper._get_http_client", return_value=client):
            result = fetch_url("https://example.com/main")

        assert "main content" in result

    def test_fetch_url_js_only_page(self, mock_get_config):
        """Test that JS-only pages (e.g. Notion) are detected."""
        js_html = """
        <!DOCTYPE html>
        <html><head><title>Notion</title></head>
        <body>
        <div>JavaScript must be enabled in order to use Notion.</div>
        <div>Please enable JavaScript to continue.</div>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.text = js_html
        mock_response.raise_for_status = MagicMock()
        client = _make_mock_client(get_return=mock_response)

        with patch("app.tools.url_scraper._get_http_client", return_value=client):
            result = fetch_url("https://notion.so/some-page")

        assert "requires JavaScript" in result
        assert "Error" in result
