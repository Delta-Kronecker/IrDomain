import asyncio

import httpx

from irdata import config
from irdata.utils.net import make_client


async def _read_limited(response: httpx.Response, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        chunks.append(chunk)
        total += len(chunk)
        if total >= limit:
            break
    return b"".join(chunks)[:limit]


async def fetch_home(
    client: httpx.AsyncClient, domain: str
) -> dict:
    last_error = ""
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}/"
        try:
            async with client.stream("GET", url) as response:
                body = await _read_limited(response, config.FETCH_MAX_BYTES)
                encoding = response.charset_encoding or "utf-8"
                try:
                    html = body.decode(encoding, errors="replace")
                except LookupError:
                    html = body.decode("utf-8", errors="replace")
                return {
                    "status": response.status_code,
                    "final_url": str(response.url),
                    "html": html,
                    "error": "",
                }
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            await asyncio.sleep(0.5)
    return {"status": None, "final_url": "", "html": "", "error": last_error}


async def fetch_many(domains: list[str]) -> dict[str, dict]:
    semaphore = asyncio.Semaphore(config.FETCH_CONCURRENCY)
    results: dict[str, dict] = {}

    async with make_client(timeout=config.FETCH_TIMEOUT) as client:

        async def worker(domain: str) -> None:
            async with semaphore:
                results[domain] = await fetch_home(client, domain)

        await asyncio.gather(*(worker(d) for d in domains))
    return results
