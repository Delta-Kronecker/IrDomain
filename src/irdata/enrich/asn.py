import gzip
import ipaddress
import logging
import socket
from bisect import bisect_left

from irdata import config
from irdata.utils.net import fetch_bytes, make_client

log = logging.getLogger(__name__)

IP2ASN_URL = "https://iptoasn.com/data/ip2asn-v4.tsv.gz"
CACHE_PATH = config.RAW_DIR / "ip2asn-v4.tsv.gz"


class AsnDB:
    def __init__(
        self,
        starts: list[int],
        ends: list[int],
        asns: list[str],
        countries: list[str],
        names: list[str] | None = None,
    ):
        self.starts = starts
        self.ends = ends
        self.asns = asns
        self.countries = countries
        self.names = names if names is not None else [""] * len(starts)

    @classmethod
    def from_tsv_text(cls, text: str) -> "AsnDB":
        starts: list[int] = []
        ends: list[int] = []
        asns: list[str] = []
        countries: list[str] = []
        names: list[str] = []
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            try:
                start = int(ipaddress.ip_address(parts[0]))
                end = int(ipaddress.ip_address(parts[1]))
            except ValueError:
                continue
            asn = parts[2]
            if asn == "0":
                continue
            starts.append(start)
            ends.append(end)
            asns.append(asn)
            countries.append(parts[3])
            names.append(parts[4].strip() if len(parts) > 4 else "")
        return cls(starts, ends, asns, countries, names)

    def lookup(self, ip: str) -> dict | None:
        try:
            value = int(ipaddress.ip_address(ip))
        except ValueError:
            return None
        idx = bisect_left(self.ends, value)
        if idx >= len(self.ends) or self.starts[idx] > value:
            return None
        return {
            "ip": ip,
            "asn": self.asns[idx],
            "country": self.countries[idx],
            "name": self.names[idx],
        }


async def load() -> AsnDB:
    if CACHE_PATH.exists():
        blob = CACHE_PATH.read_bytes()
    else:
        async with make_client(timeout=300.0) as client:
            blob = await fetch_bytes(client, IP2ASN_URL)
        CACHE_PATH.write_bytes(blob)
    text = gzip.decompress(blob).decode("utf-8", errors="replace")
    db = AsnDB.from_tsv_text(text)
    log.info("asn db loaded: %d ranges", len(db.starts))
    return db


def resolve_ipv4(domain: str, timeout: float = 5.0) -> str | None:
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        infos = socket.getaddrinfo(domain, 80, family=socket.AF_INET)
    except Exception:
        return None
    finally:
        socket.setdefaulttimeout(old)
    if not infos:
        return None
    return infos[0][4][0]
