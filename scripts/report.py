import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irdata.storage import db


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Print database stats")
    parser.add_argument("--top", type=int, default=30, help="top Iranian domains to show")
    args = parser.parse_args()

    conn = db.connect()
    report = db.report(conn)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    print(f"\nTop scored domains (verdict=iranian, limit {args.top}):")
    rows = conn.execute(
        """
        SELECT f.domain, f.ir_score, f.persian_ratio, f.title
        FROM fetches f
        WHERE f.verdict = 'iranian'
        ORDER BY f.ir_score DESC
        LIMIT ?
        """,
        (args.top,),
    ).fetchall()
    for row in rows:
        print(f"  {row['ir_score']:.3f}  {row['domain']:<40} {row['title'][:60]}")

    print("\nTop non-.ir Iranian domains:")
    rows = conn.execute(
        """
        SELECT f.domain, f.ir_score, f.title
        FROM fetches f
        JOIN domains d ON d.domain = f.domain
        WHERE f.verdict = 'iranian' AND d.is_tld_ir = 0
        ORDER BY f.ir_score DESC
        LIMIT ?
        """,
        (args.top,),
    ).fetchall()
    for row in rows:
        print(f"  {row['ir_score']:.3f}  {row['domain']:<40} {row['title'][:60]}")
    conn.close()


if __name__ == "__main__":
    main()
