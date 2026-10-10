from irdata.utils.domain import normalize_domain, registrable_domain
from irdata.utils.net import fetch_text, make_client

SOURCES: list[tuple[str, str]] = [
    (
        "https://raw.githubusercontent.com/bootmortis/iran-hosted-domains/main/"
        "src/data/tld_ir.txt",
        "lines",
    ),
    (
        "https://raw.githubusercontent.com/bootmortis/iran-hosted-domains/main/"
        "src/data/custom_domains.py",
        "regex",
    ),
]


def _from_lines(text: str) -> set[str]:
    domains: set[str] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or " " in line or "\t" in line:
            continue
        host = normalize_domain(line)
        if host is None:
            continue
        reg = registrable_domain(host)
        if reg:
            domains.add(reg)
    return domains


def _from_regex(text: str) -> set[str]:
    import re

    candidates = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9.-]{1,200}\.[a-zA-Z]{2,24}", text)
    domains: set[str] = set()
    for candidate in candidates:
        host = normalize_domain(candidate)
        if host is None:
            continue
        reg = registrable_domain(host)
        if reg:
            domains.add(reg)
    return domains


async def collect() -> set[str]:
    domains: set[str] = set()
    async with make_client(timeout=60.0) as client:
        for url, mode in SOURCES:
            try:
                text = await fetch_text(client, url)
            except Exception:
                continue
            if mode == "lines":
                domains |= _from_lines(text)
            else:
                domains |= _from_regex(text)
    return domains
