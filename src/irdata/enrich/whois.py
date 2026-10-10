import logging
import re
import socket

log = logging.getLogger(__name__)

IR_WHOIS_SERVER = "whois.nic.ir"
IANA_WHOIS_SERVER = "whois.iana.org"

COUNTRY_RE = re.compile(r"(?im)^(?:registrant\s+country|country)\s*:\s*([A-Z]{2})\b")
REGISTRAR_RE = re.compile(r"(?im)^registrar\s*:\s*(.+)$")
WHOIS_SERVER_RE = re.compile(r"(?im)^whois\s*:\s*(\S+)")

_tld_server_cache: dict[str, str | None] = {}


def _query_server(host: str, query: str, timeout: float = 20.0) -> str:
    with socket.create_connection((host, 43), timeout=timeout) as sock:
        sock.sendall((query + "\r\n").encode("utf-8"))
        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks).decode("utf-8", errors="replace")


def parse_whois_text(text: str) -> dict:
    out: dict = {}
    match = COUNTRY_RE.search(text)
    if match:
        out["registrant_country"] = match.group(1).upper()
    match = REGISTRAR_RE.search(text)
    if match:
        out["registrar"] = match.group(1).strip()[:200]
    return out


def tld_whois_server(tld: str) -> str | None:
    if tld in _tld_server_cache:
        return _tld_server_cache[tld]
    try:
        text = _query_server(IANA_WHOIS_SERVER, tld)
    except Exception:
        _tld_server_cache[tld] = None
        return None
    match = WHOIS_SERVER_RE.search(text)
    server = match.group(1) if match else None
    if server in ("whois.iana.org", "none", None):
        server = None
    _tld_server_cache[tld] = server
    return server


def lookup(domain: str) -> dict:
    tld = domain.rsplit(".", 1)[-1]
    if tld == "ir":
        server = IR_WHOIS_SERVER
    else:
        server = tld_whois_server(tld)
    if not server:
        return {}
    try:
        text = _query_server(server, domain)
    except Exception as exc:
        log.debug("whois failed for %s via %s: %s", domain, server, exc)
        return {}
    return parse_whois_text(text)
