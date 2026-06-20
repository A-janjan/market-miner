# MarketMiner – AI-Powered B2B Prospect Intelligence & Verification Pipeline

MarketMiner is an end-to-end **CLI + Streamlit** project demonstrating web scraping, NLP/LLM query expansion, strict data validation, enrichment, scoring, deduplication, and interactive visualization for B2B prospect intelligence.

Applied demo scenario: **find manufacturers of silicone insulators in Russia**, extract decision-makers, and validate contact data into a tiered Level 1 / Level 2 / Level 3 database.

> ⚠️ Compliance note: this repository is designed as a portfolio/demo pipeline. Always respect robots.txt, site terms, privacy laws, rate limits, and anti-abuse rules. The included sample output is synthetic but realistic. Live scraping modules are conservative and configurable.

## Enterprise-grade features showcased

- **Smart rate-limiting & proxy rotation**: async throttling, jitter, and optional proxy pool hooks in `utils/rate_limiter.py` and scraper constructors.
- **Resilience handling**: website failures become `Unverified` / `site_down` statuses instead of crashing the run.
- **Cost-aware AI**: local keyword/sentence heuristics run first; optional LLM is called only for Level 3 VIP extraction when `OPENAI_API_KEY` is configured.
- **Dockerized deployment**: `Dockerfile` and `docker-compose.yml` let reviewers launch the dashboard quickly.
- **Transparent logs**: every classification and skip decision is written under `pipeline_logs/`.

## Repository artifacts requested

- `sample_output.json` — exactly 5 demo companies matching the silicone/Russia criteria.
- `streamlit_app.py` — interactive dashboard with live logs and downloadable CSV/JSON.
- `pipeline_logs/` — example trace logs explaining Level 1/2/3 classifications and skips.
- `scrapers/yandex_maps.py` — Playwright scraper skeleton with infinite-scroll and pop-up handling.
- `processors/entity_resolver.py` — Pydantic schema enforcement and fuzzy deduplication.
- `validators/smtp_checker.py` — async MX/SMTP handshake validator without sending emails.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

CLI demo:

```bash
python -m marketminer.cli --keywords "Silicone Insulators" --location Russia --demo
```

Docker:

```bash
docker build -t marketminer .
docker run --rm -p 8501:8501 marketminer
```

## Optional live integrations

- `OPENAI_API_KEY`: enables GPT-based query expansion and VIP NER fallback.
- `PROXY_LIST`: comma-separated proxy URLs for scrapers.
- `MARKETMINER_LIVE_SCRAPE=1`: enables live web requests. Default uses demo/safe sample candidates.

## Architecture

```text
User input -> Query Expansion -> Multi-source discovery -> Website classification
          -> Level 1/2 extraction -> Level 3 VIP enrichment -> Email/MX/SMTP validation
          -> Pydantic validation -> fuzzy dedupe -> confidence scoring -> Streamlit/CLI exports
```

## Example log messages

- `Accepted Volga Polymer Insulators: manufacturer keywords found on /products and GOST certification detected.`
- `Skipped ElectroTrade SPB: distributor/reseller phrases outweighed manufacturing evidence.`
- `Marked contact as Unverified: MX lookup timed out; retaining syntax validation only.`
