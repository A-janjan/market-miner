from __future__ import annotations

import asyncio
import itertools
import os
import random
from dataclasses import dataclass, field


@dataclass
class SmartRateLimiter:
    min_delay: float = 1.0
    max_delay: float = 4.0
    concurrency: int = 3
    _sem: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self._sem = asyncio.Semaphore(self.concurrency)

    async def __aenter__(self):
        await self._sem.acquire()
        await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._sem.release()


class ProxyRotator:
    def __init__(self, proxies: list[str] | None = None):
        raw = proxies or [p.strip() for p in os.getenv("PROXY_LIST", "").split(",") if p.strip()]
        self._cycle = itertools.cycle(raw) if raw else None

    def next(self) -> str | None:
        return next(self._cycle) if self._cycle else None
