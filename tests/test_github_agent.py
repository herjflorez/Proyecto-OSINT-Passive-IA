import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.agents.github_agent import github_agent, _extract_emails_from_events

# ── Fixtures ────────────────────────────────────────────────────────────────

FAKE_EVENTS = [
    {
        "type": "PushEvent",
        "payload": {
            "commits": [
                {
                    "author": {"email": "hacker@osint.test", "name": "Test Dev"},
                    "message": "fix: corrige bug en autenticación",
                },
                {
                    "author": {"email": "noreply@github.com", "name": "Ghost"},
                    "message": "docs: contacto en mensaje contacto@empresa.org",
                },
            ]
        },
    },
    {
        "type": "WatchEvent",
        "payload": {},
    },
]

BASE_STATE = {
    "target_input": "octocat",
    "input_type": "username",
    "emails_found": [],
    "usernames_found": [],
    "urls_found": [],
    "metadata_extracted": [],
    "raw_logs": [],
}


# ── Tests unitarios (sin red) ────────────────────────────────────────────────

def test_extract_emails_from_push_event():
    emails = _extract_emails_from_events(FAKE_EVENTS)
    assert "hacker@osint.test" in emails
    assert "noreply@github.com" in emails


def test_extract_email_embedded_in_commit_message():
    emails = _extract_emails_from_events(FAKE_EVENTS)
    assert "contacto@empresa.org" in emails


def test_non_push_events_are_ignored():
    only_watch = [{"type": "WatchEvent", "payload": {}}]
    assert _extract_emails_from_events(only_watch) == []


def test_empty_events_returns_empty():
    assert _extract_emails_from_events([]) == []


# ── Tests de integración (mockeados) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_extracts_emails_from_mocked_api():
    mock_response = MagicMock()
    mock_response.json.return_value = FAKE_EVENTS
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await github_agent(BASE_STATE)

    assert "hacker@osint.test" in result["emails_found"]
    assert "contacto@empresa.org" in result["emails_found"]
    assert any("[GITHUB]" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_agent_logs_extraction_count():
    mock_response = MagicMock()
    mock_response.json.return_value = FAKE_EVENTS
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await github_agent(BASE_STATE)

    assert any("email(s) extraídos" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_agent_returns_log_when_no_usernames():
    state = {**BASE_STATE, "target_input": "victim@corp.com", "input_type": "email"}
    result = await github_agent(state)

    assert "emails_found" not in result or result.get("emails_found") == []
    assert "[GITHUB] No hay usernames disponibles para buscar" in result["raw_logs"]


@pytest.mark.asyncio
async def test_agent_handles_http_error_gracefully():
    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 404
    http_error = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=mock_response)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = http_error
        result = await github_agent(BASE_STATE)

    assert result["emails_found"] == []
    assert any("HTTP 404" in log for log in result["raw_logs"])
