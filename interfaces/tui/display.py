from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import LoadingIndicator, Static

# Cores do design system do Frigus (globals.css) — ver app.tcss pro resto da paleta.
_ESTILO = {
    "usuario": ("Você", "#70A2D7"),        # --color-frigus-light-blue
    "assistente": ("Frigus.AI", "#F9C968"),  # --color-frigus-accent
}


class Bubble(Static):
    """Uma mensagem no histórico do chat, no mesmo estilo de Panel do terminal."""

    def __init__(self, texto: str, tipo: str) -> None:
        titulo, cor = _ESTILO[tipo]
        painel = Panel(
            Text(texto, style="white"),
            title=f"[bold {cor}]{titulo}[/bold {cor}]",
            title_align="left",
            border_style=cor,
        )
        super().__init__(painel, classes=tipo)


class MessageRow(Horizontal):
    """Linha que alinha uma Bubble à direita (usuário) ou à esquerda (assistente)."""


class Pensando(Horizontal):
    """Indicador de carregamento (bolinhas) enquanto o assistente responde."""

    def compose(self) -> ComposeResult:
        yield LoadingIndicator()


__all__ = ["Bubble", "MessageRow", "Pensando"]
