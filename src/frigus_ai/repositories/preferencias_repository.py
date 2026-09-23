"""
Persistência crua das preferências alimentares do usuário: usa o grafo Neo4j direto
(User -[:PREFERS/DISLIKES/ALLERGIC_TO]-> Ingredient), sem tradução pra `Response` —
isso fica em `graph/tools/preferencias/repo.py` (a tool que o LLM chama).

`user_id` aqui já é o uid do node User no Neo4j (convenção de seed: "user-{id}").
Quem resolve o Postgres user_id pro uid do grafo é a tool, não este módulo.

Async de ponta a ponta (`AsyncStructuredNode`/`adb`, não `StructuredNode`/`db` +
`asyncio.to_thread`): o driver oficial do Neo4j já é async nativo, então não há
chamada bloqueante nenhuma pra empurrar pra thread — ao contrário de Postgres/Mongo
(`psycopg2`/`pymongo`, síncronos de verdade), aqui `to_thread` só adicionaria
overhead sem motivo.
"""

from typing import Literal, TypedDict

from neomodel import adb

from frigus_ai.exceptions import IngredienteNaoEncontrado
from frigus_ai.infra.neo4j.models.ingredient import Ingredient
from frigus_ai.infra.neo4j.models.user import User

type TipoPreferencia = Literal["prefers", "dislikes", "allergic_to"]


class Preferencias(TypedDict):
    prefers: list[str]
    dislikes: list[str]
    allergic_to: list[str]


class ReceitaCompativel(TypedDict):
    recipe_id: str
    name: str
    preparation_time_minutes: int
    difficulty: str


async def _ingrediente(nome: str) -> Ingredient:
    ingrediente = await Ingredient.nodes.first_or_none(name=nome)

    if ingrediente is None:
        raise IngredienteNaoEncontrado(nome)

    return ingrediente


async def _buscar_usuario(user_id: str) -> User | None:
    return await User.nodes.first_or_none(uid=user_id)


async def _obter_ou_criar_usuario(user_id: str) -> User:
    """
    `uid` (`UniqueIdProperty`) não é propriedade obrigatória do model — sem
    `merge_by` explícito, o MERGE usaria `__required_properties__` (só `name`) como
    chave, o que faria dois usuários com o mesmo nome colidirem no mesmo node.
    """

    usuarios = await User.nodes.bulk_get_or_create(
        {"uid": user_id, "name": user_id}, merge_by={"keys": ["uid"]}
    )
    return usuarios[0]


class _PreferenciasNeo4jRepo:
    async def listar_preferencias(self, user_id: str) -> Preferencias:
        """Nomes dos ingredientes nas três relações do usuário, uma lista por tipo."""

        user = await _buscar_usuario(user_id)
        if user is None:
            return Preferencias(prefers=[], dislikes=[], allergic_to=[])

        return Preferencias(
            prefers=[i.name for i in await user.prefers.all()],
            dislikes=[i.name for i in await user.dislikes.all()],
            allergic_to=[i.name for i in await user.allergic_to.all()],
        )

    async def definir_preferencia(
        self, user_id: str, ingrediente_nome: str, tipo: TipoPreferencia
    ) -> None:
        """
        Conecta o usuário ao ingrediente pela relação `tipo`; não duplica se já
        conectado. Cria o node do usuário no grafo na primeira preferência dele —
        não existe sync automático Postgres → Neo4j pra usuário ainda.
        """

        user = await _obter_ou_criar_usuario(user_id)
        ingrediente = await _ingrediente(ingrediente_nome)

        relacao = getattr(user, tipo)

        if not await relacao.is_connected(ingrediente):
            await relacao.connect(ingrediente)

    async def remover_preferencia(
        self, user_id: str, ingrediente_nome: str, tipo: TipoPreferencia
    ) -> None:
        """Desconecta o usuário do ingrediente pela relação `tipo`; no-op se não
        conectado (inclusive quando o usuário ainda não tem node no grafo)."""

        user = await _buscar_usuario(user_id)
        if user is None:
            return

        ingrediente = await _ingrediente(ingrediente_nome)
        relacao = getattr(user, tipo)

        if await relacao.is_connected(ingrediente):
            await relacao.disconnect(ingrediente)

    async def receitas_sem_restricoes(self, user_id: str, limit: int) -> list[ReceitaCompativel]:
        """
        Receitas cujos ingredientes não colidem com o que o usuário não gosta ou é
        alérgico. Cypher cru, não OGM: `WHERE NOT EXISTS { dois MATCH aninhados }`
        não tem equivalente no query builder do neomodel.
        """

        query = """
            MATCH (r:Recipe)
            WHERE NOT EXISTS {
                MATCH (r)-[:REQUIRES]->(i:Ingredient)
                MATCH (:User {id: $user_id})-[:DISLIKES|ALLERGIC_TO]->(i)
            }
            RETURN r.id AS recipe_id, r.name AS name,
                   r.preparation_time_minutes AS preparation_time_minutes,
                   r.difficulty AS difficulty
            LIMIT $limit
        """
        resultados, _ = await adb.cypher_query(query, {"user_id": user_id, "limit": limit})

        return [
            {
                "recipe_id": recipe_id,
                "name": name,
                "preparation_time_minutes": tempo,
                "difficulty": dificuldade,
            }
            for recipe_id, name, tempo, dificuldade in resultados
        ]


_preferencias = _PreferenciasNeo4jRepo()


async def listar_preferencias(user_id: str) -> Preferencias:
    return await _preferencias.listar_preferencias(user_id)


async def definir_preferencia(user_id: str, ingrediente_nome: str, tipo: TipoPreferencia) -> None:
    await _preferencias.definir_preferencia(user_id, ingrediente_nome, tipo)


async def remover_preferencia(user_id: str, ingrediente_nome: str, tipo: TipoPreferencia) -> None:
    await _preferencias.remover_preferencia(user_id, ingrediente_nome, tipo)


async def receitas_sem_restricoes(user_id: str, limit: int = 10) -> list[ReceitaCompativel]:
    return await _preferencias.receitas_sem_restricoes(user_id, limit)


__all__ = [
    "Preferencias",
    "ReceitaCompativel",
    "TipoPreferencia",
    "definir_preferencia",
    "listar_preferencias",
    "receitas_sem_restricoes",
    "remover_preferencia",
]
