"""Import previously exported processed CSVs back into the database.

Used to recover CI pipeline results (verdicts + enrichment) when the
SQLite database itself was not persisted. Reads from data/processed/.
"""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata import config
from irdata.storage import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("import_processed")

JUNK_TITLE_PATTERNS = (
    "domain for sale",
    "domain is for sale",
    "buy this domain",
    "domain parking",
    "parked",
)


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _maybe_number(value: str | None):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _maybe_int(value: str | None):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _is_junk_title(title: str | None) -> bool:
    if not title:
        return False
    lowered = title.lower()
    return any(pattern in lowered for pattern in JUNK_TITLE_PATTERNS)


def import_verdicts(conn, path: Path) -> int:
    rows = _read_csv(path)
    count = 0
    for row in rows:
        domain = row.get("domain", "").strip()
        if not domain:
            continue
        verdict = row.get("verdict", "") or ""
        score = _maybe_number(row.get("ir_score"))
        if verdict == "iranian" and _is_junk_title(row.get("title")):
            verdict = "junk"
            score = 0.0
        db.record_fetch(
            conn,
            domain,
            {
                "status": _maybe_int(row.get("status")),
                "final_url": row.get("final_url", ""),
                "title": row.get("title", ""),
                "lang": row.get("lang", ""),
                "persian_ratio": _maybe_number(row.get("persian_ratio")),
                "token_hits": row.get("token_hits", "[]"),
                "ir_score": score,
                "verdict": verdict,
                "error": row.get("error", ""),
            },
        )
        count += 1
    return count


def import_enrichment(conn, path: Path) -> int:
    rows = _read_csv(path)
    count = 0
    for row in rows:
        domain = row.get("domain", "").strip()
        country = (row.get("registrant_country") or "").strip()
        asn = (row.get("asn") or "").strip()
        if not domain or (not country and not asn):
            continue
        conn.execute(
            """
            INSERT INTO enrichment (domain, registrant_country, asn)
            VALUES (?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET
              registrant_country = COALESCE(
                NULLIF(excluded.registrant_country, ''),
                enrichment.registrant_country
              ),
              asn = COALESCE(NULLIF(excluded.asn, ''), enrichment.asn)
            """,
            (domain, country, asn),
        )
        count += 1
        if count % 500 == 0:
            conn.commit()
    conn.commit()
    return count


def import_sources(conn, path: Path) -> int:
    rows = _read_csv(path)
    count = 0
    for row in rows:
        domain = row.get("domain", "").strip()
        sources = row.get("sources") or ""
        if not domain or not sources:
            continue
        conn.execute(
            """
            INSERT INTO domains (domain, is_tld_ir, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(domain) DO NOTHING
            """,
            (domain, _maybe_int(row.get("is_tld_ir")) or 0, db.now_iso(), db.now_iso()),
        )
        for source in sources.split(";"):
            source = source.strip()
            if not source:
                continue
            conn.execute(
                """
                INSERT INTO sources (domain, source, collected_at)
                VALUES (?, ?, ?)
                ON CONFLICT(domain, source) DO NOTHING
                """,
                (domain, source, db.now_iso()),
            )
            count += 1
    conn.commit()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir", default=str(config.PROCESSED_DIR), help="directory with CSVs"
    )
    args = parser.parse_args()
    processed = Path(args.dir)

    conn = db.connect()
    n = import_sources(conn, processed / "seed_domains.csv")
    log.info("domains/sources rows: %d", n)
    n = import_verdicts(conn, processed / "verdicts.csv")
    log.info("verdicts imported: %d", n)
    n = import_enrichment(conn, processed / "all_domains.csv")
    log.info("enrichment rows: %d", n)
    log.info("db report: %s", db.report(conn))
    conn.close()


if __name__ == "__main__":
    main()
