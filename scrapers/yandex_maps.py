"""Yandex Maps scraper using Playwright.

Showcases enterprise scraping mechanics:
- smart proxy hook
- pop-up/cookie/modal closure
- infinite scroll over result cards
- graceful timeout handling

Run only when you have permission and comply with Yandex terms.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from urllib.parse import quote_plus

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from utils.rate_limiter import ProxyRotator, SmartRateLimiter

logger = logging.getLogger(__name__)


@dataclass
class YandexPlace:
    name: str
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    source_url: str | None = None


class YandexMapsScraper:
    def __init__(self, headless: bool = True, max_results: int = 30, proxy_rotator: ProxyRotator | None = None):
        self.headless = headless
        self.max_results = max_results
        self.proxy_rotator = proxy_rotator or ProxyRotator()
        self.rate_limiter = SmartRateLimiter(min_delay=1.5, max_delay=4.0, concurrency=1)

    async def _close_popups(self, page) -> None:
        selectors = [
            "button:has-text('Accept')",
            "button:has-text('I agree')",
            "button:has-text('Понятно')",
            "button:has-text('Принять')",
            "button[aria-label='Закрыть']",
            "button[aria-label='Close']",
            ".modal__close",
        ]
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=800):
                    await locator.click(timeout=800)
                    logger.info("Closed popup via selector %s", selector)
            except Exception:
                continue

    async def _infinite_scroll(self, page) -> None:
        """Scroll result panel until no new cards appear or max_results reached."""
        previous_count = -1
        stagnant_rounds = 0
        result_list = page.locator(".search-list-view__list, [class*='search-list']").first

        while stagnant_rounds < 4:
            cards = page.locator(".search-snippet-view, [class*='business-snippet']")
            count = await cards.count()
            if count >= self.max_results:
                break
            stagnant_rounds = stagnant_rounds + 1 if count == previous_count else 0
            previous_count = count
            try:
                await result_list.evaluate("el => el.scrollTo(0, el.scrollHeight)")
            except Exception:
                await page.mouse.wheel(0, 2500)
            await asyncio.sleep(1.2)

    async def scrape(self, query: str, location: str) -> list[YandexPlace]:
        url = f"https://yandex.com/maps/?text={quote_plus(query + ' ' + location)}"
        proxy = self.proxy_rotator.next()
        launch_kwargs = {"headless": self.headless}
        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}

        places: list[YandexPlace] = []
        async with self.rate_limiter:
            async with async_playwright() as p:
                browser = await p.chromium.launch(**launch_kwargs)
                context = await browser.new_context(locale="ru-RU", user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "Chrome/124.0 Safari/537.36 MarketMiner/0.1"
                ))
                page = await context.new_page()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                    await self._close_popups(page)
                    await self._infinite_scroll(page)

                    cards = page.locator(".search-snippet-view, [class*='business-snippet']")
                    for i in range(min(await cards.count(), self.max_results)):
                        card = cards.nth(i)
                        text = await card.inner_text(timeout=2_000)
                        lines = [line.strip() for line in text.splitlines() if line.strip()]
                        if not lines:
                            continue
                        places.append(YandexPlace(name=lines[0], address=lines[1] if len(lines) > 1 else None, source_url=url))
                except PlaywrightTimeoutError:
                    logger.warning("Yandex Maps timed out for query=%s location=%s", query, location)
                finally:
                    await browser.close()
        return places
