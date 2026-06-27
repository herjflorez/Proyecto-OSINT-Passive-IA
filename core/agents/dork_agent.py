import asyncio
from functools import partial

from ddgs import DDGS

from core.state import OSINTState

MAX_RESULTS = 10


def _build_query(target: str, input_type: str) -> str:
    if input_type == "email":
        return f'"{target}"'
    elif input_type == "domain":
        apex = target.lstrip("www.")
        return f"site:{apex} -www.{apex}"
    else:
        return f'"{target}" site:linkedin.com OR site:github.com OR site:twitter.com'


def _search_sync(query: str) -> list[dict]:
    return DDGS().text(query, max_results=MAX_RESULTS)


async def dork_agent(state: OSINTState) -> dict:
    target = state["target_input"]
    input_type = state.get("input_type", "name")
    query = _build_query(target, input_type)

    urls_found: list[str] = []
    metadata_extracted: list[dict] = []
    logs: list[str] = []

    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, partial(_search_sync, query))
        for r in results:
            url = r.get("href", "")
            title = r.get("title", "")
            if url:
                urls_found.append(url)
                metadata_extracted.append({
                    "source": "duckduckgo",
                    "title": title,
                    "url": url,
                    "query": query,
                })
        logs.append(f"[DORK] query='{query}' → {len(urls_found)} URL(s) encontradas")
    except Exception as e:
        logs.append(f"[DORK] Error en búsqueda para '{target}': {e}")

    return {
        "urls_found": urls_found,
        "metadata_extracted": metadata_extracted,
        "raw_logs": logs,
    }
