# IrDomain

Database of Iranian websites, including both `.ir` domains and non-`.ir` domains
run by Iranian services (e.g. `aparat.com`).

## Pipeline

1. **collect** — build a seed domain list from public sources:
   - Certificate Transparency (`crt.sh`, query `%.ir`)
   - Common Crawl index (`*.ir`, latest crawls)
   - Tranco top list (`.ir` filter)
   - Curated GitHub domain lists (Iran-hosted domains)
   - Cloudflare Radar top domains by country `IR` (optional, needs API token)
2. **classify** — fetch every homepage and score how Iranian it is
   (Persian text ratio + Iranian tokens such as ZarinPal/eNamad/phone numbers + `lang`).
3. **report** — stats and top-scored domains.

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

# 3) stats
python -m scripts.report
```

Outputs:

- `data/processed/seed_domains.csv` — domain list with sources
- `data/processed/verdicts.csv` — per-domain verdicts
- `data/irdata.sqlite` — main database (`domains`, `sources`, `fetches`)

## Tests

```bash
python -m unittest discover -s tests
```

## Notes

- Robots/politeness: homepage-only fetches, bounded concurrency (50), custom bot UA.
- Verdict thresholds: `ir_score >= 0.60` Iranian, `>= 0.35` uncertain, else foreign.
- See `PLAN.md` (local, not tracked) for the full plan.
