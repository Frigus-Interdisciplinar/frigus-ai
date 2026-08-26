import logging
from typing import ClassVar
from uuid import uuid4

import pyfiglet
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Footer, Input, RichLog, Static

from config.docker import garantir_banco
from frigus_ai.chat import service
from interfaces.tui.display import Bubble, MessageRow, Pensando


class _LogWidgetHandler(logging.Handler):
    """Redireciona registros de logging pra um RichLog em vez de stderr."""

    def __init__(self, widget: RichLog) -> None:
        super().__init__()
        self._widget = widget

    def emit(self, record: logging.LogRecord) -> None:
        self._widget.write(self.format(record))


class FrigusTUI(App):
    CSS_PATH = "app.tcss"
    BINDINGS: ClassVar = [("ctrl+c", "sair", "Sair")]

    def __init__(self) -> None:
        super().__init__()
        self.user_id = service.DEMO_USER_ID
        self.session_id = str(uuid4())
        self.stock_id: int | None = None

    def compose(self) -> ComposeResult:
        arte = pyfiglet.figlet_format("FRIGUS.AI", font="doom")
        yield Static(Text(arte, style="#70A2D7"), id="banner")  # --color-frigus-light-blue
        yield VerticalScroll(id="historico")
        yield Input(placeholder="Digite sua mensagem... (/exit para sair)")
        yield RichLog(id="logs", max_lines=200, highlight=False, markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self._redirecionar_logs()
        self.stock_id = service.iniciar_sessao(self.user_id)

    def _redirecionar_logs(self) -> None:
        handler = _LogWidgetHandler(self.query_one("#logs", RichLog))
        handler.setFormatter(
            logging.Formatter("%(levelname)s | %(name)s | %(message)s")
        )

        for nome in list(logging.root.manager.loggerDict):
            logger = logging.getLogger(nome)
            logger.handlers.clear()
            logger.propagate = True

        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(logging.INFO)

    async def on_input_submitted(self, evento: Input.Submitted) -> None:
        texto = evento.value.strip()
        evento.input.clear()

        if not texto:
            return

        if texto == "/exit":
            await self.action_sair()
            return

        await self._enviar(texto)

    async def _enviar(self, texto: str) -> None:
        historico = self.query_one("#historico", VerticalScroll)
        input_widget = self.query_one(Input)

        await historico.mount(MessageRow(Bubble(texto, "usuario"), classes="usuario"))
        indicador = Pensando(classes="pensando")
        await historico.mount(indicador)
        historico.scroll_end(animate=False)

        input_widget.disabled = True
        self._processar(texto, indicador)

    @work(thread=True)
    def _processar(self, texto: str, indicador: Pensando) -> None:
        try:
            resposta = service.send_message(
                texto,
                session_id=self.session_id,
                user_id=self.user_id,
                stock_id=self.stock_id,
            )
        except Exception as e:
            resposta = f"Erro: {e}"

        self.call_from_thread(self._exibir_resposta, indicador, resposta)

    def _exibir_resposta(self, indicador: Pensando, resposta: str) -> None:
        historico = self.query_one("#historico", VerticalScroll)
        indicador.remove()
        historico.mount(
            MessageRow(Bubble(resposta, "assistente"), classes="assistente")
        )
        historico.scroll_end(animate=False)

        input_widget = self.query_one(Input)
        input_widget.disabled = False
        input_widget.focus()

    async def action_sair(self) -> None:
        service.encerrar_sessao(self.session_id, self.user_id)
        self.exit()


def run() -> None:
    garantir_banco()
    FrigusTUI().run()


__all__ = ["FrigusTUI", "run"]
