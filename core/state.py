import operator
from typing import Annotated, NotRequired, TypedDict
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "_ga", "_gl", "mc_cid", "mc_eid",
})


def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url.strip())
        params = parse_qs(parsed.query, keep_blank_values=True)
        cleaned = {k: v for k, v in params.items() if k.lower() not in _TRACKING_PARAMS}
        return urlunparse(parsed._replace(query=urlencode(cleaned, doseq=True)))
    except Exception:
        return url.strip()


def dedup_strings(a: list[str], b: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in a + b:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item.strip())
    return result


def dedup_urls(a: list[str], b: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in a + b:
        normalized = normalize_url(url)
        key = normalized.lower()
        if key and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


class OSINTState(TypedDict):
    target_input: str
    input_type: str
    emails_found: Annotated[list[str], dedup_strings]
    usernames_found: Annotated[list[str], dedup_strings]
    urls_found: Annotated[list[str], dedup_urls]
    metadata_extracted: Annotated[list[dict], operator.add]
    raw_logs: Annotated[list[str], operator.add]
    analysis_report: NotRequired[dict]  # Poblado por analyst_agent; last-write-wins
