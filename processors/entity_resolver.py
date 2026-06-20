"""Strict entity schema validation and deduplication.

This module is intentionally central to the project: every scraper/enricher emits
messy dictionaries, and this resolver is the gatekeeper that transforms them into
a predictable enterprise JSON contract.
"""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, ValidationError, field_validator
try:
    from rapidfuzz import fuzz
except ModuleNotFoundError:  # graceful fallback for bare Python demos
    from difflib import SequenceMatcher

    class _FuzzFallback:
        @staticmethod
        def token_set_ratio(a: str, b: str) -> int:
            return int(SequenceMatcher(None, " ".join(sorted(a.lower().split())), " ".join(sorted(b.lower().split()))).ratio() * 100)

    fuzz = _FuzzFallback()


class DecisionMaker(BaseModel):
    name: str = Field(min_length=2)
    role: str = Field(min_length=2)
    direct_phone: Optional[str] = None
    direct_email: Optional[str] = None
    email_verification_status: str = Field(default="Unverified")
    linkedin_profile: Optional[str] = None

    @field_validator("email_verification_status")
    @classmethod
    def known_status(cls, v: str) -> str:
        allowed = {
            "Unverified",
            "Syntax_Validated",
            "MX_record_exists",
            "SMTP_handshake_accepted",
            "SMTP_rejected",
            "Domain_has_no_MX",
            "Timeout",
        }
        if v not in allowed:
            raise ValueError(f"Unknown email verification status: {v}")
        return v


class Level1General(BaseModel):
    legal_address: str
    industry_classification: str
    estimated_employee_count: str


class Level2Contact(BaseModel):
    website: HttpUrl
    public_phone: Optional[str] = None
    public_email: Optional[str] = None
    socials: List[str] = Field(default_factory=list)


class Level3VIPVerified(BaseModel):
    decision_makers: List[DecisionMaker] = Field(default_factory=list)
    extracted_manufacturing_evidence: str


class CompanyRecord(BaseModel):
    query_used: str
    company_name: str
    market_confidence_score: int = Field(ge=0, le=100)
    level_1_general: Level1General
    level_2_contact: Level2Contact
    level_3_vip_verified: Level3VIPVerified

    @property
    def domain(self) -> str:
        netloc = urlparse(str(self.level_2_contact.website)).netloc.lower()
        return netloc.removeprefix("www.")


def validate_company(raw: dict) -> CompanyRecord:
    """Validate one raw company dictionary against the strict schema."""
    try:
        return CompanyRecord.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Company failed schema validation: {exc}") from exc


def validate_companies(raw_records: list[dict]) -> list[CompanyRecord]:
    return [validate_company(record) for record in raw_records]


def dedupe_companies(records: list[CompanyRecord], threshold: int = 92) -> list[CompanyRecord]:
    """Deduplicate by domain and near-company names using RapidFuzz.

    Keeps the highest confidence record when a duplicate is detected.
    """
    kept: list[CompanyRecord] = []
    for candidate in sorted(records, key=lambda r: r.market_confidence_score, reverse=True):
        duplicate = False
        for existing in kept:
            same_domain = candidate.domain == existing.domain
            name_match = fuzz.token_set_ratio(candidate.company_name, existing.company_name) >= threshold
            if same_domain or name_match:
                duplicate = True
                break
        if not duplicate:
            kept.append(candidate)
    return kept


def records_to_jsonable(records: list[CompanyRecord]) -> list[dict]:
    return [record.model_dump(mode="json") for record in records]
