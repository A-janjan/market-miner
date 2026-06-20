"""Russian industry portal parser, e.g. promportal-style listing pages."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from utils.rate_limiter import SmartRateLimiter


@dataclass
class PortalListing:
    company_name: str
    profile_url: str
    snippet: str


class IndustryPortalScraper:
    def __init__(self, base_url: str = "https://promportal.su"):
        self.base_url = base_url
        self.rate_limiter = SmartRateLimiter(min_delay=1.0, max_delay=2.5, concurrency=2)

    async def search(self, query: str) -> list[PortalListing]:
        # Generic parser; selectors are intentionally broad because industry
        # portals vary frequently.
        url = f"{self.base_url}/search?query={query}"
        listings: list[PortalListing] = []
        async with self.rate_limiter:
            try:
                async with aiohttp.ClientSession(headers={"User-Agent": "MarketMinerBot/0.1"}) as session:
                    async with session.get(url, timeout=10) as resp:
                        if resp.status >= 400:
                            return []
                        soup = BeautifulSoup(await resp.text(errors="ignore"), "html.parser")
                for card in soup.select("article, .item, .company, .search-result")[:25]:
                    text = card.get_text(" ", strip=True)
                    a = card.find("a", href=True)
                    if text and a:
                        listings.append(PortalListing(company_name=text.split(" ")[0][:120], profile_url=urljoin(self.base_url, a["href"]), snippet=text[:500]))
            except Exception:
                return []
        return listings
