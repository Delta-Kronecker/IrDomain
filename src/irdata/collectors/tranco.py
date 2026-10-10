import io
import zipfile

from irdata.utils.domain import normalize_domain, registrable_domain
from irdata.utils.net import fetch_bytes, make_client

TRANCO_URL = "https://tranco-list.eu/top-1m.csv.zip"


async def collect() -> set[str]:
    async with make_client(timeout=120.0) as client:
        blob = await fetch_bytes(client, TRANCO_URL)
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        name = zf.namelist()[0]
        content = zf.read(name).decode("utf-8", errors="replace")
    domains: set[str] = set()
    for line in content.splitlines():
        parts = line.strip().split(",")
        if len(parts) != 2:
            continue
        host = normalize_domain(parts[1])
        if host is None:
            continue
        if not host.endswith(".ir"):
            continue
        reg = registrable_domain(host)
        if reg:
            domains.add(reg)
    return domains
