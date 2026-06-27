import operator
import pytest
from langgraph.graph import StateGraph, END

from core.state import OSINTState, dedup_strings, dedup_urls, normalize_url


INITIAL_STATE: OSINTState = {
    "target_input": "target@example.com",
    "input_type": "email",
    "emails_found": ["seed@example.com"],
    "usernames_found": [],
    "urls_found": [],
    "metadata_extracted": [],
    "raw_logs": ["[INIT] Estado inicializado"],
}


# ── Estructura del TypedDict ──────────────────────────────────────────────────

def test_state_fields_exist():
    keys = set(OSINTState.__annotations__.keys())
    expected = {"target_input", "input_type", "emails_found", "usernames_found",
                "urls_found", "metadata_extracted", "raw_logs", "analysis_report"}
    assert expected == keys


def test_list_fields_have_callable_reducer():
    list_fields = ["emails_found", "usernames_found", "urls_found",
                   "metadata_extracted", "raw_logs"]
    for field in list_fields:
        annotation = OSINTState.__annotations__[field]
        metadata = getattr(annotation, "__metadata__", ())
        assert any(callable(m) for m in metadata), (
            f"'{field}' debe tener un reducer callable"
        )


def test_metadata_and_logs_still_use_operator_add():
    for field in ("metadata_extracted", "raw_logs"):
        annotation = OSINTState.__annotations__[field]
        metadata = getattr(annotation, "__metadata__", ())
        assert operator.add in metadata, (
            f"'{field}' debe seguir usando operator.add"
        )


# ── Tests de normalize_url ────────────────────────────────────────────────────

def test_normalize_url_strips_utm_params():
    url = "https://example.com/page?utm_source=google&id=42"
    result = normalize_url(url)
    assert "utm_source" not in result
    assert "id=42" in result


def test_normalize_url_preserves_non_tracking_params():
    url = "https://example.com/?q=osint&page=2"
    result = normalize_url(url)
    assert "q=osint" in result
    assert "page=2" in result


def test_normalize_url_handles_no_params():
    url = "https://example.com/page"
    assert normalize_url(url) == url


def test_normalize_url_strips_fbclid():
    url = "https://example.com/?fbclid=abc123&id=1"
    result = normalize_url(url)
    assert "fbclid" not in result
    assert "id=1" in result


# ── Tests de dedup_strings ────────────────────────────────────────────────────

def test_dedup_strings_removes_exact_duplicates():
    result = dedup_strings(["a@test.com", "b@test.com"], ["a@test.com"])
    assert result.count("a@test.com") == 1
    assert "b@test.com" in result


def test_dedup_strings_case_insensitive():
    result = dedup_strings(["User@Gmail.com"], ["user@gmail.com", "other@test.com"])
    assert len(result) == 2  # user@gmail.com (dedup) + other@test.com


def test_dedup_strings_preserves_first_occurrence():
    result = dedup_strings(["ALICE@TEST.COM"], ["alice@test.com"])
    assert result == ["ALICE@TEST.COM"]


def test_dedup_strings_empty_inputs():
    assert dedup_strings([], []) == []
    assert dedup_strings(["a@b.com"], []) == ["a@b.com"]
    assert dedup_strings([], ["a@b.com"]) == ["a@b.com"]


# ── Tests de dedup_urls ───────────────────────────────────────────────────────

def test_dedup_urls_same_url_after_stripping():
    a = "https://example.com/page?utm_source=google&id=1"
    b = "https://example.com/page?id=1"
    result = dedup_urls([a], [b])
    assert len(result) == 1


def test_dedup_urls_different_urls_both_kept():
    a = "https://example.com/page1"
    b = "https://example.com/page2"
    result = dedup_urls([a], [b])
    assert len(result) == 2


def test_dedup_urls_exact_duplicate():
    url = "https://example.com/page"
    result = dedup_urls([url, url], [url])
    assert result == [url]


# ── Integración con LangGraph ─────────────────────────────────────────────────

def test_agent_appends_email_without_overwriting():
    def fake_email_agent(state: OSINTState):
        return {
            "emails_found": ["nuevo@osint.com"],
            "raw_logs": ["[AGENT] Email encontrado: nuevo@osint.com"],
        }

    graph = StateGraph(OSINTState)
    graph.add_node("email_agent", fake_email_agent)
    graph.set_entry_point("email_agent")
    graph.add_edge("email_agent", END)
    app = graph.compile()

    result = app.invoke(INITIAL_STATE)

    assert "seed@example.com" in result["emails_found"]
    assert "nuevo@osint.com" in result["emails_found"]
    assert len(result["emails_found"]) == 2


def test_multiple_agents_accumulate_data():
    def agent_a(state: OSINTState):
        return {
            "emails_found": ["agente_a@osint.com"],
            "usernames_found": ["usuario_a"],
        }

    def agent_b(state: OSINTState):
        return {
            "emails_found": ["agente_b@osint.com"],
            "urls_found": ["https://perfil.ejemplo.com/usuario_a"],
        }

    graph = StateGraph(OSINTState)
    graph.add_node("agent_a", agent_a)
    graph.add_node("agent_b", agent_b)
    graph.set_entry_point("agent_a")
    graph.add_edge("agent_a", "agent_b")
    graph.add_edge("agent_b", END)
    app = graph.compile()

    result = app.invoke(INITIAL_STATE)

    assert len(result["emails_found"]) == 3  # seed + a + b (todos únicos)
    assert "usuario_a" in result["usernames_found"]
    assert "https://perfil.ejemplo.com/usuario_a" in result["urls_found"]


def test_duplicate_emails_deduped_across_agents():
    """Dos agentes que retornan el mismo email → solo 1 en el estado final."""
    def agent_a(state: OSINTState):
        return {"emails_found": ["dup@example.com"]}

    def agent_b(state: OSINTState):
        return {"emails_found": ["dup@example.com"]}

    graph = StateGraph(OSINTState)
    graph.add_node("a", agent_a)
    graph.add_node("b", agent_b)
    graph.set_entry_point("a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)
    app = graph.compile()

    result = app.invoke({
        "target_input": "x", "input_type": "name",
        "emails_found": [], "usernames_found": [],
        "urls_found": [], "metadata_extracted": [], "raw_logs": [],
    })

    assert result["emails_found"].count("dup@example.com") == 1


def test_target_input_is_preserved():
    def noop_agent(state: OSINTState):
        return {"raw_logs": ["[NOOP] Sin cambios"]}

    graph = StateGraph(OSINTState)
    graph.add_node("noop", noop_agent)
    graph.set_entry_point("noop")
    graph.add_edge("noop", END)
    app = graph.compile()

    result = app.invoke(INITIAL_STATE)

    assert result["target_input"] == "target@example.com"
    assert result["input_type"] == "email"
