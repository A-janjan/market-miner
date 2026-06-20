from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from marketminer.pipeline import MarketMinerPipeline
from processors.entity_resolver import records_to_jsonable


async def main() -> None:
    parser = argparse.ArgumentParser(description="MarketMiner B2B prospect intelligence pipeline")
    parser.add_argument("--keywords", default="Silicone Insulators")
    parser.add_argument("--location", default="Russia")
    parser.add_argument("--demo", action="store_true", help="Use curated demo data instead of live scraping")
    parser.add_argument("--smtp", action="store_true", help="Attempt non-sending SMTP RCPT validation")
    parser.add_argument("--out", default="marketminer_output.json")
    args = parser.parse_args()

    pipeline = MarketMinerPipeline(demo=args.demo, smtp_probe=args.smtp)
    final_records = []
    async for event_or_records in pipeline.run(args.keywords, args.location):
        if isinstance(event_or_records, list):
            final_records = event_or_records
        else:
            print(f"{event_or_records.level}: {event_or_records.message}")

    Path(args.out).write_text(json.dumps(records_to_jsonable(final_records), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(final_records)} records to {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
