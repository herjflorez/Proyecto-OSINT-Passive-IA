"""
Ejecución del grafo OSINT con streaming de eventos en tiempo real.

Publica eventos (start / end / done / error) a través de un generador síncrono
que puede ser consumido directamente en Streamlit sin bloquear el event loop.
"""

import asyncio
import queue
import threading
from typing import Generator

from core.graph import osint_graph
from core.state import dedup_strings, dedup_urls

# Etiquetas para mostrar en la UI por nombre de nodo
AGENT_LABELS: dict[str, tuple[str, str]] = {
    "validator_node": ("✅", "Validando y clasificando input"),
    "github_agent":   ("🔍", "GitHub: escaneando commits públicos"),
    "dork_agent":     ("🌐", "DuckDuckGo: rastreando huellas digitales"),
    "alias_agent":    ("👤", "Verificando perfiles en 10 plataformas"),
    "wayback_agent":  ("📅", "Wayback Machine: consultando historial"),
    "breach_agent":   ("🔓", "LeakCheck: verificando brechas de datos"),
    "analyst_agent":  ("🧠", "IA: generando análisis de inteligencia"),
}


def _apply_update(current: dict, update: dict) -> dict:
    """Aplica la salida parcial de un nodo al estado acumulado usando los reducers correctos."""
    result = dict(current)
    for key, value in update.items():
        if not isinstance(value, list):
            result[key] = value  # last-write-wins para campos escalares
        elif key in ("emails_found", "usernames_found"):
            result[key] = dedup_strings(result.get(key, []), value)
        elif key == "urls_found":
            result[key] = dedup_urls(result.get(key, []), value)
        else:  # metadata_extracted, raw_logs → append
            result[key] = result.get(key, []) + value
    return result


def stream_investigation(initial_state: dict) -> Generator[tuple, None, None]:
    """
    Generador síncrono que ejecuta el grafo con astream_events(version="v2").

    Yields:
        ("start", node_name, {})        — cuando un nodo comienza a ejecutarse
        ("end",   node_name, output)    — cuando un nodo termina (output = dict parcial)
        ("done",  "",        final_state) — cuando el grafo ha terminado
        ("error", msg,       {})        — si ocurre una excepción

    El caller no necesita llamar a ainvoke por separado: el estado final
    llega en el evento "done".
    """
    q: queue.Queue = queue.Queue()
    error_holder: list[Exception | None] = [None]

    async def _run() -> None:
        current = dict(initial_state)
        try:
            async for event in osint_graph.astream_events(initial_state, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")

                if name not in AGENT_LABELS:
                    continue

                if kind == "on_chain_start":
                    q.put(("start", name, {}))

                elif kind == "on_chain_end":
                    output = event.get("data", {}).get("output") or {}
                    if isinstance(output, dict):
                        current = _apply_update(current, output)
                    q.put(("end", name, output if isinstance(output, dict) else {}))

            q.put(("done", "", current))

        except Exception as exc:
            error_holder[0] = exc
            q.put(("error", str(exc), {}))

    thread = threading.Thread(target=lambda: asyncio.run(_run()), daemon=True)
    thread.start()

    while True:
        item = q.get()
        yield item
        if item[0] in ("done", "error"):
            break

    thread.join()

    if error_holder[0]:
        raise error_holder[0]
