"""
Nome em linguagem natural -> item do estoque, pra `update_stock_quantity` e `discard_product`.

`icontains` + "o que vence antes" escolhia sozinho entre "Leite integral" e "Leite de coco", e não
achava "ovos" pra um produto cadastrado como "Ovo": nas duas tools o erro é silencioso e mexe em dado.
Aqui o nome só resolve sozinho quando é inequívoco; no resto o JeV escolhe entre os itens do próprio
estoque do usuário, e sem convicção a tool devolve a pergunta pro usuário em vez de adivinhar.
"""

import asyncio
import unicodedata

from frigus_ai.infra.llm import jev
from frigus_ai.infra.llm.jev.schemas import PerguntaEscolha
from frigus_ai.infra.logging import Logging
from frigus_ai.repositories import estoque_repository
from frigus_ai.repositories.estoque_repository import ItemEstoque
from frigus_ai.settings import settings

logger = Logging.get_logger("pg_estoque")

_NENHUM = "nenhum"
_MAX_OPCOES = 254  # o limite do JeV é 255, e uma vaga é do "nenhum"


class NomeAmbiguo(Exception):
    """Mais de um item (ou nenhum com segurança) bate com o nome; a mensagem é a pergunta pro usuário."""


def _chave(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.strip().lower()


def _descricao(item: ItemEstoque) -> str:
    return f"{item['product_name']} (vence {item['expire_date']})"


def _perguntar_ao_usuario(nome: str, candidatos: list[ItemEstoque]) -> NomeAmbiguo:
    lista = "; ".join(_descricao(i) for i in candidatos[:5])
    return NomeAmbiguo(
        f"Não sei qual item é '{nome}'. Opções: {lista}. Pergunte ao usuário qual deles (use 'esclarecer')."
    )


def _escolher(nome: str, candidatos: list[ItemEstoque]) -> int | None:
    """Id do item que o JeV acha que o usuário quis dizer, None se ele disse que nenhum serve."""

    por_id = {str(i["stock_product_id"]): i for i in candidatos}
    decisoes = asyncio.run(jev.decidir(
        "estoque_nome",
        f'O usuário se referiu a um produto do estoque como "{nome}".',
        [PerguntaEscolha(
            name="item",
            instructions="Qual item do estoque o usuário quis dizer? Escolha 'nenhum' se nenhum corresponde.",
            choices={**{k: _descricao(v) for k, v in por_id.items()}, _NENHUM: "nenhum dos itens da lista"},
            dinamica=True,
        )],
    ))
    escolha = decisoes.escolha("item")

    # Sem probabilidades do gateway, vale a escolha; com elas, exige convicção.
    chance = decisoes.probabilidade_da_opcao("item", escolha)
    if chance is not None and chance < settings.llm.confianca_minima_nome:
        raise _perguntar_ao_usuario(nome, candidatos)

    return None if escolha == _NENHUM else int(escolha)


def resolver_item(stock_id: int, nome: str) -> int | None:
    """
    Id do item do estoque, ou None pra deixar o repository tentar (e falhar com "não encontrado").
    Levanta `NomeAmbiguo` quando não dá pra escolher sem arriscar o item errado.
    """

    # Já vem ordenado pela validade: o primeiro de cada produto é o que vence antes.
    por_produto: dict[str, ItemEstoque] = {}
    for item in estoque_repository.consultar_estoque(stock_id, {}):
        por_produto.setdefault(_chave(item["product_name"]), item)

    alvo = _chave(nome)
    if exato := por_produto.get(alvo):
        return exato["stock_product_id"]

    parecidos = [item for chave, item in por_produto.items() if alvo in chave]
    if len(parecidos) == 1:
        return parecidos[0]["stock_product_id"]

    candidatos = parecidos or list(por_produto.values())
    if not candidatos or len(candidatos) > _MAX_OPCOES or not jev.disponivel():
        # Sem JeV, vários parecidos é ambíguo; sem nenhum, o repository diz "não encontrado".
        if len(parecidos) > 1:
            raise _perguntar_ao_usuario(nome, parecidos)
        return None

    try:
        escolhido = _escolher(nome, candidatos)
    except NomeAmbiguo:
        raise
    except Exception as e:
        logger.warning("Resolução de nome '%s' pelo JeV falhou: %s", nome, e)
        if len(parecidos) > 1:
            raise _perguntar_ao_usuario(nome, parecidos) from e
        return None

    if escolhido is None and len(parecidos) > 1:
        raise _perguntar_ao_usuario(nome, parecidos)

    return escolhido


__all__ = ["NomeAmbiguo", "resolver_item"]
