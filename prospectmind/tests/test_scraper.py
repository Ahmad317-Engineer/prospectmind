"""Tests for the web scraper module."""

import pytest

from prospectmind.scraper import (
    _detect_tech_hints,
    _extract_job_roles,
    clean_text,
    extract_meta_content,
    extract_text_snippets,
)
from bs4 import BeautifulSoup


class TestCleanText:
    def test_removes_extra_whitespace(self):
        assert clean_text("  hello   world  ") == "hello world"

    def test_normalizes_newlines(self):
        assert clean_text("line1\n\nline2") == "line1 line2"

    def test_empty_string(self):
        assert clean_text("") == ""


class TestExtractMetaContent:
    def test_name_meta(self):
        html = '<meta name="description" content="We build great software.">'
        soup = BeautifulSoup(html, "html.parser")
        assert extract_meta_content(soup, "description") == "We build great software."

    def test_og_meta(self):
        html = '<meta property="og:description" content="Open Graph desc.">'
        soup = BeautifulSoup(html, "html.parser")
        assert extract_meta_content(soup, "og:description") == "Open Graph desc."

    def test_missing_meta_returns_none(self):
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert extract_meta_content(soup, "description") is None


class TestExtractTextSnippets:
    def test_removes_script_style(self):
        html = """
        <html><body>
          <script>var x = 1;</script>
          <style>.foo { color: red; }</style>
          <main><p>Real content here.</p></main>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        text = extract_text_snippets(soup)
        assert "Real content here." in text
        assert "var x = 1" not in text
        assert ".foo" not in text

    def test_respects_max_chars(self):
        long_text = "word " * 10_000
        html = f"<html><body><p>{long_text}</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = extract_text_snippets(soup, max_chars=100)
        assert len(result) <= 100


class TestDetectTechHints:
    def test_detects_react(self):
        html = '<script src="/_next/static/chunks/react.js"></script>'
        hints = _detect_tech_hints(html)
        assert "React" in hints or "Next.js" in hints

    def test_detects_hubspot(self):
        html = '<script src="//js.hs-scripts.com/12345.js"></script>'
        hints = _detect_tech_hints(html)
        assert "HubSpot" in hints

    def test_detects_stripe(self):
        html = '<script src="https://js.stripe.com/v3/"></script>'
        hints = _detect_tech_hints(html)
        assert "Stripe" in hints

    def test_empty_html(self):
        hints = _detect_tech_hints("<html></html>")
        assert isinstance(hints, list)


class TestExtractJobRoles:
    def test_finds_engineering_roles(self):
        text = "We're hiring a Senior Backend Engineer and a Lead DevOps Engineer."
        roles = _extract_job_roles(text)
        assert any("Engineer" in r for r in roles)

    def test_finds_product_roles(self):
        text = "Open positions: Senior Product Manager, Principal Designer"
        roles = _extract_job_roles(text)
        assert len(roles) >= 1

    def test_empty_text(self):
        assert _extract_job_roles("") == []

    def test_limits_results(self):
        text = " ".join(
            [f"Senior Software Engineer {i}" for i in range(20)]
        )
        roles = _extract_job_roles(text)
        assert len(roles) <= 8
