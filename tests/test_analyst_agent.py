import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.agents.analyst_agent import ReporteOSINT, analyst_agent, _build_user_message

# ── Estado de prueba ─────────────────────────────────────────────────────────

RICH_STATE = {
    "target_input": "octocat",
    "input_type": "username",
    "emails_found": ["octocat@github.com", "octocat@users.noreply.github.com"],
    "usernames_found": ["octocat"],
    "urls_found": ["https://github.com/octocat", "https://twitter.com/octocat"],
    "metadata_extracted": [
        {"source": "duckduckgo", "title": "Octocat · GitHub", "url": "https://github.com/octocat", "query": '"octocat"'},
    ],
    "raw_logs": ["[GITHUB] octocat: 2 email(s) extraídos", "[DORK] 2 URL(s)"],
}

EMPTY_STATE = {
    "target_input": "ghost_user",
    "input_type": "username",
    "emails_found": [],
    "usernames_found": [],
    "urls_found": [],
    "metadata_extracted": [],
    "raw_logs": [],
}

MOCK_REPORT = ReporteOSINT(
    resumen="Objetivo con exposición moderada. Email personal visible en commits públicos.",
    conexiones_detectadas=[
        "Email octocat@github.com vinculado a perfil GitHub público",
        "Username 'octocat' presente en GitHub y Twitter",
    ],
    alertas=[
        "Email expuesto en repositorios públicos de GitHub",
        "Presencia cross-platform identificable",
    ],
    criticidad="Medio",
)


def _mock_llm_chain(report: ReporteOSINT = MOCK_REPORT):
    mock_chain = AsyncMock()
    mock_chain.ainvoke.return_value = report
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain
    return mock_llm


# ── Tests unitarios ──────────────────────────────────────────────────────────

def test_build_user_message_includes_target():
    msg = _build_user_message(RICH_STATE)
    assert "octocat" in msg
    assert "username" in msg


def test_build_user_message_lists_emails():
    msg = _build_user_message(RICH_STATE)
    assert "octocat@github.com" in msg
    assert "octocat@users.noreply.github.com" in msg


def test_build_user_message_empty_state_shows_ninguno():
    msg = _build_user_message(EMPTY_STATE)
    assert "(ninguno)" in msg or "(ninguna)" in msg


def test_reporte_osint_model_valid():
    r = ReporteOSINT(
        resumen="Test",
        conexiones_detectadas=["conn1"],
        alertas=["alerta1"],
        criticidad="Alto",
    )
    d = r.model_dump()
    assert d["criticidad"] == "Alto"
    assert isinstance(d["conexiones_detectadas"], list)


# ── Tests del agente (LLM mockeado) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyst_returns_structured_report():
    with patch("core.agents.analyst_agent.ChatGroq", return_value=_mock_llm_chain()):
        result = await analyst_agent(RICH_STATE)

    assert "analysis_report" in result
    report = result["analysis_report"]
    assert report["criticidad"] == "Medio"
    assert "resumen" in report
    assert isinstance(report["conexiones_detectadas"], list)
    assert isinstance(report["alertas"], list)


@pytest.mark.asyncio
async def test_analyst_logs_criticidad():
    with patch("core.agents.analyst_agent.ChatGroq", return_value=_mock_llm_chain()):
        result = await analyst_agent(RICH_STATE)

    assert any("[ANALYST]" in log and "Medio" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_analyst_report_is_serializable():
    with patch("core.agents.analyst_agent.ChatGroq", return_value=_mock_llm_chain()):
        result = await analyst_agent(RICH_STATE)

    import json
    serialized = json.dumps(result["analysis_report"])
    assert "criticidad" in serialized


@pytest.mark.asyncio
async def test_analyst_handles_llm_error_gracefully():
    broken_chain = AsyncMock()
    broken_chain.ainvoke.side_effect = RuntimeError("Timeout de red")
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = broken_chain

    with patch("core.agents.analyst_agent.ChatGroq", return_value=mock_llm):
        result = await analyst_agent(RICH_STATE)

    assert "analysis_report" in result
    assert result["analysis_report"]["criticidad"] == "Bajo"
    assert any("[ANALYST] Error" in log for log in result["raw_logs"])


@pytest.mark.asyncio
async def test_analyst_with_empty_state_returns_report():
    low_report = ReporteOSINT(
        resumen="Sin datos suficientes para análisis.",
        conexiones_detectadas=[],
        alertas=[],
        criticidad="Bajo",
    )
    with patch("core.agents.analyst_agent.ChatGroq", return_value=_mock_llm_chain(low_report)):
        result = await analyst_agent(EMPTY_STATE)

    assert result["analysis_report"]["criticidad"] == "Bajo"
