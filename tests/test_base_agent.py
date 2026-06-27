import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from core.agents.base_agent import fetch_with_retry


def _make_response(status: int) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    return resp


# ── Caso exitoso ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_successful_request_returned_immediately():
    client = AsyncMock()
    client.get.return_value = _make_response(200)

    result = await fetch_with_retry(client, "get", "https://api.example.com/data")

    assert result.status_code == 200
    assert client.get.call_count == 1


# ── Reintentos en 429 ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retries_on_429_and_succeeds_on_third_attempt():
    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        return _make_response(429 if call_count < 3 else 200)

    client = AsyncMock()
    client.get.side_effect = mock_get

    with patch("core.agents.base_agent.asyncio.sleep", new_callable=AsyncMock):
        result = await fetch_with_retry(client, "get", "https://api.example.com", max_retries=3)

    assert call_count == 3
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_returns_429_response_after_max_retries():
    client = AsyncMock()
    client.get.return_value = _make_response(429)

    with patch("core.agents.base_agent.asyncio.sleep", new_callable=AsyncMock):
        result = await fetch_with_retry(client, "get", "https://api.example.com", max_retries=3)

    assert result.status_code == 429
    assert client.get.call_count == 3


# ── Reintentos en timeout ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retries_on_timeout_and_succeeds():
    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise httpx.ReadTimeout("timeout")
        return _make_response(200)

    client = AsyncMock()
    client.get.side_effect = mock_get

    with patch("core.agents.base_agent.asyncio.sleep", new_callable=AsyncMock):
        result = await fetch_with_retry(client, "get", "https://api.example.com", max_retries=3)

    assert call_count == 2
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_timeout_on_last_attempt_raises():
    client = AsyncMock()
    client.get.side_effect = httpx.ReadTimeout("always timeout")

    with patch("core.agents.base_agent.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(httpx.TimeoutException):
            await fetch_with_retry(client, "get", "https://api.example.com", max_retries=3)

    assert client.get.call_count == 3


# ── Errores no recuperables no se reintentan ──────────────────────────────────

@pytest.mark.asyncio
async def test_request_error_propagates_immediately():
    """Un RequestError genérico (no timeout) no se reintenta."""
    client = AsyncMock()
    client.get.side_effect = httpx.ConnectError("connection refused")

    with pytest.raises(httpx.RequestError):
        await fetch_with_retry(client, "get", "https://api.example.com", max_retries=3)

    assert client.get.call_count == 1  # sin reintentos


# ── Métodos HTTP ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_supports_head_method():
    client = AsyncMock()
    client.head.return_value = _make_response(200)

    result = await fetch_with_retry(client, "head", "https://example.com/resource")

    assert result.status_code == 200
    client.head.assert_called_once()
    client.get.assert_not_called()


@pytest.mark.asyncio
async def test_kwargs_forwarded_to_client():
    client = AsyncMock()
    client.get.return_value = _make_response(200)

    await fetch_with_retry(
        client, "get", "https://api.example.com",
        headers={"Authorization": "Bearer token"},
        follow_redirects=True,
    )

    call_kwargs = client.get.call_args[1]
    assert call_kwargs["headers"] == {"Authorization": "Bearer token"}
    assert call_kwargs["follow_redirects"] is True
