# Relatório de avaliação e SRE — Frigus AI

Execuções de 2026-10-23 (e a medição de resumo de 2026-10-26) contra a infra real: Postgres (Supabase), MongoDB (Atlas), Redis (Upstash),
Qdrant Cloud, Neo4j (local nas primeiras rodadas, Aura nas demais; 214 receitas sincronizadas do
Postgres) e Prometheus local (`docker compose --profile observability`). O JeV (TypeSafe), pelo Vercel
AI Gateway, decide guardrail de entrada, roteador e juiz. Este relatório substitui o de 2026-10-16.

A API rodou em modo local (`API__KEY_AUTH_ENABLED=false`), com o primeiro usuário do Postgres, o mesmo
usuário que `run_scenarios` sempre usou. Foram **sete configurações** do mesmo código, porque a primeira
medição mostrou latência de até 126 s e a causa estava na configuração dos provedores, não no grafo
(seção 3).

Reproduzir:

```bash
just obs                                                   # Prometheus (9090), com o token do /metrics
uv run python -m frigus_ai.main api                        # API local; precisa do Prometheus raspando
uv run python -m frigus_ai.telemetry.evals.run_scenarios   # cenários direto no grafo (sem passar pela API)
uv run python -m frigus_ai.telemetry.evals.sre_report      # relatório (JANELA em sre_report.py)
```

Os números vieram dos cenários de `telemetry/evals/scenarios.py` enviados por
`POST /v1/chats/{id}/messages` (para as métricas caírem no processo da API, que o Prometheus raspa)
e de consultas ao Prometheus. Nada foi estimado à mão, exceto onde está dito.

## 0. Resumo (medição de 2026-10-26)

Medição mais recente: `run_scenarios --rodadas 5`, 7 cenários × 5 rodadas = **35 turnos** direto no
grafo (o mesmo caminho da API), mesma infra em nuvem e configuração final (seção 1). Custo, erros e
tempo por node vêm dos contadores Prometheus do próprio processo; a latência é medida turno a turno.
Reproduzir: `uv run python -m frigus_ai.telemetry.evals.run_scenarios --rodadas 5`.

| Indicador | 23/10 (API, 14 turnos) | 26/10 (35 turnos) | SLO |
|---|---|---|---|
| Cenários que passaram | 7/7 duas vezes | **35/35** | — |
| Índice de erros | 0% | **0%** | ≤ 5% ✅ |
| Bloqueios do guardrail | 2 | 5 (todos o cenário de ataque) | — |
| Latência mediana por turno | — | **8,0 s** | — |
| Latência média por turno | 15,7 s | ≈ 8,1 s | — |
| Latência p95 (observada) | ≈ 51 s (artefato) | **18,1 s** | ≤ 8 s ❌ |
| Maior turno | 37,7 s | **20,9 s** | — |
| Custo por turno | US$ 0,0017 | **US$ 0,0015** | — |
| Custo por resolução | US$ 0,0019 | **US$ 0,0018** | — |
| 100 usuários/semana | US$ 3,46 | **US$ 3,07** | — |
| 1000 usuários/semana | US$ 34,57 | **US$ 30,74** | — |
| ROI por resolução | ≈ 18× | **≈ 19,5×** (US$ 0,035 − 0,0018) | — |

O p95 agora é o valor observado (o 18,1 s é o 34º de 35 turnos, em ordem crescente), não o `histogram_quantile`, que
interpolava dentro do bucket. Os totais de custo vêm dos contadores do processo, sem a extrapolação do
`increase()` da medição de 23/10, então são exatos para esses 35 turnos.

Latência por cenário (5 rodadas):

| Cenário | Faixa | Observação |
|---|---|---|
| guardrail-fora-do-escopo | 0,5 a 0,7 s | bloqueio direto, sem LLM de chat |
| financeiro-gastos | 5,0 a 6,2 s | |
| faq-documentacao | 6,6 a 12,2 s | |
| estoque-consulta | 6,7 a 13,7 s | |
| compras-consulta | 7,4 a 10 s | |
| financeiro-ranking-desperdicio | 7,0 a 11,8 s | |
| **receitas-sugestao** | **9,9 a 20,9 s** | maior variação: a reescrita pedida pelo juiz dobra o turno |

Tempo somado por node (35 turnos, 360 s): estoque 34%, orquestrador 24%, compras 12%, financeiro 8%,
receitas 8%, faq 5%, juiz 4%, roteador 3%, guardrails e A2A < 1%.

### Onde vale focar

1. **Latência (único SLO que não bate).** Nenhum cenário passa de 21 s e a mediana é 8 s, mas o p95 de
   18 s está 2,3× acima dos 8 s. O tempo está em chamadas de LLM em série, não em infra: estoque e
   orquestrador somam 58% do tempo. Estoque, compras e financeiro devolvem JSON, então o orquestrador
   faz uma segunda chamada só para formatar; receitas e faq pulam essa etapa (`_RESPONDEM_EM_TEXTO` em
   `graph/nodes/orquestrador.py`) e a faq é das mais rápidas. Fazer os especialistas de dados
   responderem em texto, ou formatar sem LLM os casos simples, é o corte com maior retorno. Não foi
   feito: muda o contrato entre especialistas e juiz e precisa de uma rodada de qualidade depois.
2. **Receitas.** Pior cenário e o de maior variância (9,9 a 20,9 s); a causa é o laço juiz → reescrita
   (seção 4). Vale medir quantas reescritas ocorrem por turno antes de mexer.
3. **Custo não precisa de trabalho.** US$ 0,0015 por turno e ROI de ~19×; mesmo com 1000 usuários por
   semana são cerca de US$ 31.
4. **Erros e segurança estão limpos:** 0% de erro, guardrail bloqueou 5/5 tentativas, sem 429 nem
   fallback de modelo.

Limites desta medição: amostra de 35 turnos e um único usuário de teste; critério de acerto fraco
(palavra-chave); sem foto, escrita no estoque nem receitas por Neo4j nos cenários (escrever mexeria nos
dados reais do usuário padrão); não passou pelo HTTP, então não inclui a latência da API nem o
`/metrics` raspado pelo Prometheus. A medição pela API de 23/10 (seções 1 e 2) continua valendo para
essas partes.

## 1. Configuração final

Todas as chamadas de chat (especialistas, orquestrador, FAQ, visão) usam a **GPT-6 Luna** pelo Vercel AI
Gateway com `reasoning_effort="low"`; Groq e OpenRouter ficam de reserva; o Gemini ficou só nos
embeddings. O JeV segue como decisor de guardrail, roteador e juiz. Dois ajustes de configuração vieram
junto: o Groq deixou de esperar o `retry-after` do 429 (`retries=0`) e o limiar de grounding do juiz
passou de 0,8 para 0,4 (seção 4).

### Cenários de qualidade (duas rodadas seguidas, configuração final)

| Cenário | Rodada A | Rodada B |
|---|---|---|
| estoque-consulta | ✅ 16,7 s | ✅ 9,7 s |
| compras-consulta | ✅ 12,5 s | ✅ 37,7 s |
| receitas-sugestao | ✅ 29,0 s | ✅ 36,9 s |
| financeiro-gastos | ✅ 10,1 s | ✅ 9,7 s |
| financeiro-ranking-desperdicio | ✅ 16,2 s | ✅ 12,6 s |
| faq-documentacao | ✅ 19,0 s | ✅ 8,5 s |
| guardrail-fora-do-escopo | ✅ (bloqueado) 1,0 s | ✅ (bloqueado) 0,8 s |

**7/7 nas duas rodadas** (HTTP 200 em todos). O critério é fraco de propósito: a resposta veio e contém
ao menos uma palavra-chave (`any`). Ele não confere se o conteúdo está correto; só que a resposta existe
e é do domínio certo. A qualidade da Luna em relação ao Gemini foi olhada por amostra e pelas aprovações
do juiz, não medida.

### SRE (janela de 299 s, 14 turnos: 12 `success` + 2 `blocked`)

| Métrica | Valor | SLO |
|---|---|---|
| Índice de erros | 0% | ≤ 5% ✅ |
| Fallbacks de modelo, erros de LLM, 429 | 0 | — |
| Latência média por turno (API) | 15,7 s | — |
| Maior turno medido na API | 37,7 s | — |
| Latência p95 (Prometheus) | ≈ 51 s (ver nota) | ≤ 8 s ❌ |
| Custo médio por turno | US$ 0,0017 | — |
| Custo por resolução | US$ 0,0019 | — |
| **Estimativa 100 usuários/semana** | **US$ 3,46** | — |
| **Estimativa 1000 usuários/semana** | **US$ 34,57** | — |
| ROI por resolução | US$ 0,035 − 0,0019 (≈ 18×) | — |

Nota sobre o p95: o histograma `frigus_graph_duration_seconds` tem buckets em 30 s e 60 s
(`telemetry/metrics.py`) e o `histogram_quantile` interpola dentro do bucket, então ≈ 51 s é um
artefato; o pior turno real foi 37,7 s. Com 14 amostras, o p95 é na prática o máximo. O SLO de 8 s não
bate. Os totais do relatório vêm de `increase()`, que extrapola entre raspagens de 15 s, então os
contadores e o custo por turno são estimativas (12,6 turnos observados onde houve 14).

Tempo somado por node (a soma passa do tempo de parede por causa do `increase()`):

| Node | Tempo | % |
|---|---|---|
| estoque_node | 93,1 s | 43% |
| orquestrador_node | 64,1 s | 30% |
| compras_node | 22,0 s | 10% |
| financeiro_node | 13,6 s | 6% |
| receitas_node | 9,9 s | 5% |
| juiz_node | 9,7 s | 4% |
| roteador | 5,0 s | 2% |

57 chamadas à Luna em 212,7 s (média 3,7 s), 157 mil tokens de entrada e 6 mil de saída; o JeV gastou
15,2 s no total (≈ 1,1 s por turno) e os embeddings do Gemini 7 s. O orquestrador e o juiz rodaram 17,6
vezes para 12 resoluções (1,5 por turno): o juiz ainda pede reescrita em respostas de receitas, o que é
correto (ver seção 4). Um ponto que não investiguei: `receitas_node` aparece com tempo baixo no
histograma por node, embora o cenário de receitas seja um dos mais lentos; o tempo parece contabilizado
em outro node.

### Premissas (estimativas, não medidas)

- **Mensagens por usuário por semana: 20** (~3 por dia: uma consulta e uma ação).
- **Valor por resolução: US$ 0,035.** Uma família brasileira desperdiça cerca de R$ 1.002/ano em
  alimentos (Embrapa/FGV, 2018, sem correção pela inflação, portanto conservador). Supondo que o
  Frigus evite 20% disso: R$ 1.002 × 0,20 ÷ 52 semanas ÷ 20 mensagens ÷ R$ 5,50/US$.
- **Preços** (`PRECOS_POR_1M_TOKENS`): Luna US$ 0,10 / US$ 0,50 por 1M tokens de entrada/saída; JeV
  US$ 0,04 de entrada; Gemini 3.6 Flash US$ 0,75 / US$ 3,75; Groq `gpt-oss-120b` US$ 0,15 / US$ 0,60. O
  custo da Luna conta os tokens de raciocínio como saída, como o gateway cobra.

## 2. Comparação das configurações testadas

Mesmos 7 cenários, mesmo código de grafo; só mudaram o modelo principal e a configuração dos provedores.
A latência é a média dos 7 turnos (por rodada); o custo vem do `sre_report` (estimado por `increase()`),
exceto onde indicado.

| # | Configuração | Latência média | Maior turno | Custo/turno | 100 usuários/semana |
|---|---|---|---|---|---|
| 1 | Gemini direto (ainda com cota) + Groq | 27,3 s | 73,8 s | US$ 0,0120 | US$ 23,95 |
| 2 | Gemini direto **sem cota** (429) → Groq (429 por TPM) | 61,3 s | 126,1 s | US$ 0,0057 | US$ 11,44 |
| 3 | Gemini pelo gateway, raciocínio padrão | 15,4 s | 34,1 s | US$ 0,0204 (calculado dos tokens) | US$ 40,80 |
| 4 | Gemini pelo gateway, raciocínio mínimo | 8,6 s | 19,3 s | US$ 0,0148 | US$ 29,60 |
| 5 | idem 4 + limiar do juiz 0,4 (2 rodadas, 14 turnos) | 8,0 s | 21,4 s | US$ 0,0133 | US$ 26,51 |
| 6 | **Luna** pelo gateway, raciocínio padrão (2 rodadas) | 17,6 s | 53,3 s | US$ 0,0021 | US$ 4,13 |
| 7 | **Luna, `reasoning_effort="low"` (final)** (2 rodadas) | 15,7 s | 37,7 s | **US$ 0,0017** | **US$ 3,46** |

Leitura:

- O Gemini com raciocínio mínimo (5) é cerca de **2× mais rápido** que a Luna final (7), e a Luna é cerca
  de **8× mais barata** (US$ 0,0017 contra US$ 0,0133 por turno). A configuração final privilegia o
  custo, que era o problema: o Gemini gastava US$ 0,59 em uma parte do mês no painel do gateway contra
  centavos da Luna.
- A Luna **aceita imagem** pelo gateway (testado com uma imagem sintética de 96×96, respondeu a cor em
  2,9 s), então a visão também foi para ela. Fotos reais de geladeira não foram testadas.
- Nenhuma configuração atinge o SLO de 8 s no turno completo. O turno passa por roteador, guardrail,
  especialista (com um ciclo de tools), orquestrador e juiz; cortar isso exige reduzir chamadas por
  turno, não só trocar de modelo.

## 3. Por que a primeira medição foi tão lenta (configurações 1 e 2)

Duas causas, ambas de configuração dos provedores no plano gratuito, nenhuma de código:

1. **Gemini direto sem cota.** O plano gratuito permite 20 requisições por dia para `gemini-3.6-flash`
   (`RESOURCE_EXHAUSTED`, "retry in 17h31m"). Toda chamada de especialista falhava em ~1 s e caía no
   Groq.
2. **Groq com 8.000 tokens por minuto.** Um turno com os schemas das tools passa disso; o 429 vem com
   `retry-after: 20` e a configuração antiga (`retries=1`) esperava esses 20 s antes de seguir a
   cadeia. Foram 30 respostas 429 em uma rodada.

Medido isoladamente: o gateway pago serve os mesmos modelos em ~1 s e sem esses limites. Por isso o chat
foi para o gateway (primeiro o Gemini, depois a Luna a pedido) e o Groq passou a cair para o próximo
elo na hora. Outro achado: o Gemini 3 raciocina sem limite por padrão (575 tokens de raciocínio para ~60
caracteres de resposta no teste), o que inflava latência e custo; isso vale só para o Gemini, que saiu
das cadeias.

## 4. Calibração do juiz (grounding)

O corte `confianca_minima_grounding` era 0,8, com o comentário "chute, sem calibração". Medi a
probabilidade de "sustentada" do JeV em 24 casos: 16 respostas reais, e 8 versões das mesmas respostas
adulteradas com um fato inventado ("você tem 3 kg de picanha", "gastou R$ 1.250 em março"…).

| Grupo | Chance de "sustentada" |
|---|---|
| Adulteradas (n = 16, duas por resposta) | 0,00 a 0,10 |
| Respostas reais de receitas que inventam pratos | 0,01 a 0,28 |
| Respostas reais corretas | 0,49 a 0,98 |

Há um vão entre 0,28 e 0,49, e o limiar ficou em **0,4**. Com 0,8 o juiz reprovava respostas corretas
(a de "você gastou R$ 0,00" ficou em 0,72–0,77) e forçava até duas reescritas por turno. O juiz estava
certo ao reprovar as respostas de receitas: elas citam pratos que não existem nos dados (por exemplo
"salada de pepino com alface, cenoura e cebola"). Limitação: a amostra é pequena e vem de um único
usuário de teste; deve ser reavaliada com mais casos.

## 5. Persistência, isolamento e contratos

Contra o MongoDB e o Postgres reais:

- **Histórico sobrevive a reinício:** API derrubada e reiniciada; `GET /v1/chats/{id}/messages`
  devolveu a mesma quantidade de mensagens antes e depois (2 → 2 nos chats novos e 34 → 34 em um
  chat antigo).
- **Chat inexistente:** `POST /v1/chats/id-que-nao-existe/messages` responde **404**. O primeiro envio
  com ID inventado deixou de criar o chat; ele é criado por `POST /v1/chats` (e pelo A2A sem
  `contextId`).
- **Outro usuário não acessa o chat** (`validar_ownership` → 403) e **estoque vem só da identidade**:
  cobertos por testes automatizados; não reexecutei contra o banco real, porque o modo local usa um
  único usuário.

## 6. Funções novas, verificadas contra a infra real

| Verificação | Resultado |
|---|---|
| `GET /v1/recipes/suggestions` (Neo4j) | 200 em 0,7 a 1,5 s, 5 resultados com ingredientes encontrados/faltantes e `reason` |
| Sincronização do grafo | 214 receitas; primeira carga no Aura levou 600 s; as seguintes enviam só o que mudou (0 receitas em 1 s) |
| `GET /v1/recipes?query=a` | 200; filtra por nome |
| `GET /v1/recipes/local/{id}` | 200; receita inexistente → 404 |
| `PUT .../favorite` duas vezes | 204 e 204; um único favorito; `is_favorite` verdadeiro na listagem; `DELETE` → 204 |
| `PATCH /v1/profile/recipe-preferences` | altera só o campo enviado (`preferir_economicas`) |
| `GET /v1/recipes/spoonacular/{id}` | 200 com imagem e fonte. A receita testada veio sem instruções da própria Spoonacular, então `steps` ficou vazio |

Ficam sem verificação contra a infra: foto real no chat, sugestão com `preferir_economicas` mudando a
ordem e restrições. Os cenários de `scenarios.py` ainda não cobrem as funções novas.

Segurança: a chave da Spoonacular ia como `?apiKey=` na URL e aparecia em texto no log do `httpx` e em
tracebacks; passou a ir no header `x-api-key`. Uma chave que apareceu em log deve ser considerada
exposta e rotacionada.
