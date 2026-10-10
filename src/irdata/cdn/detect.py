import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CdnRule:
    name: str
    cname_suffixes: tuple[str, ...] = ()
    header_patterns: tuple[str, ...] = ()
    asns: tuple[str, ...] = ()


RULES: tuple[CdnRule, ...] = (
    CdnRule(
        "cloudflare",
        cname_suffixes=("cdn.cloudflare.net", "cloudflare.net"),
        header_patterns=(r"\bcf-ray\s*:", r"\bcf-cache-status\s*:"),
        asns=("13335",),
    ),
    CdnRule(
        "cloudfront",
        cname_suffixes=("cloudfront.net",),
        header_patterns=(r"\bx-amz-cf-(?:pop|id)\s*:", r"x-cache\s*:.*cloudfront"),
        asns=(),
    ),
    CdnRule(
        "fastly",
        cname_suffixes=("fastly.net", "fastlylb.net", "fastly.com"),
        header_patterns=(
            r"\bx-fastly-request-id\s*:",
            r"varnish.*x-served-by\s*:\s*cache-",
            r"x-served-by\s*:\s*cache-.*varnish",
        ),
        asns=("54113",),
    ),
    CdnRule(
        "akamai",
        cname_suffixes=(
            "akamaiedge.net", "edgekey.net", "edgesuite.net",
            "akamai.net", "akamaized.net", "akadns.net",
        ),
        header_patterns=(r"server\s*:\s*akamaighost", r"\bx-akamai-"),
        asns=("20940", "16625"),
    ),
    CdnRule(
        "azure",
        cname_suffixes=("azureedge.net", "azurefd.net", "msedge.net"),
        header_patterns=(r"\bx-azure-ref\s*:", r"\bx-msedge-ref\s*:"),
        asns=(),
    ),
    CdnRule(
        "google",
        cname_suffixes=("ghs.googlehosted.com", "googlehosted.com", "ghs.google.com"),
        header_patterns=(),
        asns=(),
    ),
    CdnRule(
        "bunnycdn",
        cname_suffixes=("bunnycdn.com", "bunnycdn.net"),
        header_patterns=(r"server\s*:\s*.*bunnycdn",),
        asns=(),
    ),
    CdnRule(
        "cdn77",
        cname_suffixes=("cdn77.org", "cdn77.net"),
        header_patterns=(r"server\s*:\s*.*cdn77",),
        asns=(),
    ),
    CdnRule(
        "imperva",
        cname_suffixes=("incapsula.com", "impervadns.net"),
        header_patterns=(r"\bx-iinfo\s*:", r"x-cdn\s*:\s*incapsula"),
        asns=("19551",),
    ),
    CdnRule(
        "stackpath",
        cname_suffixes=("stackpathdns.com", "stackpathcdn.com", "netdna-cdn.com", "netdna-ssl.com"),
        header_patterns=(r"server\s*:\s*.*(?:netdna|stackpath)",),
        asns=(),
    ),
    CdnRule(
        "keycdn",
        cname_suffixes=("kxcdn.com",),
        header_patterns=(r"server\s*:\s*.*keycdn",),
        asns=(),
    ),
    CdnRule(
        "arvancloud",
        cname_suffixes=("arvancloud.ir", "arvancdn.ir", "arvancdns.ir"),
        header_patterns=(r"server\s*:\s*.*arvan", r"\bx-arvan"),
        asns=(),
    ),
    CdnRule(
        "quiccloud",
        cname_suffixes=("quic.cloud",),
        header_patterns=(r"quic\.cloud",),
        asns=(),
    ),
    CdnRule(
        "gcore",
        cname_suffixes=("gcdn.co",),
        header_patterns=(),
        asns=("199524",),
    ),
    CdnRule(
        "edgecast",
        cname_suffixes=("edgecastcdn.net", "systemcdn.net"),
        header_patterns=(),
        asns=(),
    ),
    CdnRule(
        "edgio",
        cname_suffixes=("llnwd.net", "edgio.net"),
        header_patterns=(),
        asns=("22822",),
    ),
    CdnRule(
        "aliyun",
        cname_suffixes=("alikunlun.com",),
        header_patterns=(),
        asns=(),
    ),
)


def _normalize_cname(value: str) -> str:
    return value.strip().lower().rstrip(".")


def match_cname(cnames: list[str]) -> tuple[str, str] | None:
    for rule in RULES:
        for cname in cnames:
            host = _normalize_cname(cname)
            for suffix in rule.cname_suffixes:
                if host == suffix or host.endswith("." + suffix):
                    return rule.name, host
    return None


def _headers_blob(headers: dict) -> str:
    return "\n".join(f"{key.lower()}: {value}" for key, value in headers.items())


def match_headers(headers: dict) -> tuple[str, str] | None:
    if not headers:
        return None
    blob = _headers_blob(headers)
    for rule in RULES:
        for pattern in rule.header_patterns:
            if re.search(pattern, blob, re.IGNORECASE | re.DOTALL):
                return rule.name, pattern
    return None


def match_asn(asn: str | None) -> str | None:
    if not asn:
        return None
    asn = str(asn).upper().removeprefix("AS")
    for rule in RULES:
        if asn in rule.asns:
            return rule.name
    return None


def detect(cnames: list[str], headers: dict, asn: str | None) -> dict:
    signals: list[str] = []
    cdn: str | None = None
    confidence = "none"

    cname_hit = match_cname(cnames)
    if cname_hit:
        cdn = cname_hit[0]
        confidence = "high"
        signals.append(f"cname:{cname_hit[1]}")

    if cdn is None:
        header_hit = match_headers(headers)
        if header_hit:
            cdn = header_hit[0]
            confidence = "high"
            signals.append(f"header:{header_hit[1]}")

    asn_hit = match_asn(asn)
    if asn_hit:
        signals.append(f"asn:{asn}")
        if cdn is None:
            cdn = asn_hit
            confidence = "low"
        elif cdn == asn_hit:
            signals.append("corroborated")

    return {
        "cdn": cdn or "none",
        "confidence": confidence,
        "signals": signals,
    }
