import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.agents.alias_agent import alias_agent, _check_platform, PLATFORMS

# ── Helpers ──────────────────────────────────────────────────────────────────

def _resp(status: int, text: str = "") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.text = text
    return r


def _mock_client(head_status: int = 200, get_status: int = 200, get_text: str = "{}") -> AsyncMock:
    client = AsyncMock()
    client.head.return_value = _resp(head_status)
    client.get.return_value = _resp(get_status, get_text)
    return client


BASE_STATE = {
    "target_input": "octocat",
    "input_type": "username",
    "emails_found": [],
    "usernames_found": [],
    "urls_found": [],
    "metadata_extracted": [],
    "raw_logs": [],
}

# ── Tests unitarios de _check_platform ───────────────────────────────────────

@pytest.mark.asyncio
async def test_check_platform_returns_url_on_200():
    client = _mock_client(head_status=200)
    sem = asyncio.Semaphore(5)
    config = {"url": "https://github.com/{username}", "method": "HEAD", "fp": []}

    result = await _check_platform(client, sem, "GitHub", config, "octocat")

    assert result is not None
    platform, url = result
    assert platform == "GitHub"
    assert url == "https://github.com/octocat"


@pytest.mark.asyncio
async def test_check_platform_returns_none_on_404():
    client = _mock_client(head_status=404)
    sem = asyncio.Semaphore(5)
    config = {"url": "https://github.com/{username}", "method": "HEAD", "fp": []}

    result = await _check_platform(client, sem, "GitHub", config, "nonexistent_xyz")
    assert result is None


@pytest.mark.asyncio
async def test_check_platform_filters_false_positive_in_body():
    client = _mock_client(get_status=200, get_text="null")
    sem = asyncio.Semaphore(5)
    config = {
        "url": "https://hacker-news.firebaseio.com/v0/user/{username}.json",
        "method": "GET",
        "fp": ["null"],
    }

    result = await _check_platform(client, sem, "HackerNews", config, "ghost")
    assert result is None


@pytest.mark.asyncio
async def test_check_platform_passes_valid_get_response():
    client = _mock_client(get_status=200, get_text='{"id": "octocat", "karma": 100}')
    sem = asyncio.Semaphore(5)
    config = {
        "url": "https://hacker-news.firebaseio.com/v0/user/{username}.json",
        "method": "GET",
        "fp": ["null"],
    }

    result = await _check_platform(client, sem, "HackerNews", config, "octocat")
    assert result == ("HackerNews", "https://hacker-news.firebaseio.com/v0/user/octocat.json")


@pytest.mark.asyncio
async def test_check_platform_handles_network_error():
    import httpx
    client = AsyncMock()
    client.head.side_effect = httpx.RequestError("Connection refused")
    sem = asyncio.Semaphore(5)
    config = {"url": "https://github.com/{username}", "method": "HEAD", "fp": []}

    result = await _check_platform(client, sem, "GitHub", config, "octocat")
    assert result is None


# ── Tests del agente completo (httpx mockeado) ───────────────────────────────

@pytest.mark.asyncio
async def test_agent_skips_email_input():
    state = {**BASE_STATE, "target_input": "victim@corp.com", "input_type": "email"}
    result = await alias_agent(state)

    assert "urls_found" not in result or result.get("urls_found") == []
    assert any("Omitido" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_agent_finds_profiles_on_200():
    mock = _mock_client(head_status=200, get_status=200, get_text='{"id":"octocat"}')
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock):
        result = await alias_agent(BASE_STATE)

    assert len(result["urls_found"]) == len(PLATFORMS)
    assert "octocat" in result["usernames_found"]
    assert any("✓" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_agent_returns_nothing_on_all_404():
    mock = _mock_client(head_status=404, get_status=404)
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock):
        result = await alias_agent(BASE_STATE)

    assert result.get("urls_found", []) == []
    assert result.get("usernames_found", []) == []
    assert any("no encontrado" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_agent_hackernews_false_positive_filtered():
    """Verifica que HackerNews con body='null' no cuenta como perfil encontrado."""
    async def smart_get(url, **kwargs):
        if "hacker-news" in url:
            return _resp(200, "null")
        return _resp(404)

    async def smart_head(url, **kwargs):
        return _resp(404)

    mock = AsyncMock()
    mock.head.side_effect = smart_head
    mock.get.side_effect = smart_get
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock):
        result = await alias_agent(BASE_STATE)

    hn_urls = [u for u in result.get("urls_found", []) if "hacker-news" in u]
    assert hn_urls == [], "HackerNews con 'null' no debe añadirse a urls_found"


@pytest.mark.asyncio
async def test_agent_partial_results():
    """Solo GitHub devuelve 200, el resto 404."""
    async def smart_head(url, **kwargs):
        if "github.com" in url:
            return _resp(200)
        return _resp(404)

    mock = AsyncMock()
    mock.head.side_effect = smart_head
    mock.get.return_value = _resp(404)
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock):
        result = await alias_agent(BASE_STATE)

    assert len(result["urls_found"]) == 1
    assert "github.com/octocat" in result["urls_found"][0]
    assert any("1/" in log for log in result["raw_logs"])
