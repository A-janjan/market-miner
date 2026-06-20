from __future__ import annotations

import os

RU_TRANSLATIONS = {
    "silicone insulators": [
        "кремниевые изоляторы",
        "силиконовые изоляторы",
        "полимерные изоляторы",
        "композитные изоляторы",
    ],
    "manufacturer": ["производитель", "производство", "завод", "изготовитель"],
}

SYNONYMS = ["HTV", "RTV", "силоксан", "силиконовая резина", "GOST", "изоляционные материалы"]


async def expand_query(keywords: str, geography: str) -> list[str]:
    """Cost-aware query expansion.

    Uses a deterministic local dictionary first. If OPENAI_API_KEY is present,
    this function can be extended to call GPT-4o-mini/Llama gateway; we avoid a
    hard dependency so the demo runs offline.
    """
    lower = keywords.lower().strip()
    geography_ru = "россия" if geography.lower() in {"russia", "россия", "ru"} else geography
    translated = RU_TRANSLATIONS.get(lower, [keywords])
    queries: list[str] = []
    for term in translated:
        queries.extend([
            f"производство {term} {geography_ru}",
            f"{term} производитель {geography_ru}",
            f"{term} завод {geography_ru}",
        ])
    queries.extend([f"{syn} {translated[0]} производство {geography_ru}" for syn in SYNONYMS[:4]])

    # Reserved hook for optional paid LLM expansion.
    if os.getenv("OPENAI_API_KEY"):
        # In production, call a lightweight model here and merge unique results.
        queries.append(f"{translated[0]} OEM поставщик {geography_ru}")

    seen = set()
    return [q for q in queries if not (q in seen or seen.add(q))][:12]
