import asyncio

import httpx

_DELAYS = (1.0, 2.0, 4.0)  # backoff exponencial en segundos


async def fetch_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_retries: int = 3,
    **kwargs,
) -> httpx.Response:
    """
    Petición HTTP asíncrona con reintentos y backoff exponencial.

    Reintenta en:
    - HTTP 429 (rate limit)
    - httpx.TimeoutException (timeout de red)

    Todos los demás errores se propagan inmediatamente al llamador.
    """
    for attempt in range(max_retries):
        is_last = attempt == max_retries - 1
        delay = _DELAYS[min(attempt, len(_DELAYS) - 1)]

        try:
            resp = await getattr(client, method)(url, **kwargs)

            if resp.status_code == 429 and not is_last:
                await asyncio.sleep(delay)
                continue

            return resp

        except httpx.TimeoutException:
            if is_last:
                raise
            await asyncio.sleep(delay)

    # Sólo alcanzable si max_retries == 0
    raise httpx.RequestError(f"Sin reintentos disponibles para {url}")
