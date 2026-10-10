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
log = logging.getLogger("export")

EXPORT_QUERY = """
SELECT d.domain,
       d.is_tld_ir,
       GROUP_CONCAT(s.source, ';') AS sources,
       f.verdict,
       f.ir_score,
       f.persian_ratio,
       f.title,
       e.registrant_country,
       e.asn
FROM domains d
LEFT JOIN sources s ON s.domain = d.domain
LEFT JOIN fetches f ON f.domain = d.domain
LEFT JOIN enrichment e ON e.domain = d.domain
GROUP BY d.domain
ORDER BY d.domain
"""


def write_csv(path: Path, rows: list, header: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export deduplicated datasets")
    args = parser.parse_args()

    conn = db.connect()
    rows = conn.execute(EXPORT_QUERY).fetchall()
    domains = [row["domain"] for row in rows]
    if len(domains) != len(set(domains)):
        raise SystemExit("duplicate domains detected in export query")

    header = [
        "domain", "is_tld_ir", "sources", "verdict", "ir_score",
        "persian_ratio", "title", "registrant_country", "asn",
    ]
    table = [list(row) for row in rows]

    out = config.PROCESSED_DIR
    write_csv(out / "all_domains.csv", table, header)

    iranian = [r for r in table if r[3] == "iranian"]
    iranian.sort(key=lambda r: -(r[4] or 0))
    write_csv(out / "iranian_domains.csv", iranian, header)

    non_ir = [r for r in table if r[1] == 0 and r[3] in ("iranian", "uncertain")]
    non_ir.sort(key=lambda r: -(r[4] or 0))
    write_csv(out / "non_ir_iranian.csv", non_ir, header)

    summary = {
        "total": len(table),
        "iranian": len(iranian),
        "non_ir_iranian": len(non_ir),
        "with_asn": sum(1 for r in table if r[8]),
        "with_country": sum(1 for r in table if r[7]),
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    sub_rows = conn.execute(
        "SELECT host, parent FROM subdomains ORDER BY host"
    ).fetchall()
    with (out / "subdomains.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["host", "parent_domain"])
        for row in sub_rows:
            writer.writerow([row["host"], row["parent"]])
    summary["subdomains"] = len(sub_rows)
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    log.info("export summary: %s", summary)
    conn.close()


if __name__ == "__main__":
    main()
