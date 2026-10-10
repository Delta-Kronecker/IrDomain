import csv
import io

from irdata.utils.domain import normalize_domain, registrable_domain
from irdata.utils.net import fetch_bytes, make_client

MAJESTIC_URL = "https://downloads.majestic.com/majestic_million.csv"


async def collect() -> set[str]:
    async with make_client(timeout=300.0) as client:
        blob = await fetch_bytes(client, MAJESTIC_URL)
    text = blob.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or "Domain" not in header:
        return set()
    domain_col = header.index("Domain")
    domains: set[str] = set()
    for row in reader:
        if len(row) <= domain_col:
            continue
        host = normalize_domain(row[domain_col])
        if host is None or not host.endswith(".ir"):
            continue
        reg = registrable_domain(host)
        if reg:
            domains.add(reg)
    return domains
