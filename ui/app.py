import html as _html
import sys
import os

# Streamlit añade ui/ a sys.path; corregimos apuntando a la raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st


def _link(url: str, max_label: int = 72) -> str:
    """HTML link seguro: escapa la URL y trunca la etiqueta visible."""
    safe_href = _html.escape(url, quote=True)
    label = url if len(url) <= max_label else url[:max_label - 1] + "…"
    safe_label = _html.escape(label)
    return (
        f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer"'
        f' style="color:#00b4d8;word-break:break-all;">{safe_label}</a>'
    )

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="OSINTPassive",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Importaciones del proyecto (después de set_page_config) ─────────────────
from core.runner import AGENT_LABELS, stream_investigation  # noqa: E402
from core.validator import classify_input  # noqa: E402
from utils.pdf_generator import PDF_AVAILABLE, OSINTPDFReport  # noqa: E402

# ── Estado de sesión ─────────────────────────────────────────────────────────
if "osint_result" not in st.session_state:
    st.session_state["osint_result"] = {}
if "report_bytes" not in st.session_state:
    st.session_state["report_bytes"] = None
if "report_error" not in st.session_state:
    st.session_state["report_error"] = None

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🔍 OSINTPassive")
    st.caption("Inteligencia de fuentes abiertas · LangGraph + Groq AI")
    st.divider()

    saved_result = st.session_state["osint_result"]
    if saved_result.get("analysis_report"):
        st.markdown("### 📥 Exportar Reporte")

        _ext  = "pdf" if PDF_AVAILABLE else "html"
        _mime = "application/pdf" if PDF_AVAILABLE else "text/html"

        if st.session_state["report_error"]:
            st.error(f"No se pudo generar el reporte: {st.session_state['report_error']}")
        elif st.session_state["report_bytes"] is not None:
            st.download_button(
                label=f"📥 Descargar Reporte de Inteligencia ({_ext.upper()})",
                data=st.session_state["report_bytes"],
                file_name=f"OSINTPassive_Report.{_ext}",
                mime=_mime,
                use_container_width=True,
                type="primary",
            )
            if not PDF_AVAILABLE:
                st.caption(
                    "⚠️ xhtml2pdf no disponible — el reporte se descarga como HTML. "
                    "Instálalo con `pip install xhtml2pdf` para obtener PDF."
                )

        target_saved = saved_result.get("target_input", "")
        tipo_saved   = saved_result.get("input_type", "")
        tipo_labels  = {"email": "📧 Email", "domain": "🌐 Dominio", "name": "👤 Usuario"}
        st.divider()
        st.caption(f"Último objetivo: `{target_saved}`")
        st.caption(f"Tipo: {tipo_labels.get(tipo_saved, tipo_saved)}")
        emails_n    = len(saved_result.get("emails_found", []))
        urls_n      = len(saved_result.get("urls_found", []))
        breaches_n  = len([m for m in saved_result.get("metadata_extracted", []) if m.get("tipo") == "data_breach"])
        criticidad  = saved_result.get("analysis_report", {}).get("criticidad", "N/A")
        badge       = {"Alto": "🔴", "Medio": "🟡", "Bajo": "🟢"}.get(criticidad, "⚪")
        st.caption(f"Criticidad: {badge} {criticidad}")
        st.caption(f"Emails: {emails_n} · URLs: {urls_n} · Brechas: {breaches_n}")

# ── UI — cabecera ────────────────────────────────────────────────────────────

st.markdown(
    "<h1 style='text-align:center;color:#00b4d8;'>🔍 OSINTPassive</h1>"
    "<p style='text-align:center;color:#aaa;margin-top:-10px;'>"
    "Inteligencia de fuentes abiertas · LangGraph + Groq AI</p>",
    unsafe_allow_html=True,
)
st.divider()

col1, col2, col3 = st.columns([1, 3, 1])
with col2:
    target = st.text_input(
        label="Objetivo",
        placeholder="email@ejemplo.com · nombre-usuario · dominio.com",
        label_visibility="collapsed",
    )
    investigar = st.button("🔎 Investigar", use_container_width=True, type="primary")

st.divider()

# ── Lógica principal ─────────────────────────────────────────────────────────

if investigar:
    if not target.strip():
        st.warning("Introduce un objetivo antes de investigar.")
        st.stop()

    # Al iniciar nueva investigación, limpiar resultado anterior
    st.session_state["osint_result"]  = {}
    st.session_state["report_bytes"]  = None
    st.session_state["report_error"]  = None

    cleaned, input_type = classify_input(target.strip())
    tipo_labels = {"email": "📧 Email", "domain": "🌐 Dominio", "name": "👤 Usuario"}
    st.caption(f"Tipo detectado: **{tipo_labels.get(input_type, input_type)}** · objetivo: `{cleaned}`")

    initial_state = {
        "target_input": cleaned,
        "input_type": input_type,
        "emails_found": [],
        "usernames_found": [],
        "urls_found": [],
        "metadata_extracted": [],
        "raw_logs": [],
    }

    result: dict = {}
    error_msg: str = ""

    with st.status("🔄 Ejecutando investigación OSINT...", expanded=True) as status_box:
        try:
            for evt_type, name, data in stream_investigation(initial_state):
                icon, label = AGENT_LABELS.get(name, ("⚙️", name))

                if evt_type == "start":
                    st.write(f"🟡 **{label}**...")

                elif evt_type == "end":
                    findings = []
                    if data.get("emails_found"):
                        findings.append(f"{len(data['emails_found'])} email(s)")
                    if data.get("urls_found"):
                        findings.append(f"{len(data['urls_found'])} URL(s)")
                    if data.get("metadata_extracted"):
                        breaches = [
                            m for m in data["metadata_extracted"]
                            if m.get("tipo") == "data_breach"
                        ]
                        if breaches:
                            findings.append(f"{len(breaches)} brecha(s)")
                        snaps = [m for m in data["metadata_extracted"] if m.get("source") == "wayback"]
                        if snaps:
                            findings.append(f"{len(snaps)} snapshot(s)")
                    if data.get("analysis_report"):
                        cr = data["analysis_report"].get("criticidad", "")
                        if cr:
                            findings.append(f"criticidad: {cr}")
                    summary = f" → {', '.join(findings)}" if findings else ""
                    st.write(f"🟢 **{label}**{summary}")

                elif evt_type == "done":
                    result = data
                    # Persistir en session_state y pre-generar bytes del reporte
                    st.session_state["osint_result"] = result
                    try:
                        st.session_state["report_bytes"] = OSINTPDFReport.generate(result)
                        st.session_state["report_error"] = None
                    except Exception as pdf_exc:
                        st.session_state["report_bytes"] = None
                        st.session_state["report_error"] = str(pdf_exc)
                    status_box.update(label="✅ Investigación completada", state="complete", expanded=False)

                elif evt_type == "error":
                    error_msg = data if isinstance(data, str) else name
                    status_box.update(label="❌ Error en la investigación", state="error")

        except Exception as exc:
            error_msg = str(exc)
            status_box.update(label="❌ Error en la investigación", state="error")

    if error_msg:
        st.error(f"Error durante la investigación: {error_msg}")
        st.stop()

    if not result:
        st.warning("La investigación no devolvió resultados.")
        st.stop()

    # ── Botón de descarga en panel principal ─────────────────────────────────

    _ext  = "pdf" if PDF_AVAILABLE else "html"
    _mime = "application/pdf" if PDF_AVAILABLE else "text/html"

    dl_col, _, _ = st.columns([2, 2, 2])
    with dl_col:
        if st.session_state["report_error"]:
            st.error(f"No se pudo generar el reporte: {st.session_state['report_error']}")
        elif st.session_state["report_bytes"] is not None:
            st.download_button(
                label=f"📥 Descargar Reporte de Inteligencia ({_ext.upper()})",
                data=st.session_state["report_bytes"],
                file_name=f"OSINTPassive_Report.{_ext}",
                mime=_mime,
                use_container_width=True,
                type="primary",
            )

    st.divider()

    # ── Resultados ──────────────────────────────────────────────────────────

    report = result.get("analysis_report", {})
    emails = result.get("emails_found", [])
    urls = result.get("urls_found", [])
    metadata = result.get("metadata_extracted", [])
    logs = result.get("raw_logs", [])

    criticidad = report.get("criticidad", "N/A")
    badge = {"Alto": "🔴", "Medio": "🟡", "Bajo": "🟢"}.get(criticidad, "⚪")

    tab1, tab2 = st.tabs(["🧠 Resumen de IA", "📋 Emails y Enlaces"])

    with tab1:
        st.markdown(f"### {badge} Criticidad: **{criticidad}**")
        st.info(report.get("resumen", "Sin análisis disponible."))

        conexiones = report.get("conexiones_detectadas", [])
        if conexiones:
            st.markdown("#### 🔗 Conexiones Detectadas")
            for c in conexiones:
                st.markdown(f"- {c}")

        alertas = report.get("alertas", [])
        if alertas:
            st.markdown("#### ⚠️ Alertas de Seguridad")
            for a in alertas:
                st.warning(a)

        if logs:
            with st.expander("🪵 Log de ejecución"):
                for log in logs:
                    st.code(log, language=None)

    with tab2:
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown(f"#### 📧 Emails encontrados ({len(emails)})")
            if emails:
                for e in emails:
                    st.code(e, language=None)
            else:
                st.caption("Ninguno encontrado.")

        with col_b:
            st.markdown(f"#### 🌐 URLs encontradas ({len(urls)})")
            if urls:
                for u in urls:
                    st.markdown(f"- {_link(u)}", unsafe_allow_html=True)
            else:
                st.caption("Ninguna encontrada.")

        breaches = [m for m in metadata if m.get("tipo") == "data_breach"]
        if breaches:
            st.markdown(f"#### 🔓 Brechas de datos ({len(breaches)})")
            for b in breaches:
                st.markdown(f"- **{b.get('sitio', '?')}** ({b.get('año', '?')}) — `{b.get('email', '')}`")

        wayback_metas = [m for m in metadata if m.get("source") == "wayback"]
        if wayback_metas:
            st.markdown(f"#### 📅 Snapshots Wayback ({len(wayback_metas)})")
            for w in wayback_metas:
                snap_type = "Más reciente" if w.get("type") == "newest_snapshot" else "Más antiguo"
                ts = w.get("timestamp", "")[:8]
                archive_url = w.get("archive_url", "")
                original_url = w.get("original_url", "")
                st.markdown(
                    f"- **{snap_type}** ({ts}) · original: `{original_url}` → {_link(archive_url)}",
                    unsafe_allow_html=True,
                )

        other_meta = [m for m in metadata if m.get("source") not in ("wayback",) and m.get("tipo") != "data_breach"]
        if other_meta:
            st.markdown("#### 📄 Otros metadatos")
            for m in other_meta:
                url_val = m.get("url", "")
                title = m.get("title", url_val or "Sin título")[:80]
                with st.expander(title):
                    for k, v in m.items():
                        if k == "url" and str(v).startswith("http"):
                            st.markdown(f"**{k}:** {_link(str(v))}", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{k}:** `{_html.escape(str(v))}`", unsafe_allow_html=True)
