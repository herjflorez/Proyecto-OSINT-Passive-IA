import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.agents.wayback_agent import wayback_agent, _query_snapshot, _urls_to_check

# ── Payloads JSON de la API real de Wayback ──────────────────────────────────

SNAPSHOT_FOUND = {
    "url": "example.com",
    "archived_snapshots": {
        "closest": {
            "available": True,
            "url": "http://web.archive.org/web/20240101120000/https://example.com",
            "timestamp": "20240101120000",
            "status": "200",
        }
    },
}

OLDEST_SNAPSHOT_FOUND = {
    "url": "example.com",
    "archived_snapshots": {
        "closest": {
            "available": True,
            "url": "http://web.archive.org/web/19991015000000/https://example.com",
            "timestamp": "19991015000000",
            "status": "200",
        }
    },
}

SNAPSHOT_NOT_FOUND = {
    "url": "neverexisted.xyz",
    "archived_snapshots": {},
}

# ── Estados de prueba ─────────────────────────────────────────────────────────

DOMAIN_STATE = {
    "target_input": "example.com",
    "input_type": "domain",
    "emails_found": [],
    "usernames_found": [],
    "urls_found": [],
    "metadata_extracted": [],
    "raw_logs": [],
}

USERNAME_STATE_WITH_URLS = {
    "target_input": "octocat",
    "input_type": "username",
    "emails_found": [],
    "usernames_found": ["octocat"],
    "urls_found": ["https://github.com/octocat"],
    "metadata_extracted": [],
    "raw_logs": [],
}

EMAIL_STATE_NO_URLS = {
    "target_input": "victim@corp.com",
    "input_type": "email",
    "emails_found": [],
    "usernames_found": [],
    "urls_found": [],
    "metadata_extracted": [],
    "raw_logs": [],
}


# ── Tests de _urls_to_check ───────────────────────────────────────────────────

def test_urls_to_check_domain_input():
    targets = _urls_to_check(DOMAIN_STATE)
    assert "example.com" in targets


def test_urls_to_check_uses_urls_found():
    targets = _urls_to_check(USERNAME_STATE_WITH_URLS)
    assert "https://github.com/octocat" in targets


def test_urls_to_check_email_no_urls_returns_empty():
    targets = _urls_to_check(EMAIL_STATE_NO_URLS)
    assert targets == []


def test_urls_to_check_max_limit():
    state = {**EMAIL_STATE_NO_URLS, "urls_found": [f"https://site{i}.com" for i in range(20)]}
    targets = _urls_to_check(state)
    assert len(targets) <= 5


# ── Tests de _query_snapshot ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_snapshot_returns_url_when_available():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = SNAPSHOT_FOUND

    client = AsyncMock()
    client.get.return_value = mock_resp

    result = await _query_snapshot(client, "example.com")
    assert result is not None
    url, ts = result
    assert "web.archive.org" in url
    assert ts == "20240101120000"


@pytest.mark.asyncio
async def test_query_snapshot_returns_none_when_not_available():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = SNAPSHOT_NOT_FOUND

    client = AsyncMock()
    client.get.return_value = mock_resp

    result = await _query_snapshot(client, "neverexisted.xyz")
    assert result is None


@pytest.mark.asyncio
async def test_query_snapshot_handles_http_error():
    client = AsyncMock()
    client.get.side_effect = httpx_error()

    result = await _query_snapshot(client, "example.com")
    assert result is None


def httpx_error():
    import httpx
    return httpx.RequestError("Connection timeout")


# ── Tests del agente completo (httpx mockeado) ───────────────────────────────

def _make_mock_client(newest_data, oldest_data):
    call_count = {"n": 0}

    async def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "timestamp" in url:
            resp.json.return_value = oldest_data
        else:
            resp.json.return_value = newest_data
        return resp

    mock = AsyncMock()
    mock.get.side_effect = mock_get
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


@pytest.mark.asyncio
async def test_agent_adds_newest_and_oldest_urls():
    mock = _make_mock_client(SNAPSHOT_FOUND, OLDEST_SNAPSHOT_FOUND)

    with patch("httpx.AsyncClient", return_value=mock):
        result = await wayback_agent(DOMAIN_STATE)

    assert len(result["urls_found"]) == 2
    urls = result["urls_found"]
    assert any("20240101" in u for u in urls), "Debe incluir snapshot reciente"
    assert any("19991015" in u for u in urls), "Debe incluir snapshot antiguo"


@pytest.mark.asyncio
async def test_agent_metadata_includes_labels():
    mock = _make_mock_client(SNAPSHOT_FOUND, OLDEST_SNAPSHOT_FOUND)

    with patch("httpx.AsyncClient", return_value=mock):
        result = await wayback_agent(DOMAIN_STATE)

    sources = {m["source"] for m in result["metadata_extracted"]}
    types = {m["type"] for m in result["metadata_extracted"]}
    assert "wayback" in sources
    assert "newest_snapshot" in types
    assert "oldest_snapshot" in types


@pytest.mark.asyncio
async def test_agent_deduplicates_same_snapshot():
    """Si newest y oldest son la misma URL, solo se añade una vez."""
    same = {
        "url": "example.com",
        "archived_snapshots": {
            "closest": {
                "available": True,
                "url": "http://web.archive.org/web/20000101000000/https://example.com",
                "timestamp": "20000101000000",
                "status": "200",
            }
        },
    }
    mock = _make_mock_client(same, same)

    with patch("httpx.AsyncClient", return_value=mock):
        result = await wayback_agent(DOMAIN_STATE)

    assert len(result["urls_found"]) == 1


@pytest.mark.asyncio
async def test_agent_no_snapshots_logs_gracefully():
    mock = _make_mock_client(SNAPSHOT_NOT_FOUND, SNAPSHOT_NOT_FOUND)

    with patch("httpx.AsyncClient", return_value=mock):
        result = await wayback_agent(DOMAIN_STATE)

    assert result["urls_found"] == []
    assert any("Sin capturas" in log or "No se encontraron" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_agent_skips_when_no_domain_no_urls():
    with patch("httpx.AsyncClient") as mock_cls:
        result = await wayback_agent(EMAIL_STATE_NO_URLS)

    mock_cls.assert_not_called()
    assert any("Omitido" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_agent_processes_urls_from_state():
    mock = _make_mock_client(SNAPSHOT_FOUND, OLDEST_SNAPSHOT_FOUND)

    with patch("httpx.AsyncClient", return_value=mock):
        result = await wayback_agent(USERNAME_STATE_WITH_URLS)

    assert len(result["urls_found"]) >= 1
    assert any("[WAYBACK]" in log for log in result["raw_logs"])
