import streamlit as st

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="OSINTPassive",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Importaciones del proyecto (después de set_page_config) ─────────────────
from core.runner import AGENT_LABELS, stream_investigation  # noqa: E402
from core.validator import classify_input  # noqa: E402

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
                    st.markdown(f"- [{u}]({u})")
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
                st.markdown(f"- **{snap_type}** ({ts}) — [{w.get('archive_url', '')}]({w.get('archive_url', '')})")

        other_meta = [m for m in metadata if m.get("source") not in ("wayback",) and m.get("tipo") != "data_breach"]
        if other_meta:
            st.markdown("#### 📄 Otros metadatos")
            for m in other_meta:
                with st.expander(m.get("title", m.get("url", "Sin título"))[:80]):
                    for k, v in m.items():
                        st.markdown(f"**{k}:** `{v}`")
