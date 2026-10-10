STRONG_WEIGHT = 0.5
WEAK_WEIGHT = 0.15
TOKEN_FULL_SCORE = 3.0


def token_score(hits: list[str]) -> float:
    total = 0.0
    for hit in hits:
        if hit.startswith("strong:"):
            total += STRONG_WEIGHT
        else:
            total += WEAK_WEIGHT
    return min(total / TOKEN_FULL_SCORE, 1.0)


def lang_score(lang: str) -> float:
    if lang.startswith("fa"):
        return 1.0
    if not lang:
        return 0.25
    return 0.0


def score(features: dict) -> tuple[float, str]:
    ratio = features.get("persian_ratio", 0.0) or 0.0
    fa_component = min(ratio / 0.30, 1.0)
    tok_component = token_score(features.get("token_hits", []))
    lng_component = lang_score(features.get("lang", ""))
    value = 0.55 * fa_component + 0.30 * tok_component + 0.15 * lng_component
    value = round(value, 4)
    if value >= 0.60:
        verdict = "iranian"
    elif value >= 0.35:
        verdict = "uncertain"
    else:
        verdict = "foreign"
    return value, verdict
