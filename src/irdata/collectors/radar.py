import json

from irdata import config
from irdata.utils.domain import normalize_domain, registrable_domain
from irdata.utils.net import fetch_text, make_client

RADAR_TOP_URL = "https://api.cloudflare.com/client/v4/radar/ranking/top"


def _find_domains(node, out: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("domain", "name") and isinstance(value, str) and "." in value:
                host = normalize_domain(value)
                if host:
                    reg = registrable_domain(host)
                    if reg:
                        out.add(reg)
            else:
                _find_domains(value, out)
    elif isinstance(node, list):
        for item in node:
            _find_domains(item, out)


async def collect(limit: int = 1000) -> set[str]:
    if not config.RADAR_API_TOKEN:
        return set()
    async with make_client(
        headers={"Authorization": f"Bearer {config.RADAR_API_TOKEN}"},
        timeout=60.0,
    ) as client:
        text = await fetch_text(
            client,
            RADAR_TOP_URL,
            params={"location": "IR", "limit": str(limit)},
            retries=1,
        )
    payload = json.loads(text)
    if not payload.get("success", False):
        return set()
    domains: set[str] = set()
    _find_domains(payload.get("result"), domains)
    return domains
