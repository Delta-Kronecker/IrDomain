import asyncio
import json
import logging
from pathlib import Path

from irdata import config
from irdata.utils.domain import normalize_domain, registrable_domain
from irdata.utils.net import fetch_text, make_client

log = logging.getLogger(__name__)

URL = "https://crt.sh/"
EXPAND_DIR = config.RAW_DIR / "crtsh_expand"
SUBDOMAINS_OUT = config.RAW_DIR / "crtsh_subdomains.txt"
DELAY_BETWEEN = 2.0


def _cache_path(domain: str) -> Path:
    return EXPAND_DIR / f"{domain}.json"


async def _fetch_subdomains(client, domain: str) -> list[str] | None:
    for attempt in range(5):
        try:
            text = await fetch_text(
                client,
                URL,
                params={
                    "q": f"%.{domain}",
                    "output": "json",
                    "exclude": "expired",
                },
                retries=1,
                timeout=120.0,
            )
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 429:
                wait = 120.0 * (attempt + 1)
            else:
                wait = 60.0
            log.warning("crt.sh %s failed (status=%s), wait %.0fs", domain, status, wait)
            await asyncio.sleep(wait)
            continue
        try:
            rows = json.loads(text)
        except json.JSONDecodeError:
            log.warning("crt.sh %s returned non-JSON (%d bytes)", domain, len(text))
            await asyncio.sleep(30.0)
            continue
        hosts: set[str] = set()
        for row in rows:
            for name in str(row.get("name_value", "")).splitlines():
                host = normalize_domain(name)
                if host:
                    hosts.add(host)
        return sorted(hosts)
    return None


def merge_seeds(db_seeds: list[str], results: dict[str, set[str]]) -> list[str]:
    seeds = list(db_seeds)
    seen = set(seeds)
    for domains in results.values():
        for domain in sorted(domains):
            if domain not in seen:
                seeds.append(domain)
                seen.add(domain)
    return seeds


async def collect(
    seed_domains: list[str], limit: int = 500
) -> tuple[set[str], set[str]]:
    EXPAND_DIR.mkdir(parents=True, exist_ok=True)
    registrable: set[str] = set()
    all_hosts: set[str] = set()
    if not seed_domains:
        return registrable, all_hosts
    async with make_client(
        headers={"User-Agent": config.BROWSER_USER_AGENT},
        timeout=120.0,
    ) as client:
        done = 0
        for domain in seed_domains:
            if done >= limit:
                break
            cache = _cache_path(domain)
            if cache.exists():
                try:
                    hosts = json.loads(cache.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    hosts = None
                    cache.unlink(missing_ok=True)
                if hosts is None:
                    hosts = await _fetch_subdomains(client, domain)
                    if hosts is None:
                        continue
                    cache.write_text(json.dumps(hosts), encoding="utf-8")
                    await asyncio.sleep(DELAY_BETWEEN)
            else:
                hosts = await _fetch_subdomains(client, domain)
                if hosts is None:
                    continue
                cache.write_text(json.dumps(hosts), encoding="utf-8")
                await asyncio.sleep(DELAY_BETWEEN)
            done += 1
            for host in hosts:
                all_hosts.add(host)
                reg = registrable_domain(host)
                if reg:
                    registrable.add(reg)
            if done % 25 == 0:
                log.info(
                    "crt.sh expand: %d/%d domains, %d hosts",
                    done, limit, len(all_hosts),
                )
    SUBDOMAINS_OUT.write_text(
        "\n".join(sorted(all_hosts)) + ("\n" if all_hosts else ""),
        encoding="utf-8",
    )
    log.info(
        "crt.sh expand done: %d domains, %d hosts", done, len(all_hosts)
    )
    return registrable, all_hosts
