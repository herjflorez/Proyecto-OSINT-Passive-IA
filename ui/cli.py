import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich import box

from core.graph import osint_graph

console = Console()

BANNER = """
  ___  ___  ___  _  _ _____   ___   _   ___ ___ _____   _____
 / _ \/ __|_ _|| \| |_   _| | _ \ /_\ / __/ __|_ _\ \ / / __|
| (_) \__ \| | | .` | | |   |  _// _ \\__ \__ \| | \ V /| _|
 \___/|___/___||_|\_| |_|   |_| /_/ \_\___/___/___| \_/ |___|

         Inteligencia OSINT con LangGraph + Groq AI
"""


def _detect_input_type(target: str) -> str:
    if "@" in target:
        return "email"
    if "." in target and " " not in target:
        return "domain"
    return "name"


def _display_results(state: dict) -> None:
    report = state.get("analysis_report", {})

    console.print()
    console.print(Rule("[bold cyan]ANÁLISIS DE INTELIGENCIA[/bold cyan]"))

    criticidad = report.get("criticidad", "N/A")
    color = {"Alto": "red", "Medio": "yellow", "Bajo": "green"}.get(criticidad, "white")

    console.print(Panel(
        f"[bold {color}]Criticidad: {criticidad}[/bold {color}]\n\n"
        + report.get("resumen", "Sin resumen disponible."),
        title="[bold]Resumen Ejecutivo[/bold]",
        border_style=color,
        padding=(1, 2),
    ))

    conexiones = report.get("conexiones_detectadas", [])
    if conexiones:
        console.print()
        console.print(Panel(
            "\n".join(f"  [cyan]▸[/cyan] {c}" for c in conexiones),
            title="[bold]Conexiones Detectadas[/bold]",
            border_style="cyan",
        ))

    alertas = report.get("alertas", [])
    if alertas:
        console.print()
        console.print(Panel(
            "\n".join(f"  [red]⚠[/red]  {a}" for a in alertas),
            title="[bold red]Alertas de Seguridad[/bold red]",
            border_style="red",
        ))

    emails = state.get("emails_found", [])
    urls = state.get("urls_found", [])

    if emails or urls:
        console.print()
        table = Table(box=box.ROUNDED, border_style="dim", show_header=True)
        table.add_column("Tipo", style="bold", width=12)
        table.add_column("Valor encontrado")
        for e in emails:
            table.add_row("[green]Email[/green]", e)
        for u in urls:
            table.add_row("[blue]URL[/blue]", u)
        console.print(table)

    logs = state.get("raw_logs", [])
    if logs:
        console.print()
        console.print(Rule("[dim]Log de ejecución[/dim]", style="dim"))
        for log in logs:
            console.print(f"  [dim]{log}[/dim]")


async def _run_investigation(target: str, input_type: str) -> dict:
    state = {
        "target_input": target,
        "input_type": input_type,
        "emails_found": [],
        "usernames_found": [],
        "urls_found": [],
        "metadata_extracted": [],
        "raw_logs": [],
    }
    return await osint_graph.ainvoke(state)


def main() -> None:
    console.print(Panel(BANNER, border_style="cyan", padding=(0, 2)))
    console.print()

    target = Prompt.ask(
        "[bold cyan]  Introduce el objetivo[/bold cyan] (email, dominio o nombre)",
        console=console,
    ).strip()

    if not target:
        console.print("[red]Input vacío. Saliendo.[/red]")
        sys.exit(1)

    input_type = _detect_input_type(target)
    console.print(f"\n  Tipo detectado: [bold yellow]{input_type}[/bold yellow]")
    console.print()

    with console.status(
        "[bold cyan]Ejecutando investigación OSINT...[/bold cyan]",
        spinner="dots",
    ):
        result = asyncio.run(_run_investigation(target, input_type))

    _display_results(result)
    console.print()


if __name__ == "__main__":
    main()
