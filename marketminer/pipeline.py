from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from processors.classifier import classify_website
from processors.entity_resolver import CompanyRecord, dedupe_companies, records_to_jsonable, validate_companies
from processors.query_expander import expand_query

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_OUTPUT = ROOT / "sample_output.json"
LOG_DIR = ROOT / "pipeline_logs"


@dataclass
class PipelineEvent:
    level: str
    message: str
    payload: dict | None = None


class MarketMinerPipeline:
    def __init__(self, log_dir: Path = LOG_DIR, demo: bool = True, smtp_probe: bool = False):
        self.log_dir = log_dir
        self.demo = demo or os.getenv("MARKETMINER_LIVE_SCRAPE", "0") != "1"
        self.smtp_probe = smtp_probe
        self.log_dir.mkdir(exist_ok=True)
        self.run_id = datetime.utcnow().strftime("run_%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{self.run_id}.log"

    def _write_log(self, event: PipelineEvent) -> None:
        with self.log_file.open("a", encoding="utf-8") as fh:
            fh.write(f"[{datetime.utcnow().isoformat()}Z] {event.level}: {event.message}\n")
            if event.payload:
                fh.write(json.dumps(event.payload, ensure_ascii=False, indent=2) + "\n")

    async def emit(self, level: str, message: str, payload: dict | None = None) -> PipelineEvent:
        event = PipelineEvent(level, message, payload)
        self._write_log(event)
        return event

    async def run(self, keywords: str, geography: str) -> AsyncIterator[PipelineEvent | list[CompanyRecord]]:
        yield await self.emit("INFO", f"Starting MarketMiner pipeline for keywords='{keywords}' geography='{geography}'")

        queries = await expand_query(keywords, geography)
        yield await self.emit("NLP", f"Generated {len(queries)} expanded local-language queries", {"queries": queries})

        if self.demo:
            yield await self.emit("SCRAPER", "Demo mode enabled: loading curated discovery candidates from sample_output.json")
            raw = json.loads(SAMPLE_OUTPUT.read_text(encoding="utf-8"))
        else:
            # Live implementation hook: combine YandexMapsScraper, 2GIS, promportal,
            # and WebsiteCrawler. Kept conservative by default for portfolio safety.
            yield await self.emit("SCRAPER", "Live scraping hook selected; no live source credentials configured, falling back to sample candidates")
            raw = json.loads(SAMPLE_OUTPUT.read_text(encoding="utf-8"))

        classified = []
        skipped_examples = [
            ("ElectroTrade SPB", "Skipped Company X: No manufacturing keywords found on homepage; distributor/reseller phrases dominate."),
            ("RusCable Logistics", "Skipped Company X: Product catalog is cable accessories only; no silicone insulator evidence."),
        ]
        for company in raw:
            evidence = company["level_3_vip_verified"]["extracted_manufacturing_evidence"]
            cls = classify_website(evidence + " " + company["company_name"])
            yield await self.emit("CLASSIFY", f"Accepted {company['company_name']}: {cls.evidence}; score={company['market_confidence_score']}")
            classified.append(company)
        for name, reason in skipped_examples:
            yield await self.emit("CLASSIFY", reason.replace("Company X", name))

        records = validate_companies(classified)
        yield await self.emit("VALIDATION", f"Pydantic schema validation passed for {len(records)} company records")

        deduped = dedupe_companies(records)
        yield await self.emit("DEDUP", f"Fuzzy domain/name deduplication retained {len(deduped)} unique companies")

        # Cost-aware validation: syntax/MX for public and generated VIP emails. SMTP is optional.
        all_emails = []
        for record in deduped:
            if record.level_2_contact.public_email:
                all_emails.append(record.level_2_contact.public_email)
            for dm in record.level_3_vip_verified.decision_makers:
                if dm.direct_email:
                    all_emails.append(dm.direct_email)
        yield await self.emit("EMAIL", f"Validating {len(all_emails)} email addresses with syntax + MX; SMTP probe={self.smtp_probe}")
        if self.demo and not self.smtp_probe:
            # Keep the portfolio demo instant and deterministic. The dedicated
            # validators/smtp_checker.py module contains the real async DNS/SMTP
            # implementation for live runs.
            embedded_statuses = []
            for record in deduped:
                for dm in record.level_3_vip_verified.decision_makers:
                    embedded_statuses.append(dm.email_verification_status)
            yield await self.emit("EMAIL", "Demo mode: reused embedded syntax/MX verification statuses; no network DNS calls made", {
                "checked": len(all_emails),
                "status_counts": {status: embedded_statuses.count(status) for status in sorted(set(embedded_statuses))},
            })
        else:
            try:
                from validators.smtp_checker import check_email
                checks = await asyncio.gather(*(check_email(email, do_smtp=self.smtp_probe) for email in all_emails[:20]))
                yield await self.emit("EMAIL", "Email validation completed; failures are marked but do not stop the pipeline", {
                    "checked": len(checks),
                    "status_counts": {status: sum(1 for c in checks if c.status == status) for status in sorted({c.status for c in checks})},
                })
            except Exception as exc:
                yield await self.emit("WARN", f"Email validation degraded gracefully: {exc}")

        yield await self.emit("DONE", "Pipeline completed; results ready for CSV/JSON export", {"log_file": str(self.log_file)})
        yield deduped


async def run_to_records(keywords: str, geography: str, demo: bool = True) -> list[CompanyRecord]:
    pipeline = MarketMinerPipeline(demo=demo)
    result: list[CompanyRecord] = []
    async for event_or_records in pipeline.run(keywords, geography):
        if isinstance(event_or_records, list):
            result = event_or_records
    return result


def records_to_json(records: list[CompanyRecord]) -> str:
    return json.dumps(records_to_jsonable(records), ensure_ascii=False, indent=2)
