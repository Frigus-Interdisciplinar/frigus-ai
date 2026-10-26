"""
Projeção das receitas locais no Neo4j (`Recipe -[:REQUIRES]-> Ingredient`) e consulta de sugestão por
estoque e vencimento. O Postgres é a fonte. Chaves estáveis (`local:<id>`, `product:<id>`) com
MERGE: sincronizar de novo não duplica nó nem relação.

A escrita usa os models do neomodel; a consulta é Cypher cru porque `none()`/`any()`/list
comprehension não existem no query builder (mesma razão de `preferencias_repository`).
"""

import hashlib
import json

from frigus_ai.infra.neo4j.connection import neo4j
from frigus_ai.infra.neo4j.models.ingredient import Ingredient
from frigus_ai.infra.neo4j.models.recipe import Recipe
from frigus_ai.repositories.receitas_repository import ReceitaComIngredientes

_labels_instalados = False

# Zera a impressão digital junto: se a receita voltar ao catálogo igual, tem que ser reenviada.
_DESATIVAR_AUSENTES = """
MATCH (r:Recipe {source: 'local'})
WHERE NOT r.key IN $keys
SET r.ingredients_complete = false, r.fingerprint = null
"""

_IMPRESSOES = "MATCH (r:Recipe {source: 'local'}) RETURN r.key, r.fingerprint"

_SUGERIR = """
MATCH (r:Recipe {source: 'local'})-[:REQUIRES]->(i:Ingredient)
WHERE r.ingredients_complete = true
WITH r, collect(DISTINCT {key: i.key, name: i.name}) AS ingredientes
WHERE none(ing IN ingredientes WHERE any(e IN $evitar WHERE toLower(ing.name) CONTAINS e))
WITH r, ingredientes,
     [ing IN ingredientes WHERE ing.key IN $disponiveis] AS encontrados,
     [ing IN ingredientes WHERE ing.key IN $prioritarios | ing.name] AS prioritarios,
     [ing IN ingredientes WHERE NOT ing.key IN $disponiveis | ing.name] AS faltantes
WHERE size(encontrados) > 0
WITH r, encontrados, prioritarios, faltantes,
     toFloat(size(encontrados)) / size(ingredientes) AS score
RETURN r.external_id AS recipe_id, r.name AS name, encontrados, prioritarios, faltantes, score
ORDER BY
    size(prioritarios) DESC,
    CASE WHEN $preferir_economicas THEN size(faltantes) ELSE 0 END ASC,
    score DESC,
    recipe_id ASC
LIMIT $limite
"""


def _impressao_digital(receita: ReceitaComIngredientes) -> str:
    conteudo = [receita["name"], sorted(receita["ingredientes"], key=lambda i: i["key"])]

    return hashlib.sha1(json.dumps(conteudo, sort_keys=True).encode()).hexdigest()


async def sincronizar(receitas: list[ReceitaComIngredientes]) -> int:
    """Envia só as receitas novas ou alteradas (cada uma custa vários round trips ao Neo4j). Devolve quantas."""

    global _labels_instalados

    client = neo4j.client
    if not _labels_instalados:
        # Uma vez por processo: reinstalar faz o Neo4j logar "constraint já existe" a cada sync.
        await client.install_labels(Recipe)
        await client.install_labels(Ingredient)
        _labels_instalados = True

    linhas, _ = await client.cypher_query(_IMPRESSOES)
    ja_enviadas = dict(linhas)
    enviadas = 0

    for receita in receitas:
        impressao = _impressao_digital(receita)
        if ja_enviadas.get(f"local:{receita['recipe_id']}") == impressao:
            continue

        enviadas += 1
        # Relações refeitas do zero: `connect` com propriedades novas criaria uma segunda relação.
        async with client.transaction:
            (no_receita,) = await Recipe.nodes.bulk_create_or_update(
                {
                    "key": f"local:{receita['recipe_id']}",
                    "source": "local",
                    "external_id": receita["recipe_id"],
                    "name": receita["name"],
                    "ingredients_complete": bool(receita["ingredientes"]),
                    "fingerprint": impressao,
                },
                merge_by={"keys": ["key"]},
            )
            await no_receita.requires.disconnect_all()

            for ingrediente in receita["ingredientes"]:
                (no_ingrediente,) = await Ingredient.nodes.bulk_create_or_update(
                    {"key": ingrediente["key"], "name": ingrediente["name"]},
                    merge_by={"keys": ["key"]},
                )
                await no_receita.requires.connect(
                    no_ingrediente,
                    {"quantity": ingrediente["quantity"], "unit": ingrediente["unit"]},
                )

    await client.cypher_query(
        _DESATIVAR_AUSENTES, {"keys": [f"local:{r['recipe_id']}" for r in receitas]}
    )

    return enviadas


async def sugerir(
    disponiveis: list[str],
    prioritarios: list[str],
    evitar: list[str],
    preferir_economicas: bool,
    limite: int,
) -> list[dict]:
    """`evitar` casa por substring sem caixa no nome: pra alergia, falso positivo é melhor que falso negativo."""

    linhas, colunas = await neo4j.client.cypher_query(
        _SUGERIR,
        {
            "disponiveis": disponiveis,
            "prioritarios": prioritarios,
            "evitar": [e.strip().lower() for e in evitar if e.strip()],
            "preferir_economicas": preferir_economicas,
            "limite": limite,
        },
    )

    return [dict(zip(colunas, linha, strict=True)) for linha in linhas]


__all__ = ["sincronizar", "sugerir"]
