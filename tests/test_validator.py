import pytest

from core.validator import classify_input, validator_node


# ── Tests de classify_input ───────────────────────────────────────────────────

def test_classify_email_plain():
    cleaned, kind = classify_input("user@example.com")
    assert kind == "email"
    assert cleaned == "user@example.com"


def test_classify_email_uppercase_lowercased():
    cleaned, kind = classify_input("USER@EXAMPLE.COM")
    assert kind == "email"
    assert cleaned == "user@example.com"


def test_classify_email_with_plus():
    cleaned, kind = classify_input("user+tag@gmail.com")
    assert kind == "email"


def test_classify_domain_simple():
    cleaned, kind = classify_input("example.com")
    assert kind == "domain"
    assert cleaned == "example.com"


def test_classify_domain_with_www():
    cleaned, kind = classify_input("www.example.com")
    assert kind == "domain"


def test_classify_domain_subdomain():
    cleaned, kind = classify_input("sub.example.co.uk")
    assert kind == "domain"


def test_classify_username_plain():
    cleaned, kind = classify_input("octocat")
    assert kind == "name"
    assert cleaned == "octocat"


def test_classify_username_with_at_prefix():
    cleaned, kind = classify_input("@octocat")
    assert kind == "name"
    assert cleaned == "octocat"  # @ prefix stripped


def test_classify_username_with_spaces():
    cleaned, kind = classify_input("John Doe")
    assert kind == "name"


def test_classify_strips_whitespace():
    cleaned, kind = classify_input("  octocat  ")
    assert cleaned == "octocat"


def test_classify_lowercases_output():
    cleaned, kind = classify_input("  OCTOCAT  ")
    assert cleaned == "octocat"


def test_classify_bare_word_not_domain():
    _, kind = classify_input("google")
    assert kind == "name"  # sin punto → no es dominio


# ── Tests de validator_node ───────────────────────────────────────────────────

BASE_STATE = {
    "target_input": "octocat",
    "input_type": "",
    "emails_found": [],
    "usernames_found": [],
    "urls_found": [],
    "metadata_extracted": [],
    "raw_logs": [],
}


def test_validator_node_sets_input_type():
    result = validator_node(BASE_STATE)
    assert result["input_type"] == "name"


def test_validator_node_sets_target_input_cleaned():
    state = {**BASE_STATE, "target_input": "  OCTOCAT  "}
    result = validator_node(state)
    assert result["target_input"] == "octocat"


def test_validator_node_appends_to_raw_logs():
    result = validator_node(BASE_STATE)
    assert "raw_logs" in result
    assert len(result["raw_logs"]) == 1
    assert "[VALIDATOR]" in result["raw_logs"][0]


def test_validator_node_classifies_email():
    state = {**BASE_STATE, "target_input": "victim@corp.com"}
    result = validator_node(state)
    assert result["input_type"] == "email"
    assert result["target_input"] == "victim@corp.com"


def test_validator_node_classifies_domain():
    state = {**BASE_STATE, "target_input": "example.com"}
    result = validator_node(state)
    assert result["input_type"] == "domain"


def test_validator_node_strips_at_prefix_for_username():
    state = {**BASE_STATE, "target_input": "@johndoe"}
    result = validator_node(state)
    assert result["input_type"] == "name"
    assert result["target_input"] == "johndoe"
