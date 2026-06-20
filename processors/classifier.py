from __future__ import annotations

import re
from dataclasses import dataclass

MANUFACTURING_KEYWORDS = [
    "производство", "производитель", "завод", "изготавливает", "литье", "формование",
    "production", "manufacturer", "factory", "molding", "capacity", "iso", "gost", "гост",
    "сертификат", "лаборатория", "линия", "компаунд", "htv", "rtv",
]
DISTRIBUTOR_KEYWORDS = ["дистрибьютор", "поставщик", "реселлер", "оптовая продажа", "dealer", "distributor", "reseller", "trading"]
PRODUCT_KEYWORDS = ["изолятор", "insulator", "silicone", "силикон", "кремни", "полимер", "composite", "силоксан"]


@dataclass
class ClassificationResult:
    label: str
    score: int
    evidence: str
    manufacturer_hits: int
    distributor_hits: int


def _count(text: str, words: list[str]) -> int:
    low = text.lower()
    return sum(len(re.findall(re.escape(w.lower()), low)) for w in words)


def classify_website(text: str) -> ClassificationResult:
    m_hits = _count(text, MANUFACTURING_KEYWORDS)
    d_hits = _count(text, DISTRIBUTOR_KEYWORDS)
    p_hits = _count(text, PRODUCT_KEYWORDS)

    raw = 45 + min(m_hits * 7, 35) + min(p_hits * 4, 15) - min(d_hits * 8, 30)
    score = max(0, min(100, raw))
    label = "Manufacturer" if score >= 65 and m_hits >= max(1, d_hits) and p_hits > 0 else "Distributor_or_Irrelevant"

    evidence_bits = []
    if m_hits:
        evidence_bits.append(f"{m_hits} manufacturing keywords")
    if p_hits:
        evidence_bits.append(f"{p_hits} silicone/insulator product mentions")
    if d_hits:
        evidence_bits.append(f"{d_hits} distributor/reseller keywords")
    evidence = "; ".join(evidence_bits) or "No relevant manufacturing evidence"
    return ClassificationResult(label, score, evidence, m_hits, d_hits)
