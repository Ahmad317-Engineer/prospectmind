"""
Async web scraper for gathering live company context.

Fetches homepage content, meta tags, and news signals to build
a research brief that powers personalization.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .models import CompanyContext

logger = logging.getLogger(__name__)

# Common user agent to avoid basic bot detection
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

MAX_BODY_CHARS = 8_000  # max chars to send to LLM from raw page


def clean_text(text: str) -> str:
    """Remove excess whitespace and normalize text."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_meta_content(soup: BeautifulSoup, name: str) -> Optional[str]:
    """Extract content from a <meta> tag by name or property."""
    tag = soup.find("meta", attrs={"name": name}) or soup.find(
        "meta", attrs={"property": name}
    )
    if tag and tag.get("content"):
        return clean_text(tag["content"])
    return None


def extract_text_snippets(soup: BeautifulSoup, max_chars: int = MAX_BODY_CHARS) -> str:
    """
    Extract meaningful text from the page body.
    Removes nav, footer, script, style, etc.
    """
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()

    # Prioritize hero, about, value-prop sections
    priority_selectors = [
        "main",
        "[class*='hero']",
        "[class*='about']",
        "[class*='value']",
        "[class*='mission']",
        "article",
        ".content",
        "#content",
    ]
    collected = []
    for sel in priority_selectors:
        el = soup.select_one(sel)
        if el:
            collected.append(el.get_text(separator=" "))

    # Fall back to body text
    if not collected:
        body = soup.find("body")
        if body:
            collected.append(body.get_text(separator=" "))

    raw = " ".join(collected)
    raw = clean_text(raw)
    return raw[:max_chars]


async def fetch_url(
    client: httpx.AsyncClient,
    url: str,
    timeout: int = 15,
) -> Tuple[Optional[str], int]:
    """Fetch a URL and return (html_content, status_code)."""
    try:
        resp = await client.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        return resp.text, resp.status_code
    except httpx.TimeoutException:
        logger.debug(f"Timeout fetching {url}")
        return None, 408
    except httpx.HTTPStatusError as e:
        logger.debug(f"HTTP {e.response.status_code} for {url}")
        return None, e.response.status_code
    except Exception as e:
        logger.debug(f"Error fetching {url}: {e}")
        return None, 0


async def scrape_company(
    domain: str,
    company_name: str,
    timeout: int = 20,
) -> CompanyContext:
    """
    Scrape a company's website and extract context signals.

    Returns a CompanyContext with whatever could be found.
    Always returns something — never raises.
    """
    ctx = CompanyContext(domain=domain, company_name=company_name)

    base_url = f"https://{domain}"

    async with httpx.AsyncClient(headers=HEADERS, timeout=timeout) as client:
        # Fetch homepage
        html, status = await fetch_url(client, base_url, timeout=timeout)

        if html is None:
            # Try www subdomain fallback
            www_url = f"https://www.{domain}"
            html, status = await fetch_url(client, www_url, timeout=timeout)

        if html is None:
            logger.warning(f"Could not fetch {domain} (status={status})")
            return ctx

        soup = BeautifulSoup(html, "html.parser")

        # --- Extract meta signals ---
        title = soup.find("title")
        if title:
            ctx.tagline = clean_text(title.get_text())

        for meta_name in ["description", "og:description", "twitter:description"]:
            desc = extract_meta_content(soup, meta_name)
            if desc:
                ctx.description = desc
                break

        # --- Extract body text ---
        ctx.raw_homepage_snippet = extract_text_snippets(soup, MAX_BODY_CHARS)

        # --- Extract hiring signals from job page ---
        job_urls = [
            urljoin(base_url, "/careers"),
            urljoin(base_url, "/jobs"),
            urljoin(base_url, "/about"),
        ]

        hiring_tasks = [fetch_url(client, u, timeout=10) for u in job_urls]
        hiring_results = await asyncio.gather(*hiring_tasks, return_exceptions=True)

        for url, result in zip(job_urls, hiring_results):
            if isinstance(result, Exception):
                continue
            job_html, job_status = result
            if job_html and job_status == 200:
                job_soup = BeautifulSoup(job_html, "html.parser")
                snippet = extract_text_snippets(job_soup, 2000)
                if snippet:
                    # Look for role keywords suggesting company priorities
                    roles = _extract_job_roles(snippet)
                    ctx.hiring_signals.extend(roles[:5])
                break  # only use first successful job page

        # --- Detect tech stack from page source hints ---
        ctx.tech_stack_hints = _detect_tech_hints(html)

    return ctx


def _extract_job_roles(text: str) -> List[str]:
    """Extract job title mentions from careers page text."""
    role_patterns = [
        r"(?:Senior|Lead|Principal|Staff|Head of|VP of|Director of|Manager of)\s+[\w\s]+Engineer",
        r"(?:Senior|Lead|Principal|Staff|Head of|VP of|Director of|Manager of)\s+[\w\s]+Manager",
        r"(?:Senior|Lead|Principal|Staff)?\s*[\w]+\s+Engineer",
        r"(?:Senior|Lead|Principal|Staff)?\s*Data\s+Scientist",
        r"(?:Senior|Lead|Principal|Staff)?\s*Product\s+Manager",
        r"(?:Senior|Lead|Principal|Staff)?\s*Designer",
    ]
    found = []
    for pattern in role_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            role = clean_text(m)
            if role and role not in found and len(role) < 60:
                found.append(role)
        if len(found) >= 8:
            break
    return found


def _detect_tech_hints(html: str) -> List[str]:
    """Detect technology hints from page source."""
    hints = []
    tech_signatures = {
        "React": ["react.min.js", "react-dom", "_next/static"],
        "Vue.js": ["vue.min.js", "vuejs.org"],
        "Angular": ["angular.min.js", "@angular"],
        "Next.js": ["_next/static", "__NEXT_DATA__"],
        "Salesforce": ["salesforce.com", "force.com", "pardot"],
        "HubSpot": ["hubspot.com", "hs-scripts.com"],
        "Segment": ["segment.com/analytics.js", "cdn.segment.com"],
        "Intercom": ["intercom.io", "widget.intercom.io"],
        "Stripe": ["js.stripe.com"],
        "AWS": ["amazonaws.com", "cloudfront.net"],
        "Shopify": ["cdn.shopify.com", "shopifycloud"],
        "WordPress": ["wp-content", "wp-includes"],
        "Gatsby": ["gatsby-runtime"],
        "Vercel": ["vercel.app", "_vercel"],
    }
    html_lower = html.lower()
    for tech, signatures in tech_signatures.items():
        if any(sig.lower() in html_lower for sig in signatures):
            hints.append(tech)
    return hints
