from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from utils.rate_limiter import SmartRateLimiter


@dataclass
class CrawledSite:
    url: str
    pages: dict[str, str] = field(default_factory=dict)
    status: str = "ok"
    error: str | None = None

    @property
    def combined_text(self) -> str:
        return "\n".join(self.pages.values())


class WebsiteCrawler:
    PATHS = ["/", "/about", "/about-us", "/o-kompanii", "/products", "/produkciya", "/contacts", "/kontakty", "/team", "/management", "/rukovodstvo"]

    def __init__(self, timeout: float = 10.0):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.rate_limiter = SmartRateLimiter(min_delay=0.2, max_delay=1.0, concurrency=4)

    async def fetch_text(self, session: aiohttp.ClientSession, url: str) -> str:
        async with self.rate_limiter:
            async with session.get(url, timeout=self.timeout, allow_redirects=True) as resp:
                if resp.status >= 400:
                    return ""
                html = await resp.text(errors="ignore")
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "noscript"]):
                    tag.extract()
                return re.sub(r"\s+", " ", soup.get_text(" ")).strip()

    async def crawl(self, base_url: str) -> CrawledSite:
        site = CrawledSite(url=base_url)
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "MarketMinerBot/0.1 portfolio demo"}) as session:
                tasks = []
                for path in self.PATHS:
                    tasks.append((path, asyncio.create_task(self.fetch_text(session, urljoin(base_url, path)))))
                for path, task in tasks:
                    try:
                        text = await task
                        if text:
                            site.pages[path] = text[:25_000]
                    except Exception as exc:
                        site.pages[path] = ""
                        site.error = str(exc)
        except Exception as exc:
            site.status = "site_down"
            site.error = str(exc)
        return site
