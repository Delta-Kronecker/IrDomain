import json
import logging
import math
import re

from irdata.utils.domain import domain_from_url
from irdata.utils.net import fetch_text, make_client

log = logging.getLogger(__name__)

COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"
INVALID_PAGE_RE = re.compile(r"Last Page is (\d+)")


def _page_plan(total: int | None, max_pages: int) -> list[int]:
    if not total:
        return list(range(max_pages))
    if total <= max_pages:
        return list(range(total))
    stride = math.ceil(total / max_pages)
    return list(range(0, total, stride))[:max_pages]


async def _total_pages(client, base: str) -> int | None:
    try:
        text = await fetch_text(
            client,
            base,
            params={"url": "*.ir", "output": "json", "page": "999999"},
            retries=1,
        )
        match = INVALID_PAGE_RE.search(text)
        if match:
            return int(match.group(1)) + 1
    except Exception:
        pass
    return None


async def _collect_index(client, index_id: str, max_pages: int) -> set[str]:
    base = f"https://index.commoncrawl.org/{index_id}-index"
    domains: set[str] = set()
    total = await _total_pages(client, base)
    pages = _page_plan(total, max_pages)
    log.info("%s: total_pages=%s plan=%d pages", index_id, total, len(pages))
    failure_streak = 0
    empty_streak = 0
    for page in pages:
        try:
            text = await fetch_text(
                client,
                base,
                params={"url": "*.ir", "output": "json", "page": str(page)},
            )
            failure_streak = 0
        except Exception:
            failure_streak += 1
            if failure_streak >= 4:
                log.warning("%s: aborting after %d failures", index_id, failure_streak)
                break
            continue
        if not text.strip():
            empty_streak += 1
            if empty_streak >= 2:
                break
            continue
        empty_streak = 0
        added = 0
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            domain = domain_from_url(row.get("url", ""))
            if domain:
                domains.add(domain)
                added += 1
        log.info("%s page %d: +%d (total %d)", index_id, page, added, len(domains))
    return domains


async def collect(index_count: int = 2, max_pages: int = 40) -> set[str]:
    async with make_client(timeout=120.0) as client:
        colls = json.loads(await fetch_text(client, COLLINFO_URL))
        index_ids = [c["id"] for c in colls[:index_count]]
        domains: set[str] = set()
        for index_id in index_ids:
            try:
                domains |= await _collect_index(client, index_id, max_pages)
            except Exception:
                log.exception("index failed: %s", index_id)
    return domains
