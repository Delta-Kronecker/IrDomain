import asyncio
import random

import httpx

from irdata import config


def make_client(
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> httpx.AsyncClient:
    merged = {"User-Agent": config.USER_AGENT}
    if headers:
        merged.update(headers)
    return httpx.AsyncClient(
        headers=merged,
        timeout=timeout or config.HTTP_TIMEOUT,
        follow_redirects=True,
    )


async def fetch_text(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    retries: int = config.HTTP_RETRIES,
    timeout: float | None = None,
) -> str:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = await client.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                await asyncio.sleep((2**attempt) + random.random())
    raise last_error


async def fetch_bytes(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    retries: int = config.HTTP_RETRIES,
    timeout: float | None = None,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = await client.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.content
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                await asyncio.sleep((2**attempt) + random.random())
    raise last_error


def parse_json_line_block(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        import json

        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows
