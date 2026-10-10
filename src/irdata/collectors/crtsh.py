import asyncio
import json
import logging
from pathlib import Path

from irdata import config
from irdata.utils.domain import normalize_domain, registrable_domain
from irdata.utils.net import fetch_text, make_client

log = logging.getLogger(__name__)

URL = "https://crt.sh/"
PREFIXES = [f"{c}%" for c in "abcdefghijklmnopqrstuvwxyz0123456789"] + ["*%"]
CHUNK_DELAY = 15.0


def _cache_path(index: int, prefix: str) -> Path:
    slug = prefix.replace("%", "").replace("*", "star") or "empty"
    return config.RAW_DIR / f"crtsh_{index:02d}_{slug}.domains.txt"


def _parse_rows(rows) -> set[str]:
    domains: set[str] = set()
    for row in rows:
        for name in str(row.get("name_value", "")).splitlines():
            host = normalize_domain(name)
            if host is None:
                continue
            reg = registrable_domain(host)
            if reg:
                domains.add(reg)
    return domains


async def _fetch_chunk(client, query: str) -> str | None:
    for attempt in range(5):
        try:
            return await fetch_text(
                client,
                URL,
                params={"q": query, "output": "json"},
                retries=1,
                timeout=300.0,
            )
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 429:
                wait = 120.0 * (attempt + 1)
            elif status in (500, 502, 503, 504):
                wait = 60.0
            else:
                wait = 20.0
            log.warning("crt.sh chunk %s failed (status=%s), wait %.0fs", query, status, wait)
            await asyncio.sleep(wait)
    return None


async def collect() -> set[str]:
    domains: set[str] = set()
    async with make_client(
        headers={"User-Agent": config.BROWSER_USER_AGENT},
        timeout=300.0,
    ) as client:
        for index, prefix in enumerate(PREFIXES):
            cache = _cache_path(index, prefix)
            if cache.exists():
                domains.update(
                    line.strip()
                    for line in cache.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
                continue
            text = await _fetch_chunk(client, prefix + ".ir")
            if text is None:
                log.warning("giving up chunk %s", prefix)
                continue
            try:
                rows = json.loads(text)
            except json.JSONDecodeError:
                log.warning("chunk %s returned non-JSON (%d bytes)", prefix, len(text))
                await asyncio.sleep(60.0)
                continue
            chunk_domains = _parse_rows(rows)
            cache.write_text(
                "\n".join(sorted(chunk_domains)) + ("\n" if chunk_domains else ""),
                encoding="utf-8",
            )
            domains.update(chunk_domains)
            log.info(
                "chunk %s: %d domains (total %d)", prefix, len(chunk_domains), len(domains)
            )
            await asyncio.sleep(CHUNK_DELAY)
    return domains
