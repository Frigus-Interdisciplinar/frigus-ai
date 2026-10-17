# JeV (Decisions API do Vercel AI Gateway)

O JeV (TypeSafe) responde perguntas fechadas com probabilidade, sem gerar texto. Aqui ele é chamado
por `POST {gateway}/decisions` (`infra/llm/jev/`) e decide o guardrail de entrada, o roteador e o
juiz, sempre com o LLM de reserva. Contrato: https://vercel.com/docs/ai-gateway/sdks-and-apis/openai-decisions

**Nada disso foi exercitado contra o gateway real** (ver o primeiro item). O contrato vem da
documentação e dos testes com resposta simulada.

## Contrato: as classes de `schemas.py` e o JSON equivalente

Cada classe é um objeto do JSON do mesmo nome. Pedido e resposta têm formas separadas.

```text
PedidoDecisao ──────────────► corpo do POST /decisions
  ├─ questions: list[Pergunta]       cada pergunta é um dos três tipos abaixo
  └─ provider_options                serializa como "providerOptions" (alias)

RespostaDecisao ◄────────────── corpo da resposta
  ├─ answers: list[Resposta]         na MESMA ordem das perguntas
  ├─ model                           quem respondeu de fato (JeV ou a reserva)
  └─ usage                           {"input_tokens": ...}
```

| Pergunta (pedido) | `type` | Resposta | `type` | O que traz |
|---|---|---|---|---|
| `PerguntaPredicado` | `predicate` | `Predicado` | `predicate` | `probability` de ser "sim" (`.sim` = 0,5 ou mais) |
| `PerguntaEscolha` | `choice` | `Escolha` | `choice` | `choice` (a opção) e `confidence` |
| `PerguntaNota` | `score` | `Nota` | `score` | `score` (média ponderada dos níveis) e `confidence` |
| qualquer uma | — | `Recusa` | `refusal` | só `name`: o modelo não quis responder |

**Pedido**: as três perguntas juntas, em Python e no JSON que vai pela rede.

```python
PedidoDecisao(
    model="typesafe-ai/jev",
    input="Quero uma receita com batata frita e ver minha lista de compras",
    questions=[
        PerguntaPredicado(name="receitas", instructions="Precisa do especialista de receitas?"),
        PerguntaEscolha(
            name="categoria",
            instructions="Classifique a mensagem.",
            choices={Categoria.APROVADO: "mensagem legítima", Categoria.POLITICO: "debate político"},
        ),
        PerguntaNota(
            name="urgencia",
            instructions="Quão urgente?",
            levels=[Nivel(label="baixa"), Nivel(label="alta", description="precisa de resposta já")],
        ),
    ],
    provider_options={"gateway": {"models": ["openai/gpt-6-luna-decisions"]}},
)
```

```json
{
  "model": "typesafe-ai/jev",
  "input": "Quero uma receita com batata frita e ver minha lista de compras",
  "questions": [
    { "type": "predicate", "name": "receitas", "instructions": "Precisa do especialista de receitas?" },
    { "type": "choice", "name": "categoria", "instructions": "Classifique a mensagem.",
      "choices": [
        { "value": "APROVADO", "description": "mensagem legítima" },
        { "value": "POLITICO", "description": "debate político" }
      ] },
    { "type": "score", "name": "urgencia", "instructions": "Quão urgente?",
      "levels": [
        { "label": "baixa" },
        { "label": "alta", "description": "precisa de resposta já" }
      ] }
  ],
  "providerOptions": { "gateway": { "models": ["openai/gpt-6-luna-decisions"] } }
}
```

Dois detalhes do que a classe faz por você: `choices` aceita `{opção: descrição}` e vira a lista de
`{"value", "description"}` sozinho, e os campos vazios (`description=None`) saem do JSON.

**Resposta**: uma resposta por pergunta, na mesma ordem; `answers[i]` responde `questions[i]`.

```json
{
  "model": "typesafe-ai/jev",
  "answers": [
    { "type": "predicate", "name": "receitas", "probability": 0.93 },
    { "type": "choice", "name": "categoria", "choice": "APROVADO", "confidence": 0.98 },
    { "type": "score", "name": "urgencia", "score": 0.4, "confidence": 0.7 }
  ],
  "usage": { "input_tokens": 96, "output_tokens": 0 }
}
```

O `type` decide qual classe lê cada item: `{"type": "predicate", ...}` vira `Predicado`,
`{"type": "refusal", ...}` vira `Recusa`. Quem usa o resultado não mexe nessas classes: `decidir()`
devolve um `Decisoes`, e `decisoes.sim("receitas")` ou `decisoes.escolha("categoria")` pegam o valor pelo
nome da pergunta.

## Toda chamada dá 403 até a conta Vercel ter cartão cadastrado

`GET /models` funciona com a chave, mas `/chat/completions` e `/decisions` voltam
`customer_verification_required`, até pros créditos gratuitos. Cadastrar o cartão não tira a conta do
plano gratuito; só **comprar** créditos tira. Enquanto isso, JeV e Luna ficam inativos e o código cai
nos LLMs normais.

Com o cartão já cadastrado o erro muda para `RestrictedModelsError` ("Free tier users do not have
access to this model"): é o mesmo bloqueio de plano. Confirmado em 2026-10-16: após comprar US$ 15 de
créditos, `/decisions` passou a responder 200 (`typesafe-ai/jev`) e o grafo parou de logar
"JeV falhou, usando o LLM". Pra testar a conta sem gastar, uma pergunta mínima de `choice` basta.

## Três tipos de pergunta, e nome único por requisição

`predicate` (sim/não, devolve `probability`), `choice` (de 1 a 255 opções, devolve `choice`,
`confidence` e `probabilities`) e `score` (2 a 10 níveis, devolve `score`). As respostas voltam **na
ordem das perguntas**, e o nome de cada pergunta tem que ser único. `decidir()` faz várias perguntas
sobre a mesma entrada numa requisição só: o roteador usa 7 predicados e o juiz usa 1 escolha + 2
predicados.

`choice` aceita só string ou bool como valor, então as opções precisam ser `StrEnum` (o
`PerguntaEscolha` aceita `{opção: descrição}` direto e converte). Opções que só existem em runtime
(IDs de produto) são strings, e o limite é 255 por pergunta: nunca mande o catálogo inteiro.

## Recusa é uma resposta, não um erro HTTP

Se o modelo se recusa a responder uma pergunta, ela volta como `{"type": "refusal"}` na posição dela
e as outras são respondidas normalmente (e a requisição é cobrada). `Recusa` está no contrato e
`_validar` a trata como falha, igual a uma opção fora da lista (`invalida`). Os dois contam em
`frigus_jev_decisions_total` e caem no fallback de quem chamou.

## O modelo é só texto: imagem dá 400

`typesafe-ai/jev` não aceita imagem. A reserva `openai/gpt-6-luna-decisions` aceita, mas nenhum uso
atual manda imagem. A reserva vai em `providerOptions.gateway.models`, e o gateway a usa sozinho se o
JeV falhar. A resposta traz o modelo que respondeu de fato (`model`), e é isso que a métrica
`modelo` mostra.

## O SDK `openai` (3.5.0) não tem `decisions`

`OpenAI().decisions` não existe nessa versão. O cliente usa `httpx` direto, o que também significa que
**tokens e custo não passam pelo callback do LangChain**: `decidir()` conta
`frigus_llm_tokens_total` e `frigus_llm_cost_usd_total` por conta própria. O preço (US$ 0,04 por
milhão de tokens de entrada, saída grátis) está em `PRECOS_POR_1M_TOKENS`.

## Confiança não é probabilidade de acerto

`confidence=0,8` não quer dizer 80% de acerto (https://docs.typesafe.ai/confidence). O predicado
vira sim/não com o corte fixo de 0,5 (`Predicado.sim`), **não calibrado** com perguntas reais do
Frigus. O histograma `frigus_jev_confidence` serve pra comparar ao longo do tempo, não como nota; não
coloque alerta nem limiar nele sem exemplos medidos.

## O roteador só enxerga a última pergunta do usuário

O JeV recebe o texto da última mensagem do usuário, sem histórico. Dois pedidos numa frase ("me sugira
uma receita com batata frita e já veja minha lista de compras") passam em dois predicados e vão pros
dois especialistas em paralelo; se um depende do resultado do outro, o predicado `etapas` desvia pro
LLM. Resposta que só faz sentido com contexto ("sim", "o de ontem") não passa em nenhum predicado e o
roteador LLM assume com o histórico completo. O risco é um follow-up ambíguo ("pode adicionar o leite"
depois de o assistente falar da lista de compras) casar com o especialista errado, já que o contexto
que o desambiguaria não chega ao JeV. Se isso aparecer nos cenários, mande também a mensagem anterior
do assistente.

## O juiz perde a justificativa em texto

O JeV devolve uma opção, não uma explicação. O feedback pro orquestrador reescrever vira uma frase fixa
por critério reprovado (`_FEEDBACK` em `graph/nodes/juiz.py`), bem menos direcionado que a
justificativa livre do juiz LLM ("citou iogurte, que não está nos dados"). Compare a precisão e a
qualidade da reescrita com o juiz LLM antes de manter.

## Contrato em Pydantic: o `type` é o discriminador

`schemas.py` usa `Literal[TipoPergunta.X]` com o valor padrão em cada classe. Não junte os três tipos
num `Literal` só: o Pydantic usa esse campo pra saber se `{"type": "predicate", ...}` é um `Predicado`
ou uma `Escolha`, e perderia a separação. Os três aparecem juntos só nas uniões (`Pergunta`,
`Resposta`).

```python
class PerguntaPredicado(BaseModel):
    type: Literal[TipoPergunta.PREDICADO] = TipoPergunta.PREDICADO
    ...

type Pergunta = Annotated[PerguntaPredicado | PerguntaEscolha | PerguntaNota, Field(discriminator="type")]
```

## Cada uso novo passa o próprio `uso` e cuida da cardinalidade

`decidir(uso, ...)` separa as métricas por quem pergunta. A resposta entra como label em
`frigus_jev_decisions_total`, o que só serve pra opções fixas (6 categorias, sim/não); opção dinâmica
(ID de produto) precisa de um rótulo genérico, senão a cardinalidade explode.
