"""
Projeção de receitas no Neo4j. Cliente falso: confere o que o repository manda; que o Cypher
rende o resultado certo só se prova com um Neo4j de verdade (docker-compose).
"""

import pytest

from frigus_ai.repositories import grafo_receitas_repository as repo


class _FakeNeo4j:
    def __init__(self, linhas=(), colunas=()):
        self.linhas = list(linhas)
        self.colunas = list(colunas)
        self.chamadas: list[tuple[str, dict]] = []

    async def cypher_query(self, query, params=None):
        self.chamadas.append((query, params or {}))
        return self.linhas, self.colunas


class _FakeNo:
    def __init__(self, props):
        self.props = props
        self.requires = self
        self.conexoes = []
        self.desconectou = 0

    async def disconnect_all(self):
        self.desconectou += 1

    async def connect(self, no, props):
        self.conexoes.append((no.props["key"], props))


class _FakeNodes:
    def __init__(self):
        self.criados = []

    async def bulk_create_or_update(self, props, merge_by=None):
        self.criados.append((props, merge_by))

        return [_FakeNo(props)]


class _FakeModelo:
    def __init__(self):
        self.nodes = _FakeNodes()


class _Transacao:
    def __init__(self):
        self.entradas = 0

    async def __aenter__(self):
        self.entradas += 1

    async def __aexit__(self, *_):
        return False


class _FakeNeo4jComModelos(_FakeNeo4j):
    def __init__(self):
        super().__init__()
        self.transaction = _Transacao()
        self.labels = []

    async def install_labels(self, modelo):
        self.labels.append(modelo)


@pytest.fixture
def grafo(monkeypatch):
    fake = _FakeNeo4jComModelos()
    monkeypatch.setattr(repo.neo4j, "connect", lambda: fake)
    monkeypatch.setattr(repo, "Recipe", _FakeModelo())
    monkeypatch.setattr(repo, "Ingredient", _FakeModelo())
    monkeypatch.setattr(repo, "_labels_instalados", False)

    return fake


async def test_sincronizar_faz_merge_por_chave_estavel_e_refaz_as_relacoes(grafo):
    receita = {
        "recipe_id": 4,
        "name": "Omelete",
        "ingredientes": [{"key": "product:9", "name": "Ovo", "quantity": 2.5, "unit": "un"}],
    }

    await repo.sincronizar([receita])
    await repo.sincronizar([receita])

    (props, merge_by), _ = repo.Recipe.nodes.criados[:2]
    assert props["key"] == "local:4" and merge_by == {"keys": ["key"]}
    assert repo.Ingredient.nodes.criados[0][0]["key"] == "product:9"
    assert len(grafo.labels) == 2  # constraints instaladas uma vez só, não a cada sync
    assert grafo.transaction.entradas == 2


async def test_receita_sem_ingrediente_nao_fica_completa(grafo):
    await repo.sincronizar([{"recipe_id": 4, "name": "x", "ingredientes": []}])

    assert repo.Recipe.nodes.criados[0][0]["ingredients_complete"] is False


async def test_sincronizar_pula_receita_que_nao_mudou_e_reenvia_a_alterada(grafo):
    igual = {"recipe_id": 4, "name": "Omelete", "ingredientes": [{"key": "product:9", "name": "Ovo", "quantity": 2.0, "unit": "un"}]}
    mudou = {"recipe_id": 5, "name": "Sopa", "ingredientes": []}
    grafo.linhas = [("local:4", repo._impressao_digital(igual)), ("local:5", "impressao-antiga")]

    enviadas = await repo.sincronizar([igual, mudou])

    assert enviadas == 1
    assert [c[0]["key"] for c in repo.Recipe.nodes.criados] == ["local:5"]
    assert repo.Recipe.nodes.criados[0][0]["fingerprint"] == repo._impressao_digital(mudou)


def test_impressao_digital_ignora_ordem_dos_ingredientes():
    a = {"recipe_id": 1, "name": "x", "ingredientes": [{"key": "product:1", "name": "A"}, {"key": "product:2", "name": "B"}]}
    b = {**a, "ingredientes": list(reversed(a["ingredientes"]))}

    assert repo._impressao_digital(a) == repo._impressao_digital(b)


async def test_sincronizar_desativa_receitas_que_sairam_do_catalogo(grafo):
    await repo.sincronizar([{"recipe_id": 4, "name": "x", "ingredientes": []}])

    _, params = grafo.chamadas[-1]
    assert params == {"keys": ["local:4"]}


async def test_sugerir_normaliza_evitar_e_repassa_parametros(grafo):
    grafo.colunas = ["recipe_id", "name", "encontrados", "prioritarios", "faltantes", "score"]
    grafo.linhas = [(4, "Omelete", [{"key": "product:9", "name": "Ovo"}], ["Ovo"], ["Sal"], 0.66666)]

    sugestoes = await repo.sugerir(["product:9"], ["product:9"], [" Amendoim ", ""], True, 5)

    _, params = grafo.chamadas[0]
    assert params["evitar"] == ["amendoim"]
    assert params["disponiveis"] == ["product:9"] and params["limite"] == 5
    assert sugestoes[0]["name"] == "Omelete"
    assert sugestoes[0]["faltantes"] == ["Sal"]


def test_consulta_so_considera_receita_completa_e_ordena_por_vencimento():
    assert "r.ingredients_complete = true" in repo._SUGERIR
    assert repo._SUGERIR.index("size(prioritarios) DESC") < repo._SUGERIR.index("score DESC")
