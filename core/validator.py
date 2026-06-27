import re

from core.state import OSINTState

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_DOMAIN_RE = re.compile(
    r"^(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,})$"
)


def classify_input(raw: str) -> tuple[str, str]:
    """Limpia el input y lo clasifica como 'email', 'domain' o 'name'."""
    cleaned = raw.strip().lower()
    if _EMAIL_RE.match(cleaned):
        return cleaned, "email"
    if _DOMAIN_RE.match(cleaned):
        return cleaned, "domain"
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]
    return cleaned, "name"


def validator_node(state: OSINTState) -> dict:
    raw = state.get("target_input", "")
    cleaned, input_type = classify_input(raw)
    return {
        "target_input": cleaned,
        "input_type": input_type,
        "raw_logs": [f"[VALIDATOR] '{raw.strip()}' → '{cleaned}' (tipo: {input_type})"],
    }
