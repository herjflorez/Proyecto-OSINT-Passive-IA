import pytest
from unittest.mock import patch

from core.graph import build_graph

# ── Estado inicial de prueba ─────────────────────────────────────────────────
# input_type vacío: el validator_node (mock) lo clasificará a "name"

INITIAL_STATE = {
    "target_input": "octocat",
    "input_type": "",
    "emails_found": [],
    "usernames_found": [],
    "urls_found": [],
    "metadata_extracted": [],
    "raw_logs": [],
}

# ── Nodos falsos (sin red, sin LLM) ─────────────────────────────────────────

def _mock_validator(state):
    return {
        "target_input": state["target_input"],
        "input_type": "name",
        "raw_logs": [f"[VALIDATOR] '{state['target_input']}' → name"],
    }


async def _mock_github(state):
    return {
        "emails_found": ["octocat@github.com", "octocat@users.noreply.github.com"],
        "raw_logs": ["[GITHUB] octocat: 2 email(s) extraídos"],
    }


async def _mock_dork(state):
    return {
        "urls_found": ["https://github.com/octocat", "https://twitter.com/octocat"],
        "metadata_extracted": [
            {"source": "duckduckgo", "title": "Octocat · GitHub", "url": "https://github.com/octocat", "query": '"octocat"'},
            {"source": "duckduckgo", "title": "Octocat Twitter", "url": "https://twitter.com/octocat", "query": '"octocat"'},
        ],
        "raw_logs": ["[DORK] query='\"octocat\"' → 2 URL(s) encontradas"],
    }


async def _mock_analyst(state):
    return {
        "analysis_report": {
            "resumen": "Exposición moderada detectada.",
            "conexiones_detectadas": ["Email vinculado a GitHub público"],
            "alertas": ["Email expuesto en commits"],
            "criticidad": "Medio",
        },
        "raw_logs": ["[ANALYST] Análisis completado. Criticidad: Medio"],
    }


async def _mock_alias(state):
    return {
        "urls_found": ["https://github.com/octocat"],
        "usernames_found": ["octocat"],
        "raw_logs": ["[ALIAS] ✓ GitHub: https://github.com/octocat"],
    }


async def _mock_wayback(state):
    return {
        "urls_found": ["http://web.archive.org/web/20240101/https://github.com/octocat"],
        "metadata_extracted": [{"source": "wayback", "type": "newest_snapshot",
                                 "original_url": "https://github.com/octocat",
                                 "archive_url": "http://web.archive.org/web/20240101/https://github.com/octocat",
                                 "timestamp": "20240101120000",
                                 "label": "[Wayback Archive – Newest 20240101]"}],
        "raw_logs": ["[WAYBACK] Newest → http://web.archive.org/web/20240101/https://github.com/octocat"],
    }


async def _mock_breach(state):
    return {
        "metadata_extracted": [
            {"tipo": "data_breach", "email": "octocat@github.com",
             "sitio": "LinkedIn", "año": "2016"},
        ],
        "raw_logs": ["[BREACH] octocat@github.com: 1 filtraciones (1 detalladas)"],
    }


def _build_mocked_graph():
    with patch("core.graph.validator_node", _mock_validator), \
         patch("core.graph.github_agent",   _mock_github), \
         patch("core.graph.dork_agent",     _mock_dork), \
         patch("core.graph.alias_agent",    _mock_alias), \
         patch("core.graph.wayback_agent",  _mock_wayback), \
         patch("core.graph.breach_agent",   _mock_breach), \
         patch("core.graph.analyst_agent",  _mock_analyst):
        return build_graph()


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_graph_runs_to_completion():
    app = _build_mocked_graph()
    result = await app.ainvoke(INITIAL_STATE)
    assert result is not None


@pytest.mark.asyncio
async def test_graph_merges_emails_from_github_agent():
    app = _build_mocked_graph()
    result = await app.ainvoke(INITIAL_STATE)

    assert "octocat@github.com" in result["emails_found"]
    assert "octocat@users.noreply.github.com" in result["emails_found"]


@pytest.mark.asyncio
async def test_graph_merges_urls_from_dork_agent():
    app = _build_mocked_graph()
    result = await app.ainvoke(INITIAL_STATE)

    assert "https://github.com/octocat" in result["urls_found"]
    assert "https://twitter.com/octocat" in result["urls_found"]


@pytest.mark.asyncio
async def test_graph_accumulates_logs_from_both_agents():
    app = _build_mocked_graph()
    result = await app.ainvoke(INITIAL_STATE)

    logs = result["raw_logs"]
    assert any("[VALIDATOR]" in log for log in logs)
    assert any("[GITHUB]" in log for log in logs)
    assert any("[DORK]" in log for log in logs)


@pytest.mark.asyncio
async def test_graph_validator_sets_input_type():
    """validator_node debe clasificar 'octocat' como 'name' antes de los recolectores."""
    app = _build_mocked_graph()
    result = await app.ainvoke(INITIAL_STATE)

    assert result["target_input"] == "octocat"
    assert result["input_type"] == "name"


@pytest.mark.asyncio
async def test_graph_merges_metadata_from_dork():
    app = _build_mocked_graph()
    result = await app.ainvoke(INITIAL_STATE)

    sources = {m["source"] for m in result["metadata_extracted"] if "source" in m}
    assert "duckduckgo" in sources


@pytest.mark.asyncio
async def test_graph_both_agents_contribute():
    """Verifica que hay emails Y urls en el estado final tras la ejecución completa."""
    app = _build_mocked_graph()
    result = await app.ainvoke(INITIAL_STATE)

    assert len(result["emails_found"]) >= 1
    assert len(result["urls_found"]) >= 1


@pytest.mark.asyncio
async def test_graph_deduplicates_urls_across_agents():
    """https://github.com/octocat aparece en dork Y alias → solo 1 vez en el resultado."""
    app = _build_mocked_graph()
    result = await app.ainvoke(INITIAL_STATE)

    count = result["urls_found"].count("https://github.com/octocat")
    assert count == 1
