# Plano consolidado — Frigus.AI

Junção de cinco documentos: memória incremental de fatos, MCP/A2A/OAuth/Calendar, gaps da API vs Assessor, OGM Neo4j e visão + avaliação Neo4j.

Os documentos se contradizem em alguns pontos, e vários trechos de código têm bugs que quebram na primeira execução. O código original foi mantido; logo depois de cada bloco vem o que precisa mudar.

---

## Contradições entre os documentos (e a posição escolhida)

**1. Neo4j: OGM ou driver direto?** O doc de avaliação recomenda driver async direto, sem OGM. O doc posterior implementa com neomodel (OGM). Como a implementação veio depois e já está no repo, a escolha mantida é OGM. Ressalva: o argumento de que "neomodel é só síncrono" pode estar desatualizado — versões recentes do neomodel têm API async (`AsyncStructuredNode`). Conferir na doc da versão instalada.

**2. Prioridade do session/cookie auth.** Um doc coloca como prioridade 1, o outro como 5 ("só se for expor pra frontend"). O segundo está certo: session/cookie só faz sentido com um frontend web consumindo a API. Se hoje o único cliente é `X-API-Key` (ou agentes via A2A/MCP), fazer isso primeiro é trabalho sem retorno. Fica no fim, condicional.

**3. Perfil alimentar em dois lugares.** `GET/PUT /v1/profile` (alergias, preferências) e a coleção `user_fatos` guardam a mesma coisa. Unificado: a rota `/v1/profile` lê e escreve em `user_fatos`. Senão existem duas fontes de verdade pra "o usuário é alérgico a amendoim".

---

## Ordem de implementação

1. Rotas de domínio + exceções tipadas + rate limiting
2. Memória incremental de fatos (+ `/v1/profile` em cima dela)
3. Neo4j (models, conexão, sync, query de recomendação)
4. Visão (foto da geladeira)
5. Google Calendar como tool LangChain
6. Session/cookie auth — só se tiver frontend
7. MCP externo do Calendar — só se quiser expor pra outros agentes

Lógica da ordem: a fase 1 é a base, porque as fases 2 a 4 criam rotas novas que já nascem com exceções tipadas e rate limit. A 2 vem antes da 3 porque os fatos (alergias, preferências) alimentam as relações `ALLERGIC_TO`/`PREFERS` do Neo4j. Sem isso o grafo de recomendação não tem dados de usuário.

---

## Fase 1 — Rotas de domínio, exceções e rate limiting

### Rotas

```
# Estoque — CRUD direto
GET    /v1/stock/items          # listar produtos no estoque
POST   /v1/stock/items          # adicionar produto
PUT    /v1/stock/items/{id}     # atualizar (ex: mudar validade)
DELETE /v1/stock/items/{id}     # remover

# Compras
GET    /v1/shopping-list/items  # lista de compras
POST   /v1/shopping-list/items  # adicionar item à lista
PUT    /v1/shopping-list/items/{id}/bought  # marcar como comprado

# Receitas
GET    /v1/recipes              # listar receitas disponíveis
GET    /v1/recipes/suggestions  # sugestões baseadas no estoque

# Preferências do usuário
GET    /v1/profile              # perfil alimentar (alergias, preferências)
PUT    /v1/profile              # atualizar perfil

# Foto
POST   /v1/stock/foto           # analisar foto da geladeira
```

Ideia central: operação atômica ("adiciona 2L de leite") vai em rota direta; raciocínio ("o que faço pro jantar com o que tenho?") vai no chat.

As tools do MCP já fazem essas operações de estoque/compras. As rotas devem chamar a **mesma camada de service** que as tools usam, não reimplementar a lógica.

`/v1/profile` é implementada na fase 2 e `/v1/stock/foto` na fase 4.

### Rate limiting

```python
@router.post("")
@limiter.limit("10/minute")
async def create_user(request: Request, payload: UserCreate) -> UserResponse:
    ...
```

- O `slowapi` exige `request: Request` na assinatura da rota, senão dá erro.
- Configurar o `Limiter` com `storage_uri` apontando pro Redis. Sem isso o contador fica em memória, zera a cada restart e não funciona com mais de um worker.
- Aplicar pelo menos nas rotas de escrita (POST/PUT/DELETE).

### Exceções tipadas

```python
_MAPA = [
    (ChatNaoEncontrado, 404, ErrorCode.CHAT_NAO_ENCONTRADO),
    (ChatDeOutroUsuario, 403, ErrorCode.CHAT_DE_OUTRO_USUARIO),
    (LimiteDeMensagensExcedido, 429, ErrorCode.LIMITE_DE_MENSAGENS),
]
```

Criar as equivalentes de domínio no Frigus (`EstoqueNaoEncontrado`, `ProdutoDuplicado`, etc.) e mapear do mesmo jeito. Dá pra copiar a estrutura do Assessor.

---

## Fase 2 — Memória incremental de fatos

### O problema que resolve

Fluxo atual:

```
chat, chat, chat... (mensagens acumulam em agent_chats.messages[])
  → usuário deleta (DELETE /v1/chats/{id})
    → background task encerrar_sessao():
      1. _gerar_resumo(todas as mensagens)     → 1 chamada LLM
      2. salvar_resumo no Mongo (campo "resume")
      3. atualizar_perfil_pelo_resumo()         → + 1 chamada LLM (merge resumo + perfil atual)
      4. invalidar cache Redis do perfil
```

Se o usuário nunca deleta o chat, o perfil nunca atualiza. Esse é o problema real; custo e all-or-nothing são secundários.

### Coleção `user_fatos`

```python
# repositories/fatos_repository.py
{
    "user_id": 1,
    "fatos": [
        {"chave": "alergias",       "valor": ["lactose", "amendoim"],     "atualizado_em": "..."},
        {"chave": "preferencias",   "valor": ["comida caseira", "frango"],"atualizado_em": "..."},
        {"chave": "restricoes",     "valor": ["vegetariano"],             "atualizado_em": "..."},
        {"chave": "habitos",        "valor": ["almoça fora 3x/semana"],   "atualizado_em": "..."},
        {"chave": "dispensa_atual", "valor": "tem arroz, feijão, frango", "atualizado_em": "..."},
    ],
    "updated_at": "..."
}
```

### Gatilho a cada N mensagens

```python
# Em chat_service.send_message, depois de salvar as mensagens:
total = await chat_repository.contar_mensagens(session_id, user_id)

if total % 10 == 0:  # a cada 10 mensagens (5 turnos user+AI)
    fatos = await asyncio.to_thread(
        _extrair_fatos, mensagens_recentes, fatos_atuais
    )
    await fatos_repository.salvar_fatos(user_id, fatos)
```

### Extração

```python
def _extrair_fatos(mensagens_recentes: list[dict], fatos_atuais: dict) -> dict:
    """Extrai fatos estruturados das últimas mensagens e merge com os existentes."""
    prompt = load_prompt("fatos").format(
        fatos_atuais=json.dumps(fatos_atuais, ensure_ascii=False),
        mensagens=formatar_mensagens(mensagens_recentes),
    )
    return llm_rapido.invoke(prompt).content  # retorna JSON estruturado
```

### Prompt `fatos.md`

```markdown
## PAPEL
Você extrai fatos estruturados de uma conversa sobre alimentação e gestão doméstica.

## ENTRADA
Fatos atuais: {fatos_atuais}
Mensagens recentes: {mensagens}

## SAÍDA (JSON)
Devolva APENAS um JSON com os fatos atualizados. Mantenha fatos antigos que ainda são verdadeiros.
Descarte fatos que foram contraditos (ex: usuário disse "não sou mais vegetariano").

{
  "alergias": [...],
  "preferencias": [...],
  "restricoes": [...],
  "habitos": [...]
}
```

### Injeção no próximo chat

```python
# Em chat_service.send_message:
perfil = await user_service.buscar_perfil(user_id)        # texto (já existe)
fatos = await fatos_repository.buscar_fatos(user_id)      # dict estruturado (novo)

resposta = await runner.executar(conteudo, session_id, user_id, stock_id, perfil, fatos)
```

```
## PERFIL COMPORTAMENTAL
{perfil}

## FATOS CONHECIDOS
- Alergias: lactose, amendoim
- Preferências: comida caseira, frango
- Restrições: vegetariano
- Hábitos: almoça fora 3x/semana
```

O resumo no DELETE continua como está, agora como "full pass" final.

### ⚠️ Correções necessárias

**`_extrair_fatos` diz que retorna `dict`, mas retorna string.** `.content` é texto. Se o modelo devolver o JSON dentro de ```json ou com uma frase antes, o parse quebra. Usar structured output (mesmo padrão da visão):

```python
class Fatos(BaseModel):
    alergias: list[str] = []
    preferencias: list[str] = []
    restricoes: list[str] = []
    habitos: list[str] = []

llm_fatos = llm_rapido.with_structured_output(Fatos)
```

**Formato salvo não bate com o formato do prompt.** O Mongo guarda lista de `{chave, valor}`, o prompt devolve dict `{alergias: [...]}`. Escolher um. Dict é mais simples. Pra manter `atualizado_em` por fato: `{"alergias": {"valor": [...], "atualizado_em": ...}}`.

**Tirar `dispensa_atual`.** O estoque vive no Postgres (`stock_products`), que é a fonte de verdade. Guardar "tem arroz, feijão" como fato é uma cópia que desatualiza assim que o usuário usa `DELETE /v1/stock/items/{id}`.

**Não travar a resposta do usuário.** Do jeito que está, a cada 5 turnos o usuário espera uma chamada LLM extra. Jogar pra background (`BackgroundTasks` do FastAPI ou `asyncio.create_task`), igual o `encerrar_sessao` já faz.

**Alergia é informação de segurança.** Se o LLM "esquecer" uma alergia num merge, o grafo passa a recomendar receita com amendoim. Regra no código, não só no prompt: o LLM só pode *adicionar* alergias; remover exige ação explícita via `PUT /v1/profile`.

### `/v1/profile`

`GET` retorna o `user_fatos` do usuário; `PUT` sobrescreve. Dá ao usuário um jeito de corrigir o que o LLM extraiu errado.

---

## Fase 3 — Neo4j

### Schema

```
(User)-[:PREFERS]→(Ingredient)
(User)-[:DISLIKES]→(Ingredient)
(User)-[:ALLERGIC_TO]→(Ingredient)
(Recipe)-[:REQUIRES {quantity, unit}]→(Ingredient)
(Recipe)-[:SIMILAR_TO]→(Recipe)
```

Problemas dos `.cypher` originais: usavam `CREATE` em vez de `MERGE` (duplica ao reexecutar), IDs em string (`'user-1'`) que não cruzam com os IDs inteiros do Postgres, e não havia sync. O código abaixo resolve os dois últimos.

### `src/frigus_ai/infra/neo4j/models.py`

```python
"""
Modelos OGM do Neo4j (neomodel) — espelho do grafo de recomendação de receitas.

Nodes:
  - User (id do Postgres → users.id)
  - Ingredient (id do Postgres → products.id)
  - Recipe (id do Postgres → recipes.id)

Relationships:
  - User -[:PREFERS]-> Ingredient
  - User -[:DISLIKES]-> Ingredient
  - User -[:ALLERGIC_TO]-> Ingredient
  - Recipe -[:REQUIRES {quantity, unit}]-> Ingredient
  - Recipe -[:SIMILAR_TO]-> Recipe
"""

from neomodel import (
    FloatProperty,
    IntegerProperty,
    RelationshipFrom,
    RelationshipTo,
    StringProperty,
    StructuredNode,
    StructuredRel,
)


class RequiresRel(StructuredRel):
    quantity: float = FloatProperty()
    unit: str = StringProperty()


class User(StructuredNode):
    __label__ = "User"

    id = IntegerProperty(required=True, unique_index=True)
    name = StringProperty(required=True)

    prefers = RelationshipTo("Ingredient", "PREFERS")
    dislikes = RelationshipTo("Ingredient", "DISLIKES")
    allergic_to = RelationshipTo("Ingredient", "ALLERGIC_TO")


class Ingredient(StructuredNode):
    __label__ = "Ingredient"

    id = IntegerProperty(required=True, unique_index=True)
    name = StringProperty(required=True)
    category = StringProperty(required=True)

    preferred_by = RelationshipFrom("User", "PREFERS")
    disliked_by = RelationshipFrom("User", "DISLIKES")
    allergic_by = RelationshipFrom("User", "ALLERGIC_TO")
    required_by = RelationshipFrom("Recipe", "REQUIRES", model=RequiresRel)


class Recipe(StructuredNode):
    __label__ = "Recipe"

    id = IntegerProperty(required=True, unique_index=True)
    name = StringProperty(required=True)
    description = StringProperty()
    instructions = StringProperty()
    preparation_time_minutes = IntegerProperty()
    difficulty = StringProperty()

    requires = RelationshipTo("Ingredient", "REQUIRES", model=RequiresRel)
    similar_to = RelationshipTo("Recipe", "SIMILAR_TO")


__all__ = ["Ingredient", "Recipe", "RequiresRel", "User"]
```

### `src/frigus_ai/infra/neo4j/connection.py`

```python
"""
Conexão Neo4j via neomodel — inicializada no startup da app (ou manualmente via
`neo4j_conn.connect()`). O driver é síncrono (neomodel não tem API async nativa),
mas as queries são rápidas (MERGE/lookup por índice) e podem ser wrapping em
`asyncio.to_thread` se necessário.

Configuração vem de settings (NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD).
"""

from neomodel import config as neo4j_config

from frigus_ai.infra.base import Connector
from frigus_ai.settings import settings


class Neo4jConn(Connector[None]):
    """Conector neomodel — `connect()` configura a URL global do driver.

    neomodel usa uma URL de conexão global (config.DATABASE_URL), não retorna
    um objeto de conexão por instância. Por isso `connect()` retorna None —
    o efeito colateral é configurar o driver global."""

    def connect(self) -> None:
        password = settings.NEO4J_PASSWORD.get_secret_value()
        neo4j_config.DATABASE_URL = f"bolt://{settings.NEO4J_USER}:{password}@{settings.NEO4J_URI.removeprefix('bolt://')}"


neo4j_conn = Neo4jConn()

__all__ = ["Neo4jConn", "neo4j_conn"]
```

### `src/frigus_ai/infra/neo4j/sync.py`

```python
"""
Sincronização Postgres → Neo4j.

Lê os dados relacionais (users, products, recipes, recipe_ingredients) e faz
MERGE (upsert) nos nodes/relationships do Neo4j via neomodel. Idempotente —
pode rodar múltiplas vezes sem criar duplicados.

Uso:
    from frigus_ai.infra.neo4j.sync import sincronizar_tudo
    sincronizar_tudo()  # sync completo
    sincronizar_tudo(stock_id=1)  # só receitas com ingredientes do estoque

Não é chamado automaticamente — deve ser disparado por:
  - CLI/script de manutenção
  - Hook pós-insert de receita/ingrediente (granular)
  - Cron/scheduler
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from frigus_ai.infra.neo4j.connection import neo4j_conn
from frigus_ai.infra.neo4j.models import Ingredient, Recipe, User
from frigus_ai.infra.postgres.connection import postgres
from frigus_ai.infra.postgres.models import (
    Product,
    RecipeIngredient,
)
from frigus_ai.infra.postgres.models import (
    Recipe as RecipeModel,
)
from frigus_ai.infra.postgres.models import (
    User as UserModel,
)


@dataclass
class SyncResult:
    users: int = 0
    ingredients: int = 0
    recipes: int = 0
    requires: int = 0

    def __str__(self) -> str:
        return (
            f"Sync Neo4j: {self.users} users, {self.ingredients} ingredients, "
            f"{self.recipes} recipes, {self.requires} requires"
        )


def _sync_users(session: Session) -> int:
    users = session.execute(select(UserModel)).scalars().all()
    count = 0
    for u in users:
        User.nodes.get_or_create(
            id=u.id,
            defaults={"name": u.name},
        )
        count += 1
    return count


def _sync_ingredients(session: Session) -> int:
    products = session.execute(select(Product)).scalars().all()
    count = 0
    for p in products:
        Ingredient.nodes.get_or_create(
            id=p.id,
            defaults={"name": p.name, "category": p.category},
        )
        count += 1
    return count


def _sync_recipes(session: Session) -> tuple[int, int]:
    recipes = (
        session.execute(select(RecipeModel).where(RecipeModel.active.is_(True)))
        .scalars()
        .all()
    )

    recipe_count = 0
    requires_count = 0

    for r in recipes:
        recipe_node = Recipe.nodes.get_or_create(
            id=r.id,
            defaults={
                "name": r.name,
                "description": r.description or "",
                "instructions": r.instructions or "",
            },
        )[0]

        # Sync ingredientes da receita (relationship REQUIRES)
        ingredients = (
            session.execute(
                select(RecipeIngredient).where(RecipeIngredient.recipe_id == r.id)
            )
            .scalars()
            .all()
        )

        for ri in ingredients:
            ingredient_node = Ingredient.nodes.get_or_create(
                id=ri.product_id,
            )[0]

            # Atualiza properties do relationship
            recipe_node.requires.connect(
                ingredient_node,
                {
                    "quantity": float(ri.quantity) if ri.quantity else 0.0,
                    "unit": ri.unit or "",
                },
            )
            requires_count += 1

        recipe_count += 1

    return recipe_count, requires_count


def sincronizar_tudo() -> SyncResult:
    """Sincroniza users, products (→ingredients) e recipes do Postgres pro Neo4j.

    Idempotente — usa get_or_create (MERGE). Seguro chamar múltiplas vezes.
    """
    neo4j_conn.connect()

    with postgres.session() as session:
        users = _sync_users(session)
        ingredients = _sync_ingredients(session)
        recipes, requires = _sync_recipes(session)

    return SyncResult(
        users=users,
        ingredients=ingredients,
        recipes=recipes,
        requires=requires,
    )


__all__ = ["SyncResult", "sincronizar_tudo"]
```

### `src/frigus_ai/infra/neo4j/__init__.py`

```python
from .connection import Neo4jConn, neo4j_conn
from .models import Ingredient, Recipe, RequiresRel, User
from .sync import SyncResult, sincronizar_tudo

__all__ = [
    "Ingredient",
    "Neo4jConn",
    "Recipe",
    "RequiresRel",
    "SyncResult",
    "User",
    "neo4j_conn",
    "sincronizar_tudo",
]
```

### Config

`pyproject.toml` (em dependencies):

```toml
    "neomodel>=7.0.0",
```

`settings.py` (antes de `model_config`):

```python
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: SecretStr = SecretStr("")
```

`.env`:

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=sua_senha_aqui
```

### Query de recomendação

A query que justifica usar grafo:

```cypher
MATCH (r:Recipe)
WHERE NOT EXISTS {
  MATCH (r)-[:REQUIRES]->(i:Ingredient)
  MATCH (:User {id: 'user-1'})-[:DISLIKES|ALLERGIC_TO]->(i)
}
RETURN r;
```

Versão com driver async (caso volte pra essa opção):

```python
from neo4j import AsyncGraphDatabase

driver = AsyncGraphDatabase.driver(
    settings.NEO4J_URI,      # bolt://localhost:7687
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
)

async def receitas_sem_alergicos(user_id: str) -> list[dict]:
    async with driver.session() as session:
        result = await session.run("""
            MATCH (r:Recipe)
            WHERE NOT EXISTS {
                MATCH (r)-[:REQUIRES]->(i:Ingredient)
                MATCH (:User {id: $user_id})-[:DISLIKES|ALLERGIC_TO]->(i)
            }
            RETURN r.name AS nome, r.preparation_time_minutes AS tempo
        """, user_id=user_id)
        return [r.data() async for r in result]
```

Mesmo com neomodel, essa query é escrita em Cypher cru (`db.cypher_query(...)`), porque OGM não ajuda com `WHERE NOT EXISTS` com pattern. Lembrar que com a sync nova o `id` do User é inteiro, não `'user-1'`.

### ⚠️ Correções necessárias

O doc diz "197 testes passando", mas provavelmente nenhum teste roda esse sync contra um Neo4j real — do jeito que está, ele quebra:

**`get_or_create` com `defaults=` não é API do neomodel.** Essa sintaxe é do Django. No neomodel, `get_or_create`/`create_or_update` são métodos da **classe** (não de `.nodes`) e recebem dicts posicionais, tipo `User.create_or_update({"id": u.id, "name": u.name})`. Conferir a assinatura exata na doc da versão 7 — especialmente como o match é feito (só por propriedades unique ou por todas as required). Isso importa: se um produto mudar de nome e o match usar `name`, ele tenta criar outro node com o mesmo `id` e estoura a constraint de unique.

**`Ingredient.nodes.get_or_create(id=ri.product_id)` falha.** `name` e `category` são `required=True` e não foram passados. Como os ingredientes já foram sincronizados em `_sync_ingredients`, aqui é só buscar: `Ingredient.nodes.get(id=ri.product_id)`.

**`connect()` do REQUIRES pode duplicar a relação ao reexecutar.** Testar: rodar o sync duas vezes e contar `MATCH ()-[r:REQUIRES]->() RETURN count(r)`. Se dobrar, não é idempotente — checar `is_connected` antes, ou fazer esse passo em Cypher com `MERGE`.

**O docstring promete `sincronizar_tudo(stock_id=1)`, mas a função não aceita parâmetro.** Implementar ou tirar do docstring.

**Teste que vale ter:** subir o Neo4j no docker-compose, rodar o sync duas vezes e conferir que os counts de nodes e relações não mudaram.

### A peça que falta: fatos → grafo

O sync cobre users, ingredientes e receitas, mas **ninguém cria `ALLERGIC_TO`, `PREFERS` e `DISLIKES`**. Sem elas, a query de recomendação retorna todas as receitas. A fonte natural são os fatos da fase 2. Problema: os fatos são texto livre ("amendoim") e os `Ingredient` têm id do Postgres. Precisa de um passo de mapeamento texto → `products.id` (match por nome normalizado; o que não casar fica de fora e é logado).

---

## Fase 4 — Visão (foto da geladeira)

### Schema + LLM (`graph/llm.py`)

```python
# Schema do structured output (pode ficar em graph/schemas_visao.py ou em state.py)
class ItemIdentificado(BaseModel):
    nome: str
    quantidade: float
    unidade: str          # kg, un, litro, pct, gramas
    categoria: str        # Fruta, Verdura, Laticínio, Carne, etc
    local: str            # Geladeira, Freezer, Despensa, Armário
    validade_proxima: bool = False

class InventarioGeladeira(BaseModel):
    itens: list[ItemIdentificado]
    confianca: float      # 0.0 a 1.0

# Em llm.py, junto com as outras instâncias:
llm_visao = build_llm(model=Model.GEMINI_2_5_FLASH, temperature=0.1).with_structured_output(InventarioGeladeira)

# Adicionar em __all__
```

`temperature=0.1` porque é factual (identificar objetos), não criativo.

### Prompt `graph/prompts/visao.md`

```markdown
## PAPEL

### OBJETIVO
Analisar a foto de uma geladeira/freezer/despensa e identificar todos os itens visíveis.

### REGRAS
- Identifique cada item distinto, mesmo que apareça mais de uma unidade.
- Estime quantidade quando possível (ex.: "3 ovos", "500g de carne").
- Se não conseguir identificar algo, não invente — omita.
- Marque validade_proxima=true se parecer estar perto do vencimento (visual: murcha, mofo, descoloração).
- confiança reflete quão seguro está da identificação geral (0.0 = incerto, 1.0 = muito confiante).
```

### Nó `graph/nodes/visao.py`

Diferente dos outros nós: não usa `responder(estoque_app, mensagens_do_turno(estado))`, porque não é agente com tools — é chamada de visão direta. Mas devolve o mesmo `EspecialistaUpdate`.

```python
from base64 import b64encode
from langchain_core.messages import HumanMessage
from frigus_ai.graph.llm import llm_visao
from frigus_ai.graph.names import VISAO
from frigus_ai.graph.prompts import load_prompt
from frigus_ai.graph.state import EspecialistaUpdate, Estado
from frigus_ai.observability.metrics import medir_node


@medir_node(VISAO)
async def no_visao(estado: Estado) -> EspecialistaUpdate:
    b64 = estado["imagem_b64"]
    prompt = load_prompt("visao")

    msg = HumanMessage(content=[
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {
            "url": f"data:image/jpeg;base64,{b64}"
        }},
    ])

    inventario = await llm_visao.ainvoke([msg])

    # Serializa pra JSON string — mesmo formato que os outros especialistas devolvem
    return EspecialistaUpdate(
        agentes_chamados=[VISAO],
        resposta_especialista=inventario.model_dump_json(),
        dados_especialista=inventario.model_dump_json(),
    )
```

### `state.py`

```python
class EntradaGrafo(MessagesState):
    perfil_usuario: NotRequired[str]
    stock_id:       NotRequired[int | None]
    imagem_b64:     NotRequired[str]       # ← novo
```

### `names.py`

```python
NodeLiteral = Literal[
    ...,
    "visao_node",       # ← novo
]

VISAO: NodeLiteral = "visao_node"
```

### `builder.py`

O roteador decide rota por texto e não sabe lidar com imagem, então o guardrail de entrada desvia direto pra visão:

```python
def decidir_apos_guardrail_entrada(estado: Estado) -> str:
    if estado.get("mensagem_bloqueada"):
        return Route.FIM
    if estado.get("imagem_b64"):
        return VISAO              # ← bypass do roteador
    return ROTEADOR

# No _construir_grafo:
grafo.add_node(VISAO, no_visao)
grafo.add_edge(VISAO, ORQUESTRADOR)   # visao → orquestrador → juiz → guardrail_saida

# Atualizar path_map do guardrail_entrada:
path_map = {
    Route.FIM: END,
    ROTEADOR:  ROTEADOR,
    VISAO:     VISAO,          # ← novo
}
```

### Endpoint `api/routes/stock.py`

```python
from pydantic import BaseModel, ConfigDict

class FotoRequest(BaseModel):
    model_config = ConfigDict(val_json_bytes="base64")
    imagem: bytes

@router.post("/stock/foto")
async def analisar_foto(req: FotoRequest, usuario: User = Depends(usuario_atual)):
    b64 = base64.b64encode(req.imagem).decode()
    resultado = await fluxo_agentes.get().ainvoke(
        {"imagem_b64": b64, "stock_id": usuario.stock_id},
        config={"configurable": {"thread_id": f"visao-{usuario.id}"}},
    )
    return {"resposta": resultado["resposta_especialista"]}
```

### Fluxo

```
guardrail_entrada ──[tem imagem?]──→ visao → orquestrador → juiz → guardrail_saida → fim
                  └─[não]──→ roteador → especialista → ...
```

### ⚠️ Correções necessárias

**"Gemini é o único com visão" está errado.** Claude tem visão, e alguns modelos no Groq também. Gemini Flash é boa escolha por custo — a justificativa é essa, não exclusividade. Fallback é possível.

**O endpoint não manda `messages`.** Se o guardrail de entrada lê `estado["messages"][-1]` (quase certo, já que valida o texto do usuário), dá `IndexError` antes de chegar no desvio pra visão. Mandar uma `HumanMessage` junto ("analise esta foto") ou tratar o caso no guardrail.

**`thread_id` fixo por usuário + checkpointer = problema.** O `imagem_b64` fica salvo no checkpoint do Mongo — uma foto de celular em base64 tem vários MB, a cada foto. Pior: o estado persiste entre invocações da mesma thread, então a próxima chamada nessa thread ainda tem `imagem_b64` e vai pra visão de novo. Usar `thread_id` único por foto (`f"visao-{usuario.id}-{uuid4()}"`) e, de preferência, limpar a imagem do estado depois do nó (retornar `imagem_b64: None` no update, se o reducer permitir).

**Limite de tamanho.** Sem limite no upload, qualquer um manda 50MB e o processamento é pago por você. Validar tamanho no endpoint e incluir no rate limit da fase 1.

**Decisão de produto que falta:** o endpoint só *descreve* o que viu. Adiciona no estoque ou não? Sugestão: devolver a lista pro usuário confirmar e depois chamar `POST /v1/stock/items`. Adicionar direto o que um modelo de visão "acha" que viu suja o estoque.

---

## Fase 5 — Google Calendar pra validade (Caminho B: tool LangChain direta)

```
Usuário adiciona "Leite integral 2L, vence 25/set"
  → Frigus grava no Postgres (stock_products)
  → Frigus cria evento no Google Calendar: "⚠️ Leite vence hoje"
       data = validade - 1 dia
       calendar = "Frigus" (calendário dedicado)
       reminder = 9h da manhã
```

```python
# graph/tools/estoque/calendar.py
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import tool


def _criar_evento_validade(nome: str, validade: date, calendar_id: str = "frigus@group.calendar.google.com"):
    service = build("calendar", "v3", credentials=_creds())
    event = {
        "summary": f"⚠️ {nome} vence hoje",
        "start": {"date": (validade - timedelta(days=1)).isoformat()},
        "end": {"date": validade.isoformat()},
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 60}]},
    }
    return service.events().insert(calendarId=calendar_id, body=event).execute()
```

Fluxo OAuth do Google (`google-auth-oauthlib`):

```
1. Usuário autoriza uma vez (browser flow)
2. Token salvo no Redis (user_id → google_credentials)
3. Tool usa o token pra criar eventos
4. Token renova automaticamente (refresh token)
```

### ⚠️ Correções necessárias

**Título e data não batem.** O evento cai no dia *anterior* à validade, mas diz "vence hoje". Mudar pra "vence amanhã" ou pôr o evento no dia da validade. O reminder também: 60 minutos antes de um evento de dia inteiro não é "9h da manhã". Em evento all-day o popup é relativo à meia-noite do início do evento — conferir na doc da Calendar API o valor certo pra cair às 9h.

**`googleapiclient` é síncrono** e o projeto é async. Envolver em `asyncio.to_thread`.

**`_creds()` não existe.** É a parte mais trabalhosa (o fluxo OAuth inteiro) e ficou só como nome de função.

**Não guardar refresh token no Redis.** É credencial de longa duração. Redis pode perder dados (dependendo da persistência) e normalmente não é criptografado. Guardar no Postgres, com a coluna criptografada.

**Sobre o "OAuth? Não":** o Frigus não precisa ser *provedor* OAuth — isso está certo. Mas pra usar o Calendar, o Frigus vira *cliente* OAuth do Google, então OAuth entra de qualquer jeito. São papéis diferentes.

---

## Fase 6 — Session/cookie auth (só se tiver frontend)

```
POST /v1/auth/session  →  {email, password}  →  Set-Cookie: session=...; HttpOnly; SameSite=Strict
                                      + X-CSRF-Token: ...
GET  /v1/stock         ←  Cookie: session=...  +  X-CSRF-Token: ...
```

1. Login (email/senha ou magic link)
2. Session no Redis (`session_token → {user_id, csrf_hash}`, TTL 24h)
3. Cookie HttpOnly + CSRF token
4. Requests mandam cookie + header CSRF
5. Logout invalida no Redis

Dá pra copiar a implementação do Assessor. A `X-API-Key` continua existindo pro MCP e A2A, porque agente não tem cookie.

**Correção:** "cookie HttpOnly não pode ser roubado por XSS" é verdade no sentido de que o JS não *lê* o cookie. Mas um XSS ainda consegue fazer requests *como* o usuário, porque o browser manda o cookie automaticamente. HttpOnly reduz o dano, não elimina.

---

## Fase 7 — MCP externo do Calendar (Caminho A, opcional)

```
Frigus.AI  ──MCP──→  Google Calendar MCP Server  ──REST──→  Google Calendar API
```

Só vale se quiser expor a funcionalidade pra outros agentes. Encapsula a tool da fase 5 num MCP Server separado, que passa a ser dono do OAuth do Google.

---

## O que nenhum documento cobre

1. **Mapeamento fatos (texto) → `Ingredient` (id).** Sem isso o Neo4j não tem relações de usuário e a recomendação não filtra nada.
2. **Quando o sync do Neo4j roda.** As opções (CLI, hook, cron) foram listadas mas nenhuma escolhida. Pra disciplina, comando CLI + chamada no startup basta. Hook pós-insert é mais correto, mas dá mais trabalho.
3. **Foto → estoque.** Decidir se a visão só descreve ou também escreve no estoque, com ou sem confirmação.