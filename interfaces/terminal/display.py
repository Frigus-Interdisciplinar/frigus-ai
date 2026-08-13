import pyfiglet
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

def exibir_titulo() -> None:

    ascii_art = pyfiglet.figlet_format("FRIGUS.AI", font="doom")
    console.print(f"[cyan]{ascii_art}[/cyan]")
    console.print("[dim]Digite '/exit' para sair.[/dim]\n")


def exibir_usuario(mensagem: str) -> None:

    console.print(Panel(
        Text(mensagem, style="white"),
        title="[bold green]Você[/bold green]",
        title_align="left",
        border_style="green",
    ))


def exibir_assistente(mensagem: str) -> None:

    console.print(Panel(
        Text(mensagem, style="white"),
        title="[bold cyan]Frigus.AI[/bold cyan]",
        title_align="left",
        border_style="cyan",
    ))


__all__ = [
    "exibir_titulo",
    "exibir_usuario",
    "exibir_assistente",
    "console"
]
