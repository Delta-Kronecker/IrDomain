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
from irdata.enrich import asn as asn_mod
from irdata.storage import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("dns")


async def resolve_batch(domains: list[str], asn_db) -> list[tuple[str, list[str], list[dict]]]:
    semaphore = asyncio.Semaphore(config.FETCH_CONCURRENCY)
    resolver = nameservers.make_resolver()
    results: list[tuple[str, list[str], list[dict]]] = []

    async def worker(domain: str) -> None:
        async with semaphore:
            try:
                ns_entries = await nameservers.resolve_ns_with_ips(resolver, domain)
            except Exception:
                ns_entries = []
            ns_list = [entry["ns_host"] for entry in ns_entries]
            ip_rows: list[dict] = []
            for entry in ns_entries:
                for ip in entry["ips"]:
                    record = asn_db.lookup(ip) or {}
                    ip_rows.append(
                        {
                            "ns_host": entry["ns_host"],
                            "ip": ip,
                            "asn": record.get("asn", ""),
                            "isp": record.get("name", ""),
                            "country": record.get("country", ""),
                        }
                    )
            results.append((domain, ns_list, ip_rows))

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

    ip_rows = conn.execute(
        """
        SELECT domain, ns_host, ip, asn, isp, country
        FROM ns_ips
        ORDER BY domain, ns_host, ip
        """
    ).fetchall()

    with (out / "dns_resolver_ips.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["domain", "ns_host", "ip", "isp", "country", "asn"])
        for row in ip_rows:
            writer.writerow(
                [row["domain"], row["ns_host"], row["ip"], row["isp"], row["country"], row["asn"]]
            )

    per_ip: dict[str, dict] = {}
    for row in ip_rows:
        entry = per_ip.setdefault(
            row["ip"],
            {
                "ip": row["ip"],
                "isp": row["isp"],
                "country": row["country"],
                "asn": row["asn"],
                "times_seen": 0,
                "domains": set(),
            },
        )
        entry["times_seen"] += 1
        entry["domains"].add(row["domain"])

    by_isp: dict[str, int] = {}
    by_country: dict[str, int] = {}
    for entry in per_ip.values():
        isp = entry["isp"] or "unknown"
        country = entry["country"] or "unknown"
        by_isp[isp] = by_isp.get(isp, 0) + 1
        by_country[country] = by_country.get(country, 0) + 1

    with (out / "dns_resolvers_by_ip.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ip", "isp", "country", "asn", "times_seen", "domains"])
        for entry in sorted(per_ip.values(), key=lambda e: -e["times_seen"]):
            writer.writerow(
                [
                    entry["ip"], entry["isp"], entry["country"], entry["asn"],
                    entry["times_seen"], ";".join(sorted(entry["domains"])[:10]),
                ]
            )

    summary = {
        "total_scanned": len(rows),
        "with_nameservers": with_ns,
        "unique_nameservers": len(all_ns),
        "unique_resolver_ips": len(per_ip),
        "unique_isps": len(by_isp),
        "unique_countries": len(by_country),
        "by_provider": dict(sorted(by_provider.items(), key=lambda kv: -kv[1])),
        "by_isp": dict(sorted(by_isp.items(), key=lambda kv: -kv[1])),
        "by_country": dict(sorted(by_country.items(), key=lambda kv: -kv[1])),
    }
    (out / "dns_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve DNS name servers and their IPs for all domains"
    )
    parser.add_argument("--limit", type=int, default=0, help="0 = all pending")
    parser.add_argument("--batch", type=int, default=200)
    parser.add_argument("--force", action="store_true", help="re-resolve all domains")
    args = parser.parse_args()

    conn = db.connect()
    if args.force:
        conn.execute("DELETE FROM nameservers")
        conn.execute("DELETE FROM ns_ips")
        conn.commit()
    domains = db.pending_ns(conn, limit=args.limit or None)
    log.info("NS+IP resolution for %d domains", len(domains))

    asn_db = asyncio.run(asn_mod.load())

    async def process() -> None:
        for start in range(0, len(domains), args.batch):
            batch = domains[start : start + args.batch]
            log.info("batch %d-%d", start, start + len(batch))
            results = await resolve_batch(batch, asn_db)
            for domain, ns_list, ip_rows in results:
                provider = nameservers.detect_provider(ns_list) or "unknown"
                db.record_ns(conn, domain, ns_list, provider)
                db.record_ns_ips(conn, domain, ip_rows)

    asyncio.run(process())

    summary = export_files(conn)
    log.info("dns export summary: %s", summary)
    conn.close()


if __name__ == "__main__":
    main()
