from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from utils.pdf_generator import PDF_AVAILABLE, OSINTPDFReport

# ── Estado simulado representativo ───────────────────────────────────────────

_MOCK_STATE: dict = {
    "target_input": "objetivo_prueba@domain.com",
    "input_type": "email",
    "emails_found": [
        "objetivo_prueba@domain.com",
        "personal_leak@gmail.com",
    ],
    "usernames_found": ["obj_prueba_dev"],
    "urls_found": ["https://github.com/obj_prueba_dev"],
    "metadata_extracted": [
        {
            "tipo": "data_breach",
            "email": "objetivo_prueba@domain.com",
            "sitio": "breacheddb.example",
            "año": "2023",
        },
        {
            "source": "wayback",
            "type": "newest_snapshot",
            "original_url": "https://domain.com",
            "archive_url": "https://web.archive.org/web/20230101/https://domain.com",
            "timestamp": "20230101120000",
        },
    ],
    "raw_logs": [
        "[VALIDATOR] 'objetivo_prueba@domain.com' → 'objetivo_prueba@domain.com' (tipo: email)"
    ],
    "analysis_report": {
        "criticidad": "Alto",
        "resumen": "Riesgo critico detectado en fuentes abiertas.",
        "alertas": ["Email expuesto en brecha de datos de 2023."],
        "conexiones_detectadas": [
            "El correo corporativo esta directamente indexado a repositorios personales de desarrollo."
        ],
    },
}


# ── Contrato básico ───────────────────────────────────────────────────────────

def test_generate_returns_bytes():
    result = OSINTPDFReport.generate(_MOCK_STATE)
    assert isinstance(result, bytes)


def test_generate_returns_non_empty_result():
    result = OSINTPDFReport.generate(_MOCK_STATE)
    assert len(result) > 0


# ── Salida en PDF real (cuando xhtml2pdf está disponible) ─────────────────────

@pytest.mark.skipif(not PDF_AVAILABLE, reason="xhtml2pdf no instalado")
def test_generate_produces_valid_pdf_header():
    result = OSINTPDFReport.generate(_MOCK_STATE)
    assert result.startswith(b"%PDF-"), "El reporte debe empezar con la cabecera PDF"


@pytest.mark.skipif(not PDF_AVAILABLE, reason="xhtml2pdf no instalado")
def test_generate_pdf_is_substantial():
    result = OSINTPDFReport.generate(_MOCK_STATE)
    assert len(result) > 1000, "El PDF debe tener contenido sustancial"


# ── Contenido HTML (verificado sobre el fallback para legibilidad) ─────────────
# El PDF binario codifica texto internamente; para comprobar el contenido
# del template se fuerza el fallback HTML con patch(PDF_AVAILABLE=False).

def test_html_contains_target_input():
    with patch("utils.pdf_generator.PDF_AVAILABLE", False):
        result = OSINTPDFReport.generate(_MOCK_STATE)
    assert b"objetivo_prueba@domain.com" in result


def test_html_contains_criticidad():
    with patch("utils.pdf_generator.PDF_AVAILABLE", False):
        result = OSINTPDFReport.generate(_MOCK_STATE)
    assert b"Alto" in result


def test_html_contains_email_found():
    with patch("utils.pdf_generator.PDF_AVAILABLE", False):
        result = OSINTPDFReport.generate(_MOCK_STATE)
    assert b"personal_leak@gmail.com" in result


def test_html_contains_username():
    with patch("utils.pdf_generator.PDF_AVAILABLE", False):
        result = OSINTPDFReport.generate(_MOCK_STATE)
    assert b"obj_prueba_dev" in result


def test_html_contains_resumen():
    with patch("utils.pdf_generator.PDF_AVAILABLE", False):
        result = OSINTPDFReport.generate(_MOCK_STATE)
    assert b"Riesgo critico" in result


# ── Robustez ante estado incompleto ──────────────────────────────────────────

def test_generate_with_minimal_state_does_not_raise():
    minimal = {"target_input": "test@example.com", "input_type": "email"}
    result = OSINTPDFReport.generate(minimal)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_with_empty_lists_does_not_raise():
    state = {
        "target_input": "example.com",
        "input_type": "domain",
        "emails_found": [],
        "usernames_found": [],
        "urls_found": [],
        "metadata_extracted": [],
        "raw_logs": [],
        "analysis_report": {},
    }
    result = OSINTPDFReport.generate(state)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_generate_without_analysis_report_uses_defaults():
    state = {**_MOCK_STATE, "analysis_report": None}
    with patch("utils.pdf_generator.PDF_AVAILABLE", False):
        result = OSINTPDFReport.generate(state)
    assert b"Sin analisis" in result


# ── Fallback HTML ─────────────────────────────────────────────────────────────

def test_generate_html_fallback_when_pdf_unavailable():
    with patch("utils.pdf_generator.PDF_AVAILABLE", False):
        result = OSINTPDFReport.generate(_MOCK_STATE)
    assert result.startswith(b"<!DOCTYPE html>")
    assert b"objetivo_prueba@domain.com" in result


def test_generate_html_fallback_is_valid_utf8():
    with patch("utils.pdf_generator.PDF_AVAILABLE", False):
        result = OSINTPDFReport.generate(_MOCK_STATE)
    decoded = result.decode("utf-8")
    assert "<!DOCTYPE html>" in decoded


# ── Ruta xhtml2pdf (simulada con mock) ───────────────────────────────────────

def test_generate_calls_xhtml2pdf_when_available():
    fake_pdf = b"%PDF-1.4 fake-content"

    mock_pisa_result = MagicMock()
    mock_pisa_result.err = 0

    def fake_create_pdf(html_str, dest, encoding):
        dest.write(fake_pdf)
        return mock_pisa_result

    mock_pisa = MagicMock()
    mock_pisa.CreatePDF.side_effect = fake_create_pdf

    with patch("utils.pdf_generator.PDF_AVAILABLE", True), \
         patch("utils.pdf_generator._pisa", mock_pisa):
        result = OSINTPDFReport.generate(_MOCK_STATE)

    mock_pisa.CreatePDF.assert_called_once()
    assert result == fake_pdf


def test_generate_raises_on_xhtml2pdf_error():
    mock_pisa_result = MagicMock()
    mock_pisa_result.err = 3

    mock_pisa = MagicMock()
    mock_pisa.CreatePDF.return_value = mock_pisa_result

    with patch("utils.pdf_generator.PDF_AVAILABLE", True), \
         patch("utils.pdf_generator._pisa", mock_pisa):
        with pytest.raises(RuntimeError, match="xhtml2pdf"):
            OSINTPDFReport.generate(_MOCK_STATE)
