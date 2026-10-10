import argparse
import asyncio
import csv
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata import config
from irdata.classify import features, fetcher, scorer
from irdata.storage import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("classify")


async def classify_batch(domains: list[str]) -> list[tuple[str, dict]]:
    pages = await fetcher.fetch_many(domains)
    rows = []
    for domain, page in pages.items():
        if not page["html"] or page["status"] is None:
            row = {
                "status": None,
                "final_url": "",
                "title": "",
                "lang": "",
                "persian_ratio": None,
                "token_hits": "[]",
                "ir_score": None,
                "verdict": "dead",
                "error": page["error"],
            }
        else:
            feats = features.extract(page["html"])
            ir_score, verdict = scorer.score(feats)
            row = {
                "status": page["status"],
                "final_url": page["final_url"],
                "title": feats["title"],
                "lang": feats["lang"],
                "persian_ratio": feats["persian_ratio"],
                "token_hits": json.dumps(feats["token_hits"], ensure_ascii=False),
                "ir_score": ir_score,
                "verdict": verdict,
                "error": "",
            }
        rows.append((domain, row))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify seed domains")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--batch", type=int, default=200)
    parser.add_argument("--out", default=str(config.PROCESSED_DIR / "verdicts.csv"))
    args = parser.parse_args()

    conn = db.connect()
    domains = db.pending_domains(conn, limit=args.limit)
    log.info("classifying %d domains", len(domains))

    out_path = Path(args.out)
    new_file = not out_path.exists()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fh = out_path.open("a", newline="", encoding="utf-8")
    writer = csv.writer(fh)
    if new_file:
        writer.writerow(
            [
                "domain", "status", "final_url", "title", "lang",
                "persian_ratio", "token_hits", "ir_score", "verdict", "error",
            ]
        )

    async def process() -> None:
        for start in range(0, len(domains), args.batch):
            batch = domains[start : start + args.batch]
            log.info("batch %d-%d", start, start + len(batch))
            rows = await classify_batch(batch)
            for domain, row in rows:
                db.record_fetch(conn, domain, row)
                writer.writerow(
                    [
                        domain, row["status"], row["final_url"], row["title"],
                        row["lang"], row["persian_ratio"], row["token_hits"],
                        row["ir_score"], row["verdict"], row["error"],
                    ]
                )
            fh.flush()

    asyncio.run(process())
    fh.close()
    log.info("db report: %s", db.report(conn))
    conn.close()


if __name__ == "__main__":
    main()
