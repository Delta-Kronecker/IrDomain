import argparse
import asyncio
import csv
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata import config
from irdata.cdn import detect, resolve
from irdata.enrich import asn as asn_mod
from irdata.storage import db
from irdata.utils.net import make_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("cdn")


async def detect_batch(domains: list[str], asn_db) -> list[tuple[str, dict]]:
    semaphore = asyncio.Semaphore(config.FETCH_CONCURRENCY)
    results: list[tuple[str, dict]] = []

    async with make_client(timeout=config.FETCH_TIMEOUT) as client:

        async def worker(domain: str) -> None:
            async with semaphore:
                cnames, headers = await resolve.gather_signals(client, domain)
                ip = asn_mod.resolve_ipv4(domain)
                record = asn_db.lookup(ip) if ip else None
                row = detect.detect(
                    cnames, headers, record["asn"] if record else None
                )
                results.append((domain, row))

        await asyncio.gather(*(worker(d) for d in domains))
    return results


def export_files(conn) -> dict:
    rows = conn.execute(
        """
        SELECT c.domain, c.cdn, c.confidence, c.signals,
               d.is_tld_ir, f.verdict
        FROM cdns c
        JOIN domains d ON d.domain = c.domain
        LEFT JOIN fetches f ON f.domain = c.domain
        ORDER BY c.cdn, c.confidence DESC, c.domain
        """
    ).fetchall()

    out = config.PROCESSED_DIR
    csv_path = out / "domains_by_cdn.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["cdn", "confidence", "domain", "is_tld_ir", "verdict", "signals"]
        )
        for row in rows:
            writer.writerow(
                [
                    row["cdn"], row["confidence"], row["domain"],
                    row["is_tld_ir"], row["verdict"] or "", row["signals"],
                ]
            )

    cdn_dir = out / "cdn"
    cdn_dir.mkdir(parents=True, exist_ok=True)
    per_cdn: dict[str, dict] = {}
    grouped: dict[str, list[str]] = {}
    for row in rows:
        stats = per_cdn.setdefault(
            row["cdn"], {"total": 0, "high": 0, "low": 0, "none": 0}
        )
        stats["total"] += 1
        conf = row["confidence"]
        stats[conf if conf in ("high", "low") else "none"] += 1
        if row["confidence"] == "high":
            grouped.setdefault(row["cdn"], []).append(row["domain"])

    for old in cdn_dir.glob("*.txt"):
        old.unlink()
    for cdn_name, domains in grouped.items():
        (cdn_dir / f"{cdn_name}.txt").write_text(
            "\n".join(sorted(domains)) + "\n", encoding="utf-8"
        )

    summary = {
        "total_scanned": len(rows),
        "with_cdn": sum(1 for r in rows if r["cdn"] != "none"),
        "high_confidence": sum(1 for r in rows if r["confidence"] == "high"),
        "by_cdn": dict(sorted(per_cdn.items(), key=lambda kv: -kv[1]["total"])),
    }
    (out / "cdn_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect CDNs for all domains")
    parser.add_argument("--limit", type=int, default=0, help="0 = all pending")
    parser.add_argument("--batch", type=int, default=200)
    parser.add_argument("--force", action="store_true", help="re-detect all domains")
    args = parser.parse_args()

    conn = db.connect()
    if args.force:
        conn.execute("DELETE FROM cdns")
        conn.commit()
        domains = db.pending_cdn(conn, limit=args.limit or None)
    else:
        domains = db.pending_cdn(conn, limit=args.limit or None)
    log.info("cdn detection for %d domains", len(domains))

    asn_db = asyncio.run(asn_mod.load())

    async def process() -> None:
        for start in range(0, len(domains), args.batch):
            batch = domains[start : start + args.batch]
            log.info("batch %d-%d", start, start + len(batch))
            rows = await detect_batch(batch, asn_db)
            for domain, row in rows:
                db.record_cdn(conn, domain, row)

    asyncio.run(process())

    summary = export_files(conn)
    log.info("cdn export summary: %s", summary)
    conn.close()


if __name__ == "__main__":
    main()
