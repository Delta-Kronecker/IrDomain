import json
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from irdata import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS domains (
  domain       TEXT PRIMARY KEY,
  is_tld_ir    INTEGER NOT NULL,
  first_seen   TEXT NOT NULL,
  last_seen    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
  domain       TEXT NOT NULL REFERENCES domains(domain),
  source       TEXT NOT NULL,
  collected_at TEXT NOT NULL,
  PRIMARY KEY (domain, source)
);

CREATE TABLE IF NOT EXISTS fetches (
  domain         TEXT NOT NULL REFERENCES domains(domain),
  fetched_at     TEXT NOT NULL,
  status         INTEGER,
  final_url      TEXT,
  title          TEXT,
  lang           TEXT,
  persian_ratio  REAL,
  token_hits     TEXT,
  ir_score       REAL,
  verdict        TEXT,
  error          TEXT,
  PRIMARY KEY (domain)
);

CREATE TABLE IF NOT EXISTS enrichment (
  domain             TEXT NOT NULL REFERENCES domains(domain),
  registrant_country TEXT,
  registrar          TEXT,
  ip                 TEXT,
  asn                TEXT,
  rank_country       REAL,
  PRIMARY KEY (domain)
);

CREATE TABLE IF NOT EXISTS cdns (
  domain       TEXT NOT NULL REFERENCES domains(domain),
  cdn          TEXT NOT NULL,
  confidence   TEXT NOT NULL,
  signals      TEXT,
  detected_at  TEXT,
  PRIMARY KEY (domain)
);

CREATE TABLE IF NOT EXISTS nameservers (
  domain       TEXT NOT NULL REFERENCES domains(domain),
  ns_list      TEXT,
  provider     TEXT,
  resolved_at  TEXT,
  PRIMARY KEY (domain)
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_domains(conn: sqlite3.Connection, domains: Iterable[str], source: str) -> int:
    ts = now_iso()
    count = 0
    for domain in domains:
        is_tld_ir = 1 if domain.endswith(".ir") else 0
        conn.execute(
            """
            INSERT INTO domains (domain, is_tld_ir, first_seen, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET last_seen = excluded.last_seen
            """,
            (domain, is_tld_ir, ts, ts),
        )
        conn.execute(
            """
            INSERT INTO sources (domain, source, collected_at)
            VALUES (?, ?, ?)
            ON CONFLICT(domain, source) DO NOTHING
            """,
            (domain, source, ts),
        )
        count += 1
    conn.commit()
    return count


def pending_domains(conn: sqlite3.Connection, limit: int | None = None) -> list[str]:
    query = """
        SELECT d.domain FROM domains d
        LEFT JOIN fetches f ON f.domain = d.domain
        WHERE f.domain IS NULL
        ORDER BY d.is_tld_ir DESC, d.domain
    """
    if limit:
        query += f" LIMIT {int(limit)}"
    return [row["domain"] for row in conn.execute(query)]


def record_fetch(conn: sqlite3.Connection, domain: str, row: dict) -> None:
    conn.execute(
        """
        INSERT INTO fetches (
          domain, fetched_at, status, final_url, title, lang,
          persian_ratio, token_hits, ir_score, verdict, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(domain) DO UPDATE SET
          fetched_at = excluded.fetched_at,
          status = excluded.status,
          final_url = excluded.final_url,
          title = excluded.title,
          lang = excluded.lang,
          persian_ratio = excluded.persian_ratio,
          token_hits = excluded.token_hits,
          ir_score = excluded.ir_score,
          verdict = excluded.verdict,
          error = excluded.error
        """,
        (
            domain,
            now_iso(),
            row.get("status"),
            row.get("final_url"),
            row.get("title"),
            row.get("lang"),
            row.get("persian_ratio"),
            row.get("token_hits"),
            row.get("ir_score"),
            row.get("verdict"),
            row.get("error"),
        ),
    )
    conn.commit()


def record_cdn(conn: sqlite3.Connection, domain: str, row: dict) -> None:
    conn.execute(
        """
        INSERT INTO cdns (domain, cdn, confidence, signals, detected_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(domain) DO UPDATE SET
          cdn = excluded.cdn,
          confidence = excluded.confidence,
          signals = excluded.signals,
          detected_at = excluded.detected_at
        """,
        (
            domain,
            row["cdn"],
            row["confidence"],
            json.dumps(row.get("signals", []), ensure_ascii=False),
            now_iso(),
        ),
    )
    conn.commit()


def pending_cdn(conn: sqlite3.Connection, limit: int | None = None) -> list[str]:
    query = """
        SELECT d.domain FROM domains d
        LEFT JOIN cdns c ON c.domain = d.domain
        WHERE c.domain IS NULL
        ORDER BY d.is_tld_ir DESC, d.domain
    """
    if limit:
        query += f" LIMIT {int(limit)}"
    return [row["domain"] for row in conn.execute(query)]


def record_ns(conn: sqlite3.Connection, domain: str, ns_list: list[str], provider: str) -> None:
    conn.execute(
        """
        INSERT INTO nameservers (domain, ns_list, provider, resolved_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(domain) DO UPDATE SET
          ns_list = excluded.ns_list,
          provider = excluded.provider,
          resolved_at = excluded.resolved_at
        """,
        (
            domain,
            json.dumps(ns_list, ensure_ascii=False),
            provider,
            now_iso(),
        ),
    )
    conn.commit()


def pending_ns(conn: sqlite3.Connection, limit: int | None = None) -> list[str]:
    query = """
        SELECT d.domain FROM domains d
        LEFT JOIN nameservers n ON n.domain = d.domain
        WHERE n.domain IS NULL
        ORDER BY d.is_tld_ir DESC, d.domain
    """
    if limit:
        query += f" LIMIT {int(limit)}"
    return [row["domain"] for row in conn.execute(query)]


def report(conn: sqlite3.Connection) -> dict:
    out: dict = {}
    out["domains_total"] = conn.execute("SELECT COUNT(*) FROM domains").fetchone()[0]
    out["domains_ir_tld"] = conn.execute(
        "SELECT COUNT(*) FROM domains WHERE is_tld_ir = 1"
    ).fetchone()[0]
    out["domains_non_ir_tld"] = out["domains_total"] - out["domains_ir_tld"]
    out["by_source"] = dict(
        conn.execute("SELECT source, COUNT(*) FROM sources GROUP BY source").fetchall()
    )
    out["by_verdict"] = dict(
        conn.execute(
            "SELECT verdict, COUNT(*) FROM fetches GROUP BY verdict"
        ).fetchall()
    )
    return out
