import os
import random
import re

import httpx

from core.agents.base_agent import fetch_with_retry
from core.state import OSINTState

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
GITHUB_API = "https://api.github.com"


def _build_headers() -> dict:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _extract_emails_from_events(events: list[dict]) -> list[str]:
    emails: set[str] = set()
    for event in events:
        if event.get("type") != "PushEvent":
            continue
        commits = event.get("payload", {}).get("commits", [])
        for commit in commits:
            author_email = commit.get("author", {}).get("email", "")
            if author_email:
                emails.update(EMAIL_REGEX.findall(author_email))
            emails.update(EMAIL_REGEX.findall(commit.get("message", "")))
    return list(emails)


async def github_agent(state: OSINTState) -> dict:
    usernames: list[str] = list(state.get("usernames_found", []))

    if state.get("input_type") in ("name", "username"):
        usernames = [state["target_input"]] + usernames

    if not usernames:
        return {"raw_logs": ["[GITHUB] No hay usernames disponibles para buscar"]}

    emails_found: list[str] = []
    logs: list[str] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for username in usernames:
            url = f"{GITHUB_API}/users/{username}/events/public"
            try:
                response = await fetch_with_retry(client, "get", url, headers=_build_headers())
                response.raise_for_status()
                extracted = _extract_emails_from_events(response.json())
                emails_found.extend(extracted)
                logs.append(f"[GITHUB] {username}: {len(extracted)} email(s) extraídos")
            except httpx.HTTPStatusError as e:
                logs.append(f"[GITHUB] HTTP {e.response.status_code} para usuario '{username}'")
            except httpx.RequestError as e:
                logs.append(f"[GITHUB] Error de conexión para '{username}': {e}")

    return {"emails_found": emails_found, "raw_logs": logs}
