import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata import config
from irdata.enrich import asn, whois
from irdata.storage import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("enrich")

DNS_SLEEP = 0.05


def enrich_asn(conn, asn_db, limit: int | None) -> int:
    if limit:
        rows = conn.execute(
            """
            SELECT d.domain FROM domains d
            LEFT JOIN enrichment e ON e.domain = d.domain
            WHERE e.ip IS NULL
            ORDER BY d.is_tld_ir DESC, d.domain
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT d.domain FROM domains d
            LEFT JOIN enrichment e ON e.domain = d.domain
            WHERE e.ip IS NULL
            ORDER BY d.is_tld_ir DESC, d.domain
            """
        ).fetchall()
    count = 0
    for row in rows:
        domain = row["domain"]
        ip = asn.resolve_ipv4(domain)
        if ip is None:
            ip_value = ""
            record = {}
        else:
            ip_value = ip
            record = asn_db.lookup(ip) or {}
        conn.execute(
            """
            INSERT INTO enrichment (domain, ip, asn, registrant_country)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET
              ip = excluded.ip,
              asn = excluded.asn
            """,
            (domain, ip_value, record.get("asn", ""), record.get("country", "")),
        )
        count += 1
        if count % 100 == 0:
            conn.commit()
            log.info("asn progress: %d/%d", count, len(rows))
        time.sleep(DNS_SLEEP)
    conn.commit()
    return count


def enrich_whois(conn, limit: int, sleep_seconds: float) -> int:
    rows = conn.execute(
        """
        SELECT d.domain FROM domains d
        LEFT JOIN enrichment e ON e.domain = d.domain
        WHERE e.registrant_country IS NULL OR e.registrant_country = ''
        ORDER BY d.is_tld_ir DESC, d.domain
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    count = 0
    for row in rows:
        domain = row["domain"]
        info = whois.lookup(domain)
        conn.execute(
            """
            INSERT INTO enrichment (domain, registrant_country, registrar)
            VALUES (?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET
              registrant_country = COALESCE(
                NULLIF(excluded.registrant_country, ''),
                enrichment.registrant_country
              ),
              registrar = COALESCE(
                NULLIF(excluded.registrar, ''),
                enrichment.registrar
              )
            """,
            (domain, info.get("registrant_country", ""), info.get("registrar", "")),
        )
        count += 1
        if count % 25 == 0:
            conn.commit()
            log.info("whois progress: %d/%d", count, len(rows))
        time.sleep(sleep_seconds)
    conn.commit()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich domains with ASN and WHOIS")
    parser.add_argument("--whois-limit", type=int, default=500)
    parser.add_argument("--dns-limit", type=int, default=0, help="0 = all domains")
    parser.add_argument("--whois-sleep", type=float, default=1.0)
    args = parser.parse_args()

    conn = db.connect()
    asn_db = asyncio.run(asn.load())

    log.info("starting ASN enrichment (limit=%s)", args.dns_limit or "all")
    asn_count = enrich_asn(conn, asn_db, args.dns_limit or None)
    log.info("asn enriched: %d", asn_count)

    if args.whois_limit > 0:
        log.info("starting WHOIS enrichment (limit=%d)", args.whois_limit)
        whois_count = enrich_whois(conn, args.whois_limit, args.whois_sleep)
        log.info("whois enriched: %d", whois_count)

    stats = conn.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN asn != '' THEN 1 ELSE 0 END) AS with_asn,
               SUM(CASE WHEN registrant_country != '' THEN 1 ELSE 0 END) AS with_country,
               SUM(CASE WHEN registrant_country = 'IR' THEN 1 ELSE 0 END) AS country_ir
        FROM enrichment
        """
    ).fetchone()
    log.info("enrichment stats: %s", dict(stats))
    conn.close()


if __name__ == "__main__":
    main()
