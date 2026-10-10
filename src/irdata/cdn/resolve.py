import asyncio

import dns.asyncresolver
import dns.resolver
import httpx

from irdata import config

MAX_CHAIN = 10


async def resolve_cname_chain(
    resolver: dns.asyncresolver.Resolver, domain: str
) -> list[str]:
    chain: list[str] = []
    current = domain
    for _ in range(MAX_CHAIN):
        try:
            answer = await resolver.resolve(current, "CNAME")
        except (
            dns.resolver.NoAnswer,
            dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers,
            dns.exception.Timeout,
        ):
            break
        if not answer:
            break
        target = str(answer[0].target).rstrip(".")
        chain.append(target)
        current = target
    return chain


async def collect_cnames(domain: str) -> list[str]:
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = 5.0
    chains = await asyncio.gather(
        resolve_cname_chain(resolver, domain),
        resolve_cname_chain(resolver, f"www.{domain}"),
        return_exceptions=True,
    )
    out: list[str] = []
    for chain in chains:
        if isinstance(chain, list):
            out.extend(chain)
    seen: set[str] = set()
    deduped = []
    for item in out:
        key = item.lower().rstrip(".")
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


async def fetch_headers(client: httpx.AsyncClient, domain: str) -> dict:
    for scheme in ("https", "http"):
        try:
            async with client.stream("GET", f"{scheme}://{domain}/") as response:
                return dict(response.headers)
        except Exception:
            continue
    return {}


async def gather_signals(
    client: httpx.AsyncClient, domain: str
) -> tuple[list[str], dict]:
    cnames, headers = await asyncio.gather(
        collect_cnames(domain),
        fetch_headers(client, domain),
        return_exceptions=True,
    )
    if isinstance(cnames, Exception):
        cnames = []
    if isinstance(headers, Exception):
        headers = {}
    return list(cnames), dict(headers)
