from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from config.settings import GROQ_API_KEY, GROQ_MODEL
from core.state import OSINTState

SYSTEM_PROMPT = """Eres un analista experto en ciberseguridad e inteligencia OSINT (Open Source Intelligence).
Tu misión es analizar los datos recopilados sobre un objetivo digital y producir un informe de inteligencia estructurado.

Instrucciones:
- Identifica correlaciones entre emails, usernames, URLs y metadatos recopilados.
- Detecta posibles brechas: emails expuestos en repositorios públicos, patrones de username reutilizados entre plataformas, subdominios o rutas sensibles indexadas.
- Evalúa el riesgo real y práctico para la privacidad y seguridad del objetivo.
- Asigna criticidad proporcional a la cantidad, sensibilidad y correlación de los datos hallados:
    Bajo  → datos mínimos o no correlacionables.
    Medio → datos correlacionables que exponen presencia digital significativa.
    Alto  → datos que permiten perfilar al objetivo, acceder a cuentas o ejecutar ataques dirigidos.
- Sé técnico, conciso y objetivo. No especules sin evidencia en los datos."""


class ReporteOSINT(BaseModel):
    resumen: str = Field(description="Resumen ejecutivo de los hallazgos del análisis OSINT")
    conexiones_detectadas: list[str] = Field(
        description="Correlaciones identificadas entre los datos recopilados"
    )
    alertas: list[str] = Field(
        description="Posibles brechas de seguridad, datos sensibles o riesgos detectados"
    )
    criticidad: Literal["Bajo", "Medio", "Alto"] = Field(
        description="Nivel de criticidad global de la exposición detectada"
    )


def _build_user_message(state: OSINTState) -> str:
    emails = "\n".join(f"  - {e}" for e in state["emails_found"]) or "  (ninguno)"
    usernames = "\n".join(f"  - {u}" for u in state["usernames_found"]) or "  (ninguno)"
    urls = "\n".join(f"  - {u}" for u in state["urls_found"]) or "  (ninguna)"
    meta = "\n".join(
        f"  - [{m.get('source', '?')}] {m.get('title', 'sin título')} → {m.get('url', '')}"
        for m in state["metadata_extracted"]
    ) or "  (ninguno)"

    return f"""Analiza el siguiente perfil OSINT y genera el informe estructurado:

TARGET: {state['target_input']} (tipo: {state['input_type']})

EMAILS ENCONTRADOS ({len(state['emails_found'])}):
{emails}

USERNAMES ENCONTRADOS ({len(state['usernames_found'])}):
{usernames}

URLs ENCONTRADAS ({len(state['urls_found'])}):
{urls}

METADATOS ({len(state['metadata_extracted'])} registros):
{meta}"""


async def analyst_agent(state: OSINTState) -> dict:
    logs: list[str] = []

    try:
        llm = ChatGroq(api_key=GROQ_API_KEY, model=GROQ_MODEL, temperature=0)
        chain = llm.with_structured_output(ReporteOSINT)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=_build_user_message(state)),
        ]

        reporte: ReporteOSINT = await chain.ainvoke(messages)
        logs.append(f"[ANALYST] Análisis completado. Criticidad: {reporte.criticidad}")

        return {
            "analysis_report": reporte.model_dump(),
            "raw_logs": logs,
        }

    except Exception as e:
        logs.append(f"[ANALYST] Error durante el análisis: {e}")
        return {
            "analysis_report": {
                "resumen": "Error durante el análisis LLM.",
                "conexiones_detectadas": [],
                "alertas": [str(e)],
                "criticidad": "Bajo",
            },
            "raw_logs": logs,
        }
