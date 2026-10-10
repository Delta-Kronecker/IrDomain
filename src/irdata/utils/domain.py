import re
from urllib.parse import urlsplit

from irdata import config

LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
TLD_RE = re.compile(r"^(?:[a-z]{2,24}|xn--[a-z0-9-]{2,59})$")


def normalize_domain(value: str) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    if not v:
        return None
    if "://" in v:
        parts = urlsplit(v)
        v = parts.netloc or ""
    v = v.split("/")[0].split("?")[0].split("#")[0]
    if "@" in v:
        v = v.rsplit("@", 1)[1]
    if ":" in v:
        v = v.split(":", 1)[0]
    v = v.strip(".").lstrip("*.")
    if not v or len(v) > 253:
        return None
    labels = v.split(".")
    if len(labels) < 2:
        return None
    if not all(LABEL_RE.match(label) for label in labels):
        return None
    if not TLD_RE.match(labels[-1]):
        return None
    return v


def registrable_domain(domain: str) -> str | None:
    labels = domain.split(".")
    if len(labels) < 2:
        return None
    if labels[-1] == "ir" and len(labels) >= 3 and labels[-2] in config.IR_SECOND_LEVEL:
        return ".".join(labels[-3:])
    if len(labels) >= 2:
        return ".".join(labels[-2:])
    return None


def is_ir_tld(domain: str) -> bool:
    return domain.endswith(".ir")


def domain_from_url(url: str) -> str | None:
    host = urlsplit(url).hostname
    if not host:
        return None
    domain = normalize_domain(host)
    if domain is None:
        return None
    return registrable_domain(domain)
