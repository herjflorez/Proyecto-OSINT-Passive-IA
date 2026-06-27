import asyncio

import httpx

from core.agents.base_agent import fetch_with_retry
from core.state import OSINTState

AVAILABILITY_API = "http://archive.org/wayback/available?url={url}"
OLDEST_TIMESTAMP = "19960101"
MAX_URLS_TO_CHECK = 5
TIMEOUT = 12.0


async def _query_snapshot(
    client: httpx.AsyncClient,
    url: str,
    timestamp: str | None = None,
) -> tuple[str, str] | None:
    """Devuelve (archive_url, snapshot_timestamp) o None si no hay captura."""
    endpoint = AVAILABILITY_API.format(url=url)
    if timestamp:
        endpoint += f"&timestamp={timestamp}"
    try:
        resp = await fetch_with_retry(client, "get", endpoint)
        resp.raise_for_status()
        data = resp.json()
        closest = data.get("archived_snapshots", {}).get("closest", {})
        if closest.get("available"):
            return (closest["url"], closest["timestamp"])
    except (httpx.RequestError, httpx.HTTPStatusError, KeyError, ValueError):
        pass
    return None


def _urls_to_check(state: OSINTState) -> list[str]:
    targets: list[str] = []

    if state.get("input_type") == "domain":
        targets.append(state["target_input"])

    for url in state.get("urls_found", [])[:MAX_URLS_TO_CHECK]:
        if url not in targets:
            targets.append(url)

    return targets


async def wayback_agent(state: OSINTState) -> dict:
    targets = _urls_to_check(state)

    if not targets:
        return {"raw_logs": ["[WAYBACK] Omitido: no hay dominio ni URLs previas que archivar"]}

    urls_found: list[str] = []
    metadata_extracted: list[dict] = []
    logs: list[str] = []

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for target in targets:
            # Lanzamos las dos consultas en paralelo: más reciente y más antigua
            newest, oldest = await asyncio.gather(
                _query_snapshot(client, target),
                _query_snapshot(client, target, timestamp=OLDEST_TIMESTAMP),
            )

            if newest:
                archive_url, ts = newest
                label = f"[Wayback Archive – Newest {ts[:8]}] {archive_url}"
                urls_found.append(archive_url)
                metadata_extracted.append({
                    "source": "wayback",
                    "type": "newest_snapshot",
                    "original_url": target,
                    "archive_url": archive_url,
                    "timestamp": ts,
                    "label": label,
                })
                logs.append(f"[WAYBACK] Newest → {archive_url}")

            if oldest and (not newest or oldest[0] != newest[0]):
                archive_url, ts = oldest
                label = f"[Wayback Archive – Oldest {ts[:8]}] {archive_url}"
                urls_found.append(archive_url)
                metadata_extracted.append({
                    "source": "wayback",
                    "type": "oldest_snapshot",
                    "original_url": target,
                    "archive_url": archive_url,
                    "timestamp": ts,
                    "label": label,
                })
                logs.append(f"[WAYBACK] Oldest → {archive_url}")

            if not newest and not oldest:
                logs.append(f"[WAYBACK] Sin capturas archivadas para: {target}")

    if not urls_found:
        logs.append("[WAYBACK] No se encontraron capturas en ningún objetivo")

    return {
        "urls_found": urls_found,
        "metadata_extracted": metadata_extracted,
        "raw_logs": logs,
    }
