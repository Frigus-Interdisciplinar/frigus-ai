"""
JeV (TypeSafe) pela Decisions API do Vercel AI Gateway: responde perguntas fechadas (predicado,
escolha, nota) com probabilidade, sem gerar texto — mais barato e rápido que um LLM pra decidir.

Se o JeV falhar, o próprio gateway responde com o modelo de reserva. Qualquer outra falha (rede,
HTTP != 2xx, corpo fora do schema, recusa, opção fora da lista) levanta: quem chama decide o fallback.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import httpx

from frigus_ai.infra.llm.jev.schemas import (
    Escolha,
    MensagemUsuario,
    Nota,
    ParteImagem,
    ParteTexto,
    PedidoDecisao,
    Pergunta,
    PerguntaEscolha,
    Predicado,
    Recusa,
    RespostaDecisao,
)
from frigus_ai.settings import settings
from frigus_ai.settings.llm import Model
from frigus_ai.telemetry.metrics import (
    JEV_CONFIDENCE,
    JEV_DECISIONS,
    LLM_COST,
    LLM_TOKENS,
    medir_externo,
)
from frigus_ai.telemetry.metrics_callback import custo_usd


@dataclass(frozen=True)
class Decisoes:
    """Respostas de uma requisição, por nome da pergunta."""

    respostas: Mapping[str, Predicado | Escolha | Nota]

    def escolha(self, nome: str) -> str:
        match self.respostas[nome]:
            case Escolha(choice=valor):
                return valor
            case outra:
                raise TypeError(f"{nome} não é escolha: {outra}")

    def sim(self, nome: str) -> bool:
        return self.probabilidade(nome) >= 0.5

    def probabilidade(self, nome: str) -> float:
        """De a resposta de um predicado ser "sim"."""

        match self.respostas[nome]:
            case Predicado(probability=probabilidade):
                return probabilidade
            case outra:
                raise TypeError(f"{nome} não é predicado: {outra}")

    def probabilidade_da_opcao(self, nome: str, opcao: str) -> float | None:
        """De a `opcao` ser a certa numa escolha; None se o gateway não mandou as probabilidades."""

        match self.respostas[nome]:
            case Escolha(probabilities=opcoes) if opcoes:
                return next((o.probability for o in opcoes if o.value == opcao), 0.0)
            case Escolha():
                return None
            case outra:
                raise TypeError(f"{nome} não é escolha: {outra}")


def disponivel() -> bool:
    return bool(settings.llm.gateway.api_key)


def _medir(uso: str, pergunta: str, modelo: str, escolha: str, confianca: float | None = None) -> None:
    JEV_DECISIONS.labels(uso=uso, pergunta=pergunta, escolha=escolha, modelo=modelo).inc()
    if confianca is not None:
        JEV_CONFIDENCE.labels(uso=uso).observe(confianca)


def _validar(
    uso: str, modelo: str, resposta: Predicado | Escolha | Nota | Recusa, pergunta: Pergunta
) -> Predicado | Escolha | Nota:
    opcoes = {o.value for o in pergunta.choices} if isinstance(pergunta, PerguntaEscolha) else set()

    match resposta:
        case Escolha(choice=valor, confidence=confianca) if valor in opcoes:
            _medir(uso, resposta.name, modelo, "opcao" if pergunta.dinamica else valor, confianca)
        
        case Predicado(probability=probabilidade):
            _medir(uso, resposta.name, modelo, "sim" if resposta.sim else "nao", max(probabilidade, 1 - probabilidade))
        
        case Nota(score=nota, confidence=confianca):
            _medir(uso, resposta.name, modelo, str(round(nota)), confianca)
        
        case Escolha():
            _medir(uso, resposta.name, modelo, "invalida")
            raise ValueError(f"JeV escolheu fora das opções: {resposta}")
        
        case Recusa():
            _medir(uso, resposta.name, modelo, "recusa")
            raise ValueError(f"JeV recusou a pergunta {resposta.name}")

    return resposta


async def decidir(
    uso: str, entrada: str, perguntas: Sequence[Pergunta], imagem_b64: str | None = None
) -> Decisoes:
    """Faz todas as `perguntas` sobre a mesma `entrada` numa requisição só. `uso` separa as métricas
    por quem pergunta (ex.: `guardrail_entrada`). Com `imagem_b64` (JPEG), as perguntas valem pra
    foto também: o JeV é só texto e dá 400, então vai direto na Luna, sem reserva."""

    if imagem_b64:
        pedido = PedidoDecisao(
            model=Model.GPT_6_LUNA_DECISIONS,
            input=[MensagemUsuario(content=[
                ParteTexto(text=entrada),
                ParteImagem(image_url=f"data:image/jpeg;base64,{imagem_b64}"),
            ])],
            questions=list(perguntas),
        )
    else:
        pedido = PedidoDecisao(
            model=Model.JEV,
            input=entrada,
            questions=list(perguntas),
            provider_options={"gateway": {"models": [Model.GPT_6_LUNA_DECISIONS]}},
        )
    chave = settings.llm.gateway.api_key.get_secret_value()
    # Foto é a chamada pesada: o teto de saída curta não serve.
    timeout = settings.llm.timeout_visao_s if imagem_b64 else settings.llm.timeout_curto_s

    with medir_externo("jev"):
        async with httpx.AsyncClient(timeout=timeout) as client:
            resposta = await client.post(
                f"{settings.llm.gateway.base_url}/decisions",
                json=pedido.model_dump(mode="json", by_alias=True, exclude_none=True),
                headers={"Authorization": f"Bearer {chave}"},
            )
            resposta.raise_for_status()
    corpo = RespostaDecisao.model_validate_json(resposta.content)

    # HTTP direto não passa pelo callback do LangChain: o custo entra nas métricas daqui.
    tokens = corpo.usage.get("input_tokens", 0)
    LLM_TOKENS.labels(provider="gateway", model=corpo.model, direction="input").inc(tokens)
    # O gateway informa o custo real; a tabela local é só o plano B.
    custo = corpo.provider_metadata.get("gateway", {}).get("cost")
    LLM_COST.labels(provider="gateway", model=corpo.model).inc(
        float(custo) if custo is not None else custo_usd(corpo.model, tokens, 0)
    )

    por_nome = {p.name: p for p in perguntas}
    return Decisoes({r.name: _validar(uso, corpo.model, r, por_nome[r.name]) for r in corpo.answers})


async def escolher[T: str](uso: str, entrada: str, instrucoes: str, opcoes: Mapping[T, str]) -> T:
    """Atalho pra uma pergunta só: qual chave de `opcoes` (opção → descrição) o modelo escolheu."""

    decisoes = await decidir(uso, entrada, [PerguntaEscolha(name="escolha", instructions=instrucoes, choices=opcoes)])
    return {str(o): o for o in opcoes}[decisoes.escolha("escolha")]


__all__ = ["Decisoes", "decidir", "disponivel", "escolher"]
