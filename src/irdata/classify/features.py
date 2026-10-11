import html as html_module
import re

PERSIAN_RANGES = (
    (0x0600, 0x06FF),
    (0x0750, 0x077F),
    (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF),
    (0xFE70, 0xFEFF),
)

SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
LANG_RE = re.compile(r"<html[^>]*\blang\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
PHONE_RE = re.compile(r"(?:\+98|0098|0?9)\d{9,10}|۰۹\d{9}")

STRONG_TOKENS = [
    "zarinpal",
    "زرین‌پال",
    "زرین پال",
    "enamad",
    "نماد اعتماد",
    "ساماندهی",
    "shaparak",
    "به‌پرداخت",
    "به پرداخت",
    "بانک ملت",
    "بانک سامان",
    "بانک پارسیان",
    "درگاه پرداخت",
]
WEAK_TOKENS = [
    "تهران",
    "ایران",
    "فارسی",
]
PARKED_PATTERNS = [
    "domain for sale",
    "domain is for sale",
    "this domain is for sale",
    "this domain may be for sale",
    "buy this domain",
    "domain parking",
    "domain parking page",
    "parked free",
    "has been parked",
    "is parked",
    "domainmarket",
    "afternic",
    "sedo.com",
    "dan.com",
    "این دامنه برای فروش",
    "دامنه برای فروش",
    "فروش دامنه",
]


def strip_html(html: str) -> str:
    text = SCRIPT_RE.sub(" ", html)
    text = COMMENT_RE.sub(" ", text)
    text = TAG_RE.sub(" ", text)
    return text


def persian_ratio(text: str) -> float:
    total_alpha = 0
    persian = 0
    for ch in text:
        if ch.isalpha():
            total_alpha += 1
            code = ord(ch)
            for start, end in PERSIAN_RANGES:
                if start <= code <= end:
                    persian += 1
                    break
    if total_alpha == 0:
        return 0.0
    return persian / total_alpha


def detect_lang(html: str) -> str:
    match = LANG_RE.search(html)
    if match:
        return match.group(1).strip().lower()
    return ""


def detect_title(html: str) -> str:
    match = TITLE_RE.search(html)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()[:300]


def token_hits(html: str) -> list[str]:
    haystack = html.lower()
    hits = []
    for token in STRONG_TOKENS:
        if token.lower() in haystack:
            hits.append(f"strong:{token}")
    for token in WEAK_TOKENS:
        if token in html:
            hits.append(f"weak:{token}")
    if PHONE_RE.search(html) or PHONE_RE.search(html.replace("\u200c", "")):
        hits.append("strong:phone_ir")
    return hits


def parked(html: str) -> bool:
    haystack = html.lower()
    return any(pattern in haystack for pattern in PARKED_PATTERNS)


def extract(html: str) -> dict:
    html = html_module.unescape(html)
    visible = strip_html(html)
    hits = token_hits(html)
    return {
        "persian_ratio": round(persian_ratio(visible), 4),
        "lang": detect_lang(html),
        "title": detect_title(html),
        "token_hits": hits,
        "parked": parked(html),
    }
