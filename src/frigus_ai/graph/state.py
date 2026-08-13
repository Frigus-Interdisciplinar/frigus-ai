import operator
from typing import Annotated, Optional
from langgraph.graph import MessagesState
from enum import StrEnum


class Route(StrEnum):
    ESTOQUE           = "estoque"
    COMPRAS           = "compras"
    RECEITAS          = "receitas"
    FAQ               = "faq"
    FINANCEIRO        = "financeiro"
    FIM               = "fim"
    GUARDRAIL_ENTRADA = "guardrail_entrada"
    GUARDRAIL_SAIDA   = "guardrail_saida"
    JUIZ              = "juiz"


class Estado(MessagesState):
    resposta_especialista: str
    dados_especialista:    str  # saída crua do especialista (JSON/RAG), preservada mesmo após o Orquestrador reformatar resposta_especialista — usada pelo Juiz para checar grounding
    agentes_chamados:      Annotated[list[str], operator.add]
    rota:                  Route
    pergunta_original:     str
    mapa_pii:              dict
    mensagem_bloqueada:    str
    perfil_usuario:        str
    stock_id:              Optional[int]

    # Juiz (LLM-as-judge)
    tentativas_juiz:  int
    veredito_juiz:    str
    justificativa_juiz: str
    feedback_juiz:    str
