"""
utils/pdf_generator.py

Genera un reporte de inteligencia OSINT en formato PDF usando xhtml2pdf
(motor puro Python, sin dependencias nativas del sistema operativo).
Fallback a HTML bytes si xhtml2pdf no está disponible.
"""

import html
from datetime import datetime
from io import BytesIO

try:
    from xhtml2pdf import pisa as _pisa
    PDF_AVAILABLE = True
except Exception:
    _pisa = None
    PDF_AVAILABLE = False


# ── Mapas de presentación ─────────────────────────────────────────────────────

_BADGE_COLORS: dict[str, tuple[str, str]] = {
    "Alto":  ("#c0392b", "#ffffff"),
    "Medio": ("#e67e22", "#ffffff"),
    "Bajo":  ("#1e8449", "#ffffff"),
}

_TIPO_LABELS: dict[str, str] = {
    "email":  "Email",
    "domain": "Dominio",
    "name":   "Usuario / Alias",
}


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _truncate(text: str, max_len: int = 85) -> str:
    return text if len(text) <= max_len else text[:max_len - 3] + "..."


# ── Construcción del HTML ─────────────────────────────────────────────────────

def _cover_row(label: str, value_html: str) -> str:
    return (
        f'<tr>'
        f'<td style="color:#90caf9;font-size:8pt;text-transform:uppercase;'
        f'letter-spacing:1pt;width:90pt;padding:5pt 0;vertical-align:top;">{_e(label)}</td>'
        f'<td style="color:#ffffff;font-size:11pt;font-weight:bold;padding:5pt 0;">{value_html}</td>'
        f'</tr>'
    )


def _build_html(
    target: str,
    tipo_label: str,
    fecha: str,
    criticidad: str,
    resumen: str,
    conexiones: list[str],
    alertas: list[str],
    emails: list[str],
    usernames: list[str],
    urls: list[str],
    breaches: list[dict],
    snapshots: list[dict],
) -> str:

    badge_bg, badge_fg = _BADGE_COLORS.get(criticidad, ("#7f8c8d", "#ffffff"))
    accent = badge_bg

    badge_html = (
        f'<span style="background-color:{badge_bg};color:{badge_fg};'
        f'padding:3pt 12pt;font-size:9pt;font-weight:bold;'
        f'text-transform:uppercase;letter-spacing:1pt;">{_e(criticidad)}</span>'
    )

    # ── CSS global ────────────────────────────────────────────────────────────
    css = f"""
    @page {{
        size: A4;
        margin: 20mm 15mm;
    }}
    body {{
        font-family: Arial, Helvetica, sans-serif;
        font-size: 10pt;
        color: #1a1a2e;
        line-height: 1.5;
    }}
    p {{ margin: 0 0 6pt 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 9pt; }}
    th {{
        background-color: #0d1b2a;
        color: #ffffff;
        padding: 5pt 7pt;
        text-align: left;
        font-size: 8pt;
        letter-spacing: 0.5pt;
    }}
    td {{ padding: 5pt 7pt; border-bottom: 0.5pt solid #dce6f0; }}
    .section {{ margin-bottom: 18pt; }}
    .section-title {{
        font-size: 9pt;
        font-weight: bold;
        color: #0d1b2a;
        text-transform: uppercase;
        letter-spacing: 1pt;
        border-left: 3pt solid {accent};
        padding-left: 7pt;
        margin-bottom: 7pt;
    }}
    .resumen-box {{
        background-color: #f4f8fb;
        border: 0.5pt solid #d0e4f0;
        padding: 10pt 12pt;
        font-size: 10.5pt;
        color: #1a1a2e;
        line-height: 1.6;
    }}
    .alert-box {{
        background-color: #fff8f0;
        border-left: 3pt solid #e67e22;
        padding: 6pt 10pt;
        margin-bottom: 5pt;
        font-size: 9.5pt;
    }}
    .conexion-box {{
        background-color: #f0f4ff;
        border-left: 3pt solid #3b82f6;
        padding: 6pt 10pt;
        margin-bottom: 5pt;
        font-size: 9.5pt;
    }}
    .empty-note {{ color: #aab0bc; font-style: italic; font-size: 9.5pt; }}
    .page-header {{
        border-bottom: 1.5pt solid #0d1b2a;
        padding-bottom: 6pt;
        margin-bottom: 16pt;
    }}
    """

    # ── Portada ───────────────────────────────────────────────────────────────
    cover = f"""
    <div style="background-color:#0d1b2a;padding:45pt 50pt 35pt 50pt;page-break-after:always;">

        <p style="font-size:9pt;color:#00b4d8;letter-spacing:2pt;text-transform:uppercase;
                  border-bottom:0.5pt solid #00b4d8;padding-bottom:7pt;margin-bottom:0;">
            OSINTPASSIVE
        </p>

        <div style="height:45pt;"></div>

        <p style="font-size:32pt;color:#ffffff;font-weight:bold;margin:0;line-height:1.1;">Intelligence</p>
        <p style="font-size:32pt;color:#ffffff;font-weight:bold;margin:0 0 8pt 0;line-height:1.1;">Report</p>
        <p style="font-size:10pt;color:#90caf9;margin:0 0 30pt 0;">
            Open Source Intelligence &#xB7; LangGraph + Groq AI
        </p>

        <hr style="border:0;border-top:0.5pt solid #4a6080;margin-bottom:14pt;"/>

        <table style="width:100%;background-color:#0d1b2a;border-collapse:collapse;">
            {_cover_row("Objetivo", _e(target))}
            {_cover_row("Tipo", _e(tipo_label))}
            {_cover_row("Generado", _e(fecha))}
            <tr>
                <td style="color:#90caf9;font-size:8pt;text-transform:uppercase;
                           letter-spacing:1pt;width:90pt;padding:5pt 0;">Criticidad</td>
                <td style="padding:5pt 0;">{badge_html}</td>
            </tr>
        </table>

        <div style="height:30pt;"></div>

        <p style="font-size:7.5pt;color:#4a6080;text-align:right;margin:0;">
            Generado automáticamente &#8212; OSINTPassive v2.0 &#8212; uso exclusivo para investigación autorizada
        </p>
    </div>
    """

    # ── Cabecera de página ────────────────────────────────────────────────────
    page_header = f"""
    <div class="page-header">
        <table style="width:100%;border-collapse:collapse;">
            <tr>
                <td style="padding:0;border:0;font-size:9pt;font-weight:bold;color:#00b4d8;
                           letter-spacing:1.5pt;text-transform:uppercase;">
                    OSINTPassive &#xB7; Intelligence Report
                </td>
                <td style="padding:0;border:0;text-align:right;font-size:8.5pt;color:#7f8c9a;">
                    {_e(target)} &#xB7; {_e(fecha)}
                </td>
            </tr>
        </table>
    </div>
    """

    # ── Resumen ejecutivo ─────────────────────────────────────────────────────
    sec_resumen = f"""
    <div class="section">
        <div class="section-title">Resumen Ejecutivo</div>
        <div class="resumen-box">{_e(resumen)}</div>
    </div>
    """

    # ── Alertas ───────────────────────────────────────────────────────────────
    if alertas:
        items = "".join(f'<div class="alert-box">&#9888; {_e(a)}</div>' for a in alertas)
    else:
        items = '<p class="empty-note">Sin alertas detectadas.</p>'
    sec_alertas = (
        f'<div class="section">'
        f'<div class="section-title">Alertas de Seguridad</div>{items}</div>'
    )

    # ── Conexiones ────────────────────────────────────────────────────────────
    if conexiones:
        items = "".join(f'<div class="conexion-box">&#x2197; {_e(c)}</div>' for c in conexiones)
    else:
        items = '<p class="empty-note">Sin conexiones detectadas.</p>'
    sec_conexiones = (
        f'<div class="section">'
        f'<div class="section-title">Conexiones Detectadas por la IA</div>{items}</div>'
    )

    # ── Emails ────────────────────────────────────────────────────────────────
    if emails:
        rows = "".join(
            f'<tr><td style="width:30pt;">{i + 1}</td><td>{_e(em)}</td></tr>'
            for i, em in enumerate(emails)
        )
        tbl = (
            f'<table><thead><tr><th>#</th><th>Direccion de Email</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
        )
    else:
        tbl = '<p class="empty-note">No se encontraron emails.</p>'
    sec_emails = (
        f'<div class="section">'
        f'<div class="section-title">Emails Encontrados ({len(emails)})</div>{tbl}</div>'
    )

    # ── Usernames ─────────────────────────────────────────────────────────────
    if usernames:
        rows = "".join(
            f'<tr><td style="width:30pt;">{i + 1}</td><td>{_e(u)}</td></tr>'
            for i, u in enumerate(usernames)
        )
        tbl = (
            f'<table><thead><tr><th>#</th><th>Alias / Username</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
        )
    else:
        tbl = '<p class="empty-note">No se encontraron aliases.</p>'
    sec_usernames = (
        f'<div class="section">'
        f'<div class="section-title">Aliases y Usernames ({len(usernames)})</div>{tbl}</div>'
    )

    # ── URLs ──────────────────────────────────────────────────────────────────
    if urls:
        rows = "".join(
            f'<tr><td style="width:30pt;">{i + 1}</td>'
            f'<td style="word-wrap:break-word;">{_e(_truncate(u))}</td></tr>'
            for i, u in enumerate(urls)
        )
        tbl = (
            f'<table><thead><tr><th>#</th><th>URL</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
        )
    else:
        tbl = '<p class="empty-note">No se encontraron URLs.</p>'
    sec_urls = (
        f'<div class="section">'
        f'<div class="section-title">URLs Encontradas ({len(urls)})</div>{tbl}</div>'
    )

    # ── Brechas de datos ──────────────────────────────────────────────────────
    sec_breaches = ""
    if breaches:
        rows = "".join(
            f'<tr><td>{_e(b.get("email", "—"))}</td>'
            f'<td>{_e(b.get("sitio", "—"))}</td>'
            f'<td>{_e(b.get("año", "—"))}</td></tr>'
            for b in breaches
        )
        tbl = (
            f'<table><thead><tr><th>Email</th><th>Sitio</th><th>Año</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
        )
        sec_breaches = (
            f'<div class="section">'
            f'<div class="section-title">Brechas de Datos ({len(breaches)})</div>{tbl}</div>'
        )

    # ── Snapshots Wayback ─────────────────────────────────────────────────────
    sec_snapshots = ""
    if snapshots:
        rows = "".join(
            f'<tr><td style="word-wrap:break-word;">'
            f'{_e(_truncate(s.get("original_url", "—"), 60))}</td>'
            f'<td>{"Reciente" if s.get("type") == "newest_snapshot" else "Antiguo"}</td>'
            f'<td>{_e(s.get("timestamp", "")[:8])}</td></tr>'
            for s in snapshots
        )
        tbl = (
            f'<table><thead><tr><th>URL Original</th><th>Tipo</th><th>Fecha</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
        )
        sec_snapshots = (
            f'<div class="section">'
            f'<div class="section-title">Snapshots Wayback ({len(snapshots)})</div>{tbl}</div>'
        )

    # ── Ensamblado final ──────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8"/>
    <title>OSINTPassive Report — {_e(target)}</title>
    <style>{css}</style>
</head>
<body>

{cover}

<div>
    {page_header}
    {sec_resumen}
    {sec_alertas}
    {sec_conexiones}
    {sec_emails}
    {sec_usernames}
    {sec_urls}
    {sec_breaches}
    {sec_snapshots}
</div>

</body>
</html>"""


# ── Clase pública ─────────────────────────────────────────────────────────────

class OSINTPDFReport:
    """
    Genera un reporte OSINT en PDF (xhtml2pdf) o HTML (fallback).

    Uso:
        pdf_bytes = OSINTPDFReport.generate(state_data)
        with open("report.pdf", "wb") as f:
            f.write(pdf_bytes)
    """

    @staticmethod
    def generate(state_data: dict) -> bytes:
        target    = state_data.get("target_input", "desconocido")
        inp_type  = state_data.get("input_type", "")
        emails    = state_data.get("emails_found", [])
        usernames = state_data.get("usernames_found", [])
        urls      = state_data.get("urls_found", [])
        metadata  = state_data.get("metadata_extracted", [])
        report    = state_data.get("analysis_report") or {}

        resumen    = report.get("resumen", "Sin analisis disponible.")
        conexiones = report.get("conexiones_detectadas", [])
        alertas    = report.get("alertas", [])
        criticidad = report.get("criticidad", "Bajo")

        tipo_label = _TIPO_LABELS.get(
            inp_type,
            inp_type.capitalize() if inp_type else "Desconocido",
        )
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

        breaches  = [m for m in metadata if m.get("tipo") == "data_breach"]
        snapshots = [m for m in metadata if m.get("source") == "wayback"]

        html_content = _build_html(
            target=target,
            tipo_label=tipo_label,
            fecha=fecha,
            criticidad=criticidad,
            resumen=resumen,
            conexiones=conexiones,
            alertas=alertas,
            emails=emails,
            usernames=usernames,
            urls=urls,
            breaches=breaches,
            snapshots=snapshots,
        )

        if PDF_AVAILABLE:
            buf = BytesIO()
            result = _pisa.CreatePDF(html_content, dest=buf, encoding="utf-8")
            if result.err:
                raise RuntimeError(
                    f"xhtml2pdf: {result.err} error(s) al compilar el PDF"
                )
            return buf.getvalue()

        return html_content.encode("utf-8")
