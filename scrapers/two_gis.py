"""2GIS discovery adapter.

The public implementation is intentionally conservative: it exposes the async
interface and proxy/rate-limit hooks used by the orchestrator. In production,
wire this to an approved 2GIS API/account or a ToS-compliant export source.
"""
from __future__ import annotations

from dataclasses import dataclass

from utils.rate_limiter import ProxyRotator, SmartRateLimiter


@dataclass
class TwoGISCompany:
    name: str
    address: str | None
    phone: str | None
    website: str | None
    rubric: str | None = None


class TwoGISScraper:
    def __init__(self, proxy_rotator: ProxyRotator | None = None):
        self.proxy_rotator = proxy_rotator or ProxyRotator()
        self.rate_limiter = SmartRateLimiter(min_delay=1.0, max_delay=3.0, concurrency=2)

    async def search(self, query: str, location: str) -> list[TwoGISCompany]:
        # Hook for approved API/scrape implementation. Returning [] lets the
        # pipeline continue with other sources instead of failing.
        async with self.rate_limiter:
            _ = self.proxy_rotator.next()
            return []
