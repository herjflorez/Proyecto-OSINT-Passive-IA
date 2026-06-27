import pytest
from unittest.mock import patch

from core.agents.dork_agent import dork_agent, _build_query

# ── Fixtures ────────────────────────────────────────────────────────────────

FAKE_RESULTS = [
    {"title": "Perfil expuesto", "href": "https://example.com/profile", "body": "Datos públicos"},
    {"title": "Foro OSINT", "href": "https://forum.osint.org/thread/42", "body": "Mención encontrada"},
    {"title": "Sin URL", "href": "", "body": "Resultado inválido"},
]

BASE_STATE = {
    "target_input": "victim@corp.com",
    "input_type": "email",
    "emails_found": [],
    "usernames_found": [],
    "urls_found": [],
    "metadata_extracted": [],
    "raw_logs": [],
}


# ── Tests de _build_query ────────────────────────────────────────────────────

def test_query_email_uses_quotes():
    assert _build_query("victim@corp.com", "email") == '"victim@corp.com"'


def test_query_domain_uses_site_operator():
    q = _build_query("corp.com", "domain")
    assert "site:corp.com" in q
    assert "-www.corp.com" in q


def test_query_domain_strips_www():
    q = _build_query("www.corp.com", "domain")
    assert "site:corp.com" in q


def test_query_name_includes_social_sites():
    q = _build_query("John Doe", "name")
    assert '"John Doe"' in q
    assert "linkedin.com" in q


# ── Tests del agente (I/O mockeado) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_adds_valid_urls_to_state():
    with patch("core.agents.dork_agent._search_sync", return_value=FAKE_RESULTS):
        result = await dork_agent(BASE_STATE)

    assert "https://example.com/profile" in result["urls_found"]
    assert "https://forum.osint.org/thread/42" in result["urls_found"]


@pytest.mark.asyncio
async def test_agent_skips_empty_urls():
    with patch("core.agents.dork_agent._search_sync", return_value=FAKE_RESULTS):
        result = await dork_agent(BASE_STATE)

    assert "" not in result["urls_found"]
    assert len(result["urls_found"]) == 2


@pytest.mark.asyncio
async def test_agent_populates_metadata():
    with patch("core.agents.dork_agent._search_sync", return_value=FAKE_RESULTS):
        result = await dork_agent(BASE_STATE)

    assert len(result["metadata_extracted"]) == 2
    first = result["metadata_extracted"][0]
    assert first["source"] == "duckduckgo"
    assert first["title"] == "Perfil expuesto"
    assert first["url"] == "https://example.com/profile"
    assert '"victim@corp.com"' in first["query"]


@pytest.mark.asyncio
async def test_agent_logs_result_count():
    with patch("core.agents.dork_agent._search_sync", return_value=FAKE_RESULTS):
        result = await dork_agent(BASE_STATE)

    assert any("[DORK]" in log and "2 URL(s)" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_agent_handles_exception_gracefully():
    with patch("core.agents.dork_agent._search_sync", side_effect=RuntimeError("Rate limit")):
        result = await dork_agent(BASE_STATE)

    assert result["urls_found"] == []
    assert any("[DORK] Error" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_agent_domain_query_format():
    state = {**BASE_STATE, "target_input": "target.com", "input_type": "domain"}
    with patch("core.agents.dork_agent._search_sync", return_value=[]) as mock_search:
        await dork_agent(state)
        called_query = mock_search.call_args[0][0]

    assert "site:target.com" in called_query
    assert "-www.target.com" in called_query


@pytest.mark.asyncio
async def test_agent_empty_results_returns_empty_state():
    with patch("core.agents.dork_agent._search_sync", return_value=[]):
        result = await dork_agent(BASE_STATE)

    assert result["urls_found"] == []
    assert result["metadata_extracted"] == []
    assert any("0 URL(s)" in log for log in result["raw_logs"])
