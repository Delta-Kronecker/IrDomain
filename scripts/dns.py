import argparse
import asyncio
import csv
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata import config
from irdata.dnsinfo import nameservers
from irdata.storage import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("dns")


async def resolve_batch(domains: list[str]) -> list[tuple[str, list[str]]]:
    semaphore = asyncio.Semaphore(config.FETCH_CONCURRENCY)
    resolver = nameservers.make_resolver()
    results: list[tuple[str, list[str]]] = []

    async def worker(domain: str) -> None:
        async with semaphore:
            try:
                ns_list = await nameservers.resolve_ns(resolver, domain)
            except Exception:
                ns_list = []
            results.append((domain, ns_list))

    await asyncio.gather(*(worker(d) for d in domains))
    return results


def export_files(conn) -> dict:
    rows = conn.execute(
        """
        SELECT n.domain, n.ns_list, n.provider, d.is_tld_ir, f.verdict
        FROM nameservers n
        JOIN domains d ON d.domain = n.domain
        LEFT JOIN fetches f ON f.domain = n.domain
        ORDER BY n.domain
        """
    ).fetchall()

    out = config.PROCESSED_DIR
    all_ns: set[str] = set()
    by_provider: dict[str, int] = {}
    with_ns = 0

    csv_path = out / "domains_nameservers.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["domain", "provider", "ns_count", "nameservers", "is_tld_ir", "verdict"]
        )
        for row in rows:
            ns_list = json.loads(row["ns_list"] or "[]")
            provider = row["provider"] or "unknown"
            if ns_list:
                with_ns += 1
                all_ns.update(ns_list)
                by_provider[provider] = by_provider.get(provider, 0) + 1
            writer.writerow(
                [
                    row["domain"],
                    provider,
                    len(ns_list),
                    ";".join(ns_list),
                    row["is_tld_ir"],
                    row["verdict"] or "",
                ]
            )

    resolvers_path = out / "dns_nameservers.txt"
    resolvers_path.write_text(
        "\n".join(sorted(all_ns)) + ("\n" if all_ns else ""), encoding="utf-8"
    )

    summary = {
        "total_scanned": len(rows),
        "with_nameservers": with_ns,
        "unique_nameservers": len(all_ns),
        "by_provider": dict(sorted(by_provider.items(), key=lambda kv: -kv[1])),
    }
    (out / "dns_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve DNS name servers for all domains"
    )
    parser.add_argument("--limit", type=int, default=0, help="0 = all pending")
    parser.add_argument("--batch", type=int, default=200)
    parser.add_argument("--force", action="store_true", help="re-resolve all domains")
    args = parser.parse_args()

    conn = db.connect()
    if args.force:
        conn.execute("DELETE FROM nameservers")
        conn.commit()
    domains = db.pending_ns(conn, limit=args.limit or None)
    log.info("NS resolution for %d domains", len(domains))

    async def process() -> None:
        for start in range(0, len(domains), args.batch):
            batch = domains[start : start + args.batch]
            log.info("batch %d-%d", start, start + len(batch))
            results = await resolve_batch(batch)
            for domain, ns_list in results:
                provider = nameservers.detect_provider(ns_list) or "unknown"
                db.record_ns(conn, domain, ns_list, provider)

    asyncio.run(process())

    summary = export_files(conn)
    log.info("dns export summary: %s", summary)
    conn.close()


if __name__ == "__main__":
    main()
