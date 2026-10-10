import argparse
import asyncio
import csv
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata import config
from irdata.collectors import commoncrawl, crtsh, lists, radar, tranco
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
    "radar": radar.collect,
}


async def run(sources: list[str], commoncrawl_kwargs: dict | None = None) -> dict[str, set[str]]:
    results: dict[str, set[str]] = {}
    for name in sources:
        collector = COLLECTORS[name]
        if name == "commoncrawl" and commoncrawl_kwargs:
            collector = lambda: commoncrawl.collect(**commoncrawl_kwargs)
        log.info("starting collector: %s", name)
        try:
            domains = await collector()
        except Exception:
            log.exception("collector failed: %s", name)
            domains = set()
        log.info("collector %s returned %d domains", name, len(domains))
        results[name] = domains
    return results


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
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    unknown = [s for s in sources if s not in COLLECTORS]
    if unknown:
        parser.error(f"unknown sources: {unknown}")

    results = asyncio.run(
        run(
            sources,
            {"index_count": args.cc_index_count, "max_pages": args.cc_max_pages},
        )
    )

    conn = db.connect()
    for source, domains in results.items():
        db.upsert_domains(conn, domains, source)

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
