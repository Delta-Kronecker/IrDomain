import argparse
import asyncio
import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata import config
from irdata.collectors import commoncrawl, crtsh, lists, majestic, radar, tranco
from irdata.storage import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("collect")

COLLECTORS = {
    "crtsh": crtsh.collect,
    "commoncrawl": commoncrawl.collect,
    "tranco": tranco.collect,
    "lists": lists.collect,
    "majestic": majestic.collect,
    "radar": radar.collect,
}


async def run(
    sources: list[str],
    commoncrawl_kwargs: dict | None = None,
    crtsh_seeds: list[str] | None = None,
    crtsh_limit: int = 500,
) -> tuple[dict[str, set[str]], set[str]]:
    results: dict[str, set[str]] = {}
    subdomain_hosts: set[str] = set()
    for name in sources:
        if name == "crtsh":
            continue
        log.info("starting collector: %s", name)
        try:
            if name == "commoncrawl" and commoncrawl_kwargs:
                domains = await commoncrawl.collect(**commoncrawl_kwargs)
            else:
                domains = await COLLECTORS[name]()
        except Exception:
            log.exception("collector failed: %s", name)
            domains = set()
        log.info("collector %s returned %d domains", name, len(domains))
        results[name] = domains
    if "crtsh" in sources:
        seeds = crtsh.merge_seeds(crtsh_seeds or [], results)
        log.info("starting collector: crtsh (%d seeds)", len(seeds))
        try:
            domains, hosts = await crtsh.collect(seeds, limit=crtsh_limit)
            subdomain_hosts |= hosts
        except Exception:
            log.exception("collector failed: crtsh")
            domains = set()
        log.info("collector crtsh returned %d domains", len(domains))
        results["crtsh"] = domains
    return results, subdomain_hosts


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect seed domains")
    parser.add_argument(
        "--sources",
        default=",".join(COLLECTORS),
        help="comma separated list: " + ",".join(COLLECTORS),
    )
    parser.add_argument("--out", default=str(config.PROCESSED_DIR / "seed_domains.csv"))
    parser.add_argument("--cc-index-count", type=int, default=2)
    parser.add_argument("--cc-max-pages", type=int, default=40)
    parser.add_argument("--crtsh-limit", type=int, default=500)
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    unknown = [s for s in sources if s not in COLLECTORS]
    if unknown:
        parser.error(f"unknown sources: {unknown}")

    conn = db.connect()
    crtsh_seeds = (
        db.expand_seeds(conn, args.crtsh_limit) if "crtsh" in sources else []
    )

    results, subdomain_hosts = asyncio.run(
        run(
            sources,
            {"index_count": args.cc_index_count, "max_pages": args.cc_max_pages},
            crtsh_seeds=crtsh_seeds,
            crtsh_limit=args.crtsh_limit,
        )
    )

    for source, domains in results.items():
        db.upsert_domains(conn, domains, source)
    if subdomain_hosts:
        inserted = db.insert_subdomains(conn, subdomain_hosts)
        log.info("subdomains table: +%d rows", inserted)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["domain", "is_tld_ir", "sources"])
        rows = conn.execute(
            """
            SELECT d.domain, d.is_tld_ir,
                   GROUP_CONCAT(s.source, ';') AS sources
            FROM domains d JOIN sources s ON s.domain = d.domain
            GROUP BY d.domain ORDER BY d.domain
            """
        ).fetchall()
        for row in rows:
            writer.writerow([row["domain"], row["is_tld_ir"], row["sources"]])

    log.info("wrote %d domains to %s", len(rows), out_path)
    log.info("db report: %s", db.report(conn))
    conn.close()


if __name__ == "__main__":
    main()
