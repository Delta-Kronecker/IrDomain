import dns.asyncresolver
import dns.resolver

SUFFIX_PROVIDERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cloudflare", ("cloudflare.com", "cloudflare.net")),
    ("arvancloud", ("arvancloud.ir",)),
    ("godaddy", ("domaincontrol.com",)),
    ("namecheap", ("registrar-servers.com",)),
    ("google", ("googledomains.com", "google.com", "googlehosted.com")),
    ("azure", ("azure-dns.com", "azure-dns.net", "azure-dns.org", "azure-dns.info")),
    ("gandi", ("gandi.net",)),
    ("dynadns", ("dynadns.com", "dyndns.org")),
    ("he", ("he.net",)),
    ("irandns", ("irandns.com",)),
    ("parsdns", ("parsdns.com", "parsonline.ir")),
    ("netafraz", ("netafraz.com", "netafraz.net")),
    ("hostiran", ("hostiran.ir",)),
    ("parspack", ("parspack.co", "parspack.net")),
    ("firsthost", ("firstholdings.com",)),
)

SUBSTRING_PROVIDERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("aws", ("awsdns-",)),
    ("gcp", ("googledomains", "cloud-dns")),
)

RESOLVE_TIMEOUT = 5.0


def detect_provider(ns_hosts: list[str]) -> str | None:
    hosts = [h.strip().lower().rstrip(".") for h in ns_hosts if h.strip()]
    for provider, suffixes in SUFFIX_PROVIDERS:
        for host in hosts:
            for suffix in suffixes:
                if host == suffix or host.endswith("." + suffix):
                    return provider
    for provider, needles in SUBSTRING_PROVIDERS:
        for host in hosts:
            for needle in needles:
                if needle in host:
                    return provider
    return None


def make_resolver() -> dns.asyncresolver.Resolver:
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = RESOLVE_TIMEOUT
    return resolver


async def resolve_ns(resolver: dns.asyncresolver.Resolver, domain: str) -> list[str]:
    try:
        answer = await resolver.resolve(domain, "NS")
    except (
        dns.resolver.NoAnswer,
        dns.resolver.NXDOMAIN,
        dns.resolver.NoNameservers,
        dns.exception.Timeout,
    ):
        return []
    if not answer:
        return []
    names = sorted({str(record.target).rstrip(".").lower() for record in answer})
    return names
