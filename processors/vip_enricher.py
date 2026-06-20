from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


ROLE_PATTERNS = [
    r"(?P<role>Commercial Director|Technical Director|Chief Engineer|Head of Procurement|Production Manager|General Director)",
    r"(?P<role>Коммерческий директор|Технический директор|Главный инженер|Генеральный директор|Руководитель отдела продаж)",
]
NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+|[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)\b")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"\+7[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")


@dataclass
class VIPCandidate:
    name: str
    role: str
    direct_email: str | None = None
    direct_phone: str | None = None


def guess_email_patterns(name: str, website: str) -> list[str]:
    domain = urlparse(website).netloc.removeprefix("www.")
    parts = name.lower().split()
    if len(parts) < 2 or not domain:
        return []
    first, last = parts[0], parts[-1]
    return [
        f"{first}.{last}@{domain}",
        f"{first[0]}.{last}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{last}@{domain}",
    ]


def extract_vips(text: str, website: str, max_people: int = 3) -> list[VIPCandidate]:
    emails = EMAIL_PATTERN.findall(text)
    phones = PHONE_PATTERN.findall(text)
    roles = []
    for pattern in ROLE_PATTERNS:
        roles.extend(m.group("role") for m in re.finditer(pattern, text, flags=re.I))
    names = NAME_PATTERN.findall(text)

    people: list[VIPCandidate] = []
    for i, role in enumerate(roles[:max_people]):
        name = names[i] if i < len(names) else f"Unknown Executive {i + 1}"
        email = emails[i] if i < len(emails) else (guess_email_patterns(name, website) or [None])[0]
        phone = phones[i] if i < len(phones) else None
        people.append(VIPCandidate(name=name, role=role, direct_email=email, direct_phone=phone))
    return people
