import logging
import os
import warnings
from uuid import uuid4

from frigus_ai.chat import service

from config.docker import garantir_banco
from interfaces.terminal.display import console, exibir_assistente, exibir_titulo, exibir_usuario

# --------------------- FIX WARNING ---------------------
warnings.filterwarnings("ignore", message="Deserializing unregistered type")
logging.getLogger("langgraph").setLevel(logging.ERROR)
# --------------------- FIX WARNING ---------------------


def run() -> None:
    os.system("cls")

    garantir_banco()
    exibir_titulo()

    user_id = service.DEMO_USER_ID
    session_id = str(uuid4())
    stock_id = service.iniciar_sessao(user_id)

    while True:
        try:
            user_input = console.input("[bold green]>[/bold green] ").strip()

            if user_input == "/exit":
                service.encerrar_sessao(session_id, user_id)
                console.print("\n[dim]Encerrando...[/dim]")
                break

            if not user_input:
                continue

            exibir_usuario(user_input)
            resposta = service.send_message(user_input, session_id=session_id, user_id=user_id, stock_id=stock_id)
            exibir_assistente(resposta)

        except KeyboardInterrupt:
            service.encerrar_sessao(session_id, user_id)
            console.print("\n[dim]Encerrando...[/dim]")
            break
        except Exception as e:
            console.print(f"[bold red]Erro:[/bold red] {e}")
