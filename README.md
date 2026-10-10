# IrDomain

Database of Iranian websites, including both `.ir` domains and non-`.ir` domains
run by Iranian services (e.g. `aparat.com`).

## Pipeline

1. **collect** — build a seed domain list from public sources:
   - Certificate Transparency (`crt.sh`, chunked per-prefix queries `a%.ir` … `*%.ir`)
   - Common Crawl index (`*.ir`, latest crawls, stride-sampled pages)
   - Tranco top list (`.ir` filter)
   - Majestic Million (`.ir` filter)
   - Curated GitHub domain lists (Iran-hosted domains)
   - Cloudflare Radar top domains by country `IR` (optional, needs API token)
2. **classify** — fetch every homepage and score how Iranian it is
   (Persian text ratio + Iranian tokens such as ZarinPal/eNamad/phone numbers + `lang`).
3. **enrich** — ASN via local `iptoasn` database (DNS A lookup) and WHOIS
   (`whois.nic.ir` + TLD whois servers via IANA referral) for registrant country.
4. **cdn** — detect CDN provider for every domain using three signals:
   CNAME chains (`dnspython`), HTTP header fingerprints (CF-RAY, AkamaiGHost,
   X-Served-By/Varnish, …) and IP ASN. Output is grouped by CDN with a
   confidence level (`high` = CNAME or header evidence, `low` = ASN only).
5. **export** — deduplicated CSV datasets (`all_domains.csv`, `iranian_domains.csv`,
   `non_ir_iranian.csv`, `summary.json`).
6. **report** — stats and top-scored domains.

## GitHub Actions

`.github/workflows/pipeline.yml` runs the whole pipeline on a weekly schedule or
manually (`workflow_dispatch`) with configurable inputs (sources, page limits,
classification/WHOIS limits). The runner commits `data/processed/` back to the
repository and uploads artifacts. Raw collector caches and the SQLite database are
cached between runs for incremental progress.

Optional secret: `RADAR_API_TOKEN` (free Cloudflare Radar API token).

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt
export PYTHONPATH=src         # optional, scripts add src/ automatically
```

Optional Cloudflare Radar token:

```bash
export RADAR_API_TOKEN=...
```

## Usage

```bash
# 1) seed collection (all sources)
python -m scripts.collect

# subset of sources
python -m scripts.collect --sources tranco,lists

# 2) classification (homepage fetch + scoring)
python -m scripts.classify --limit 5000

# 3) enrichment (ASN + WHOIS)
python -m scripts.enrich --whois-limit 500

# 4) CDN detection (grouped output files)
python -m scripts.cdn

# 5) export deduplicated datasets
python -m scripts.export

# 6) stats
python -m scripts.report
```

Outputs:

- `data/processed/seed_domains.csv` — domain list with sources
- `data/processed/verdicts.csv` — per-domain verdicts
- `data/processed/domains_by_cdn.csv` — all domains sorted by CDN (cdn, confidence, signals)
- `data/processed/cdn/<provider>.txt` — high-confidence domains per CDN (e.g. `cloudflare.txt`, `arvancloud.txt`)
- `data/processed/cdn_summary.json` — per-CDN counts and confidence breakdown
- `data/processed/all_domains.csv` — full deduplicated dataset
- `data/processed/iranian_domains.csv` — verdict=iranian, sorted by score
- `data/processed/non_ir_iranian.csv` — non-`.ir` Iranian candidates
- `data/processed/summary.json` — export counters
- `data/irdata.sqlite` — main database (`domains`, `sources`, `fetches`, `enrichment`)

## Tests

```bash
python -m unittest discover -s tests
```

## Notes

- Robots/politeness: homepage-only fetches, bounded concurrency (50), custom bot UA.
- Verdict thresholds: `ir_score >= 0.60` Iranian, `>= 0.35` uncertain, else foreign.
- See `PLAN.md` (local, not tracked) for the full plan.
