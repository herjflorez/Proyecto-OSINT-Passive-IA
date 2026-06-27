from langgraph.graph import END, START, StateGraph

from core.agents.alias_agent import alias_agent
from core.agents.analyst_agent import analyst_agent
from core.agents.breach_agent import breach_agent
from core.agents.dork_agent import dork_agent
from core.agents.github_agent import github_agent
from core.agents.wayback_agent import wayback_agent
from core.state import OSINTState
from core.validator import validator_node


def build_graph():
    graph = StateGraph(OSINTState)

    graph.add_node("validator_node", validator_node)
    graph.add_node("github_agent",   github_agent)
    graph.add_node("dork_agent",     dork_agent)
    graph.add_node("alias_agent",    alias_agent)
    graph.add_node("wayback_agent",  wayback_agent)
    graph.add_node("breach_agent",   breach_agent)
    graph.add_node("analyst_agent",  analyst_agent)

    # Validación primero
    graph.add_edge(START, "validator_node")

    # Capa 1 — recolectores en paralelo (tras validación)
    graph.add_edge("validator_node", "github_agent")
    graph.add_edge("validator_node", "dork_agent")
    graph.add_edge("validator_node", "alias_agent")

    # Capa 2 — wayback y breach en paralelo (fan-in desde capa 1)
    graph.add_edge("github_agent", "wayback_agent")
    graph.add_edge("dork_agent",   "wayback_agent")
    graph.add_edge("alias_agent",  "wayback_agent")

    graph.add_edge("github_agent", "breach_agent")
    graph.add_edge("dork_agent",   "breach_agent")
    graph.add_edge("alias_agent",  "breach_agent")

    # Capa 3 — análisis final (fan-in desde capa 2)
    graph.add_edge("wayback_agent", "analyst_agent")
    graph.add_edge("breach_agent",  "analyst_agent")

    graph.add_edge("analyst_agent", END)

    return graph.compile()


osint_graph = build_graph()
