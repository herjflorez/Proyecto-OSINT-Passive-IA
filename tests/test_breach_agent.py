import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.agents.breach_agent import (
    breach_agent,
    _check_email,
    _emails_to_check,
    _extract_year,
)

# ── Payloads JSON de la API LeakCheck ────────────────────────────────────────

BREACH_RESPONSE = {
    "success": True,
    "found": 3,
    "sources": [
        {"name": "LinkedIn",     "date": "2016-05"},
        {"name": "Adobe",        "date": "2013-10"},
        {"name": "Collection#1", "date": "2019-01"},
    ],
}

NO_BREACH_RESPONSE = {
    "success": True,
    "found": 0,
    "sources": [],
}

API_ERROR_RESPONSE = {
    "success": False,
    "message": "Rate limit exceeded",
}

# ── Estados de prueba ─────────────────────────────────────────────────────────

EMAIL_STATE = {
    "target_input": "victim@corp.com",
    "input_type": "email",
    "emails_found": [],
    "usernames_found": [],
    "urls_found": [],
    "metadata_extracted": [],
    "raw_logs": [],
}

USERNAME_STATE_WITH_EMAILS = {
    "target_input": "octocat",
    "input_type": "username",
    "emails_found": ["octocat@github.com", "octocat@noreply.com"],
    "usernames_found": ["octocat"],
    "urls_found": [],
    "metadata_extracted": [],
    "raw_logs": [],
}

USERNAME_STATE_NO_EMAILS = {
    "target_input": "ghost",
    "input_type": "username",
    "emails_found": [],
    "usernames_found": [],
    "urls_found": [],
    "metadata_extracted": [],
    "raw_logs": [],
}


# ── Tests de helpers ──────────────────────────────────────────────────────────

def test_extract_year_full_date():
    assert _extract_year("2016-05") == "2016"


def test_extract_year_year_only():
    assert _extract_year("2019") == "2019"


def test_extract_year_empty_string():
    assert _extract_year("") == "Desconocido"


def test_extract_year_none_like():
    assert _extract_year("") == "Desconocido"


def test_emails_to_check_email_input():
    emails = _emails_to_check(EMAIL_STATE)
    assert "victim@corp.com" in emails


def test_emails_to_check_includes_emails_found():
    emails = _emails_to_check(USERNAME_STATE_WITH_EMAILS)
    assert "octocat@github.com" in emails
    assert "octocat@noreply.com" in emails


def test_emails_to_check_respects_max_limit():
    state = {**USERNAME_STATE_NO_EMAILS,
             "emails_found": [f"user{i}@test.com" for i in range(10)]}
    emails = _emails_to_check(state)
    assert len(emails) <= 3


def test_emails_to_check_no_email_no_found_returns_empty():
    emails = _emails_to_check(USERNAME_STATE_NO_EMAILS)
    assert emails == []


def test_emails_to_check_deduplicates():
    state = {**EMAIL_STATE, "emails_found": ["victim@corp.com", "other@corp.com"]}
    emails = _emails_to_check(state)
    assert emails.count("victim@corp.com") == 1


# ── Tests de _check_email ─────────────────────────────────────────────────────

def _resp(data: dict, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.raise_for_status = MagicMock()
    r.json.return_value = data
    return r


@pytest.mark.asyncio
async def test_check_email_returns_breaches():
    client = AsyncMock()
    client.get.return_value = _resp(BREACH_RESPONSE)

    metadata, logs = await _check_email(client, "victim@corp.com")

    assert len(metadata) == 3
    assert all(m["tipo"] == "data_breach" for m in metadata)
    assert any(m["sitio"] == "LinkedIn" for m in metadata)
    assert any(m["año"] == "2016" for m in metadata)


@pytest.mark.asyncio
async def test_check_email_no_breaches_returns_empty():
    client = AsyncMock()
    client.get.return_value = _resp(NO_BREACH_RESPONSE)

    metadata, logs = await _check_email(client, "clean@example.com")

    assert metadata == []
    assert any("sin brechas" in log for log in logs)


@pytest.mark.asyncio
async def test_check_email_api_error_logs_gracefully():
    client = AsyncMock()
    client.get.return_value = _resp(API_ERROR_RESPONSE)

    metadata, logs = await _check_email(client, "victim@corp.com")

    assert metadata == []
    assert any("rechazó" in log for log in logs)


@pytest.mark.asyncio
async def test_check_email_network_error_handled():
    import httpx
    client = AsyncMock()
    client.get.side_effect = httpx.RequestError("Timeout")

    metadata, logs = await _check_email(client, "victim@corp.com")

    assert metadata == []
    assert any("Error de red" in log for log in logs)


@pytest.mark.asyncio
async def test_check_email_breach_structure():
    client = AsyncMock()
    client.get.return_value = _resp(BREACH_RESPONSE)

    metadata, _ = await _check_email(client, "victim@corp.com")

    for entry in metadata:
        assert "tipo" in entry
        assert "email" in entry
        assert "sitio" in entry
        assert "año" in entry
        assert entry["tipo"] == "data_breach"
        assert entry["email"] == "victim@corp.com"


# ── Tests del agente completo ─────────────────────────────────────────────────

def _make_mock_client(response_data):
    mock = AsyncMock()
    mock.get.return_value = _resp(response_data)
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


@pytest.mark.asyncio
async def test_agent_adds_breaches_to_metadata():
    mock = _make_mock_client(BREACH_RESPONSE)
    with patch("httpx.AsyncClient", return_value=mock):
        result = await breach_agent(EMAIL_STATE)

    assert len(result["metadata_extracted"]) == 3
    assert all(m["tipo"] == "data_breach" for m in result["metadata_extracted"])


@pytest.mark.asyncio
async def test_agent_logs_total_found():
    mock = _make_mock_client(BREACH_RESPONSE)
    with patch("httpx.AsyncClient", return_value=mock):
        result = await breach_agent(EMAIL_STATE)

    assert any("[BREACH]" in log and "filtraciones" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_agent_skips_when_no_emails():
    with patch("httpx.AsyncClient") as mock_cls:
        result = await breach_agent(USERNAME_STATE_NO_EMAILS)

    mock_cls.assert_not_called()
    assert any("Omitido" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_agent_checks_emails_found_in_state():
    mock = _make_mock_client(BREACH_RESPONSE)
    with patch("httpx.AsyncClient", return_value=mock):
        result = await breach_agent(USERNAME_STATE_WITH_EMAILS)

    assert len(result["metadata_extracted"]) > 0
    assert mock.get.call_count >= 2


@pytest.mark.asyncio
async def test_agent_no_breaches_returns_empty_metadata():
    mock = _make_mock_client(NO_BREACH_RESPONSE)
    with patch("httpx.AsyncClient", return_value=mock):
        result = await breach_agent(EMAIL_STATE)

    assert result["metadata_extracted"] == []
    assert any("sin brechas" in log for log in result["raw_logs"])
