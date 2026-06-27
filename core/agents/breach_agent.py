import asyncio

import httpx

from core.agents.base_agent import fetch_with_retry
from core.state import OSINTState

LEAKCHECK_API = "https://leakcheck.io/api/public?check={email}"
MAX_EMAILS_TO_CHECK = 3
MAX_BREACHES_PER_EMAIL = 25
TIMEOUT = 12.0


def _extract_year(date_str: str) -> str:
    if not date_str:
        return "Desconocido"
    return date_str[:4] if len(date_str) >= 4 else date_str


def _emails_to_check(state: OSINTState) -> list[str]:
    emails: list[str] = []

    if state.get("input_type") == "email":
        emails.append(state["target_input"])

    for e in state.get("emails_found", []):
        if e not in emails:
            emails.append(e)
        if len(emails) >= MAX_EMAILS_TO_CHECK:
            break

    return emails


async def _check_email(client: httpx.AsyncClient, email: str) -> tuple[list[dict], list[str]]:
    """Devuelve (metadata_breaches, logs)."""
    url = LEAKCHECK_API.format(email=email)
    metadata: list[dict] = []
    logs: list[str] = []

    try:
        resp = await fetch_with_retry(client, "get", url)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            logs.append(f"[BREACH] API rechazó la consulta para {email}")
            return metadata, logs

        found = data.get("found", 0)
        if not found:
            logs.append(f"[BREACH] {email}: sin brechas conocidas")
            return metadata, logs

        sources = data.get("sources", [])[:MAX_BREACHES_PER_EMAIL]
        for source in sources:
            metadata.append({
                "tipo": "data_breach",
                "email": email,
                "sitio": source.get("name", "Desconocido"),
                "año": _extract_year(source.get("date", "")),
            })

        logs.append(f"[BREACH] {email}: {found} filtraciones ({len(sources)} detalladas)")

    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logs.append(f"[BREACH] Error de red para {email}: {e}")
    except (ValueError, KeyError) as e:
        logs.append(f"[BREACH] Error parseando respuesta para {email}: {e}")

    return metadata, logs


async def breach_agent(state: OSINTState) -> dict:
    emails = _emails_to_check(state)

    if not emails:
        return {"raw_logs": ["[BREACH] Omitido: no hay emails para verificar"]}

    all_metadata: list[dict] = []
    all_logs: list[str] = []

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        tasks = [_check_email(client, email) for email in emails]
        results = await asyncio.gather(*tasks)

    for metadata, logs in results:
        all_metadata.extend(metadata)
        all_logs.extend(logs)

    return {
        "metadata_extracted": all_metadata,
        "raw_logs": all_logs,
    }
