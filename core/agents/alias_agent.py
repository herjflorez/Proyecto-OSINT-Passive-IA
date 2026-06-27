import asyncio
import random

import httpx

from core.agents.base_agent import fetch_with_retry
from core.state import OSINTState

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# method: HEAD (rápido, sin body) o GET (necesario para detectar falsos positivos en body)
# fp: lista de cadenas que, si aparecen en el body de un 200, indican que la cuenta NO existe
PLATFORMS: dict[str, dict] = {
    "GitHub":     {"url": "https://github.com/{username}",                                  "method": "HEAD", "fp": []},
    "Reddit":     {"url": "https://www.reddit.com/user/{username}/about.json",              "method": "GET",  "fp": ["error", "USER_DOESNT_EXIST"]},
    "Medium":     {"url": "https://medium.com/@{username}",                                 "method": "HEAD", "fp": []},
    "Linktree":   {"url": "https://linktr.ee/{username}",                                   "method": "HEAD", "fp": []},
    "Pinterest":  {"url": "https://www.pinterest.com/{username}/",                          "method": "HEAD", "fp": []},
    "SoundCloud": {"url": "https://soundcloud.com/{username}",                              "method": "HEAD", "fp": []},
    "Keybase":    {"url": "https://keybase.io/{username}",                                  "method": "HEAD", "fp": []},
    "DevTo":      {"url": "https://dev.to/{username}",                                      "method": "HEAD", "fp": []},
    "HackerNews": {"url": "https://hacker-news.firebaseio.com/v0/user/{username}.json",    "method": "GET",  "fp": ["null"]},
    "Telegram":   {"url": "https://t.me/{username}",                                        "method": "HEAD", "fp": []},
}

CONCURRENCY = 5
TIMEOUT = 10.0


async def _check_platform(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    platform: str,
    config: dict,
    username: str,
) -> tuple[str, str] | None:
    url = config["url"].format(username=username)
    async with semaphore:
        try:
            resp = await fetch_with_retry(
                client, config["method"].lower(), url, follow_redirects=True
            )

            if resp.status_code != 200:
                return None

            # Filtra falsos positivos inspeccionando el body (solo en GET)
            if config["method"] == "GET" and config["fp"]:
                body = resp.text
                for marker in config["fp"]:
                    if marker in body:
                        return None

            return (platform, url)

        except (httpx.RequestError, httpx.TimeoutException):
            return None


async def alias_agent(state: OSINTState) -> dict:
    if state.get("input_type") not in ("name", "username"):
        return {"raw_logs": ["[ALIAS] Omitido: input no es username/name"]}

    username = state["target_input"]
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers) as client:
        tasks = [
            _check_platform(client, semaphore, platform, config, username)
            for platform, config in PLATFORMS.items()
        ]
        results = await asyncio.gather(*tasks)

    urls_found: list[str] = []
    logs: list[str] = []

    for res in results:
        if res:
            platform, url = res
            urls_found.append(url)
            logs.append(f"[ALIAS] ✓ {platform}: {url}")

    if not urls_found:
        logs.append(f"[ALIAS] '{username}' no encontrado en ninguna plataforma verificada")
        return {"raw_logs": logs}

    logs.append(f"[ALIAS] {len(urls_found)}/{len(PLATFORMS)} plataformas con perfil activo")
    return {
        "urls_found": urls_found,
        "usernames_found": [username],
        "raw_logs": logs,
    }
