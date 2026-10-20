# Relatório de avaliação e SRE — Frigus AI

Execução de 2026-10-16 contra a infra real: Postgres (Supabase), MongoDB (Atlas), Redis (Upstash),
Qdrant Cloud e Prometheus local (`docker compose --profile observability`). LLMs: Gemini 3.6 Flash e
Groq `gpt-oss-120b`, mais o Vercel AI Gateway com créditos comprados (US$ 15), onde o JeV (TypeSafe)
decide guardrail de entrada, roteador e juiz, com o LLM de reserva se ele falhar. A rodada anterior
(2026-10-11, plano gratuito, 5/7 cenários, 22% de erro e p95 ≥ 120 s por 429 dos provedores) foi
substituída por esta.

Reproduzir:

```bash
uv run python -m frigus_ai.telemetry.evals.run_scenarios   # cenários
uv run python -m frigus_ai.main api                       # API local, com o Prometheus no ar
uv run python -m frigus_ai.telemetry.evals.sre_report     # relatório
```

## 1. Cenários de qualidade (`telemetry/evals/run_scenarios.py`)

Os 7 cenários rodaram pela API (`POST /v1/chats/{id}/messages`, HTTP 200 em todos), depois de ativar
o gateway pago.

| Cenário | Resultado | Latência |
|---|---|---|
| estoque-consulta | ✅ | 6 s |
| compras-consulta | ✅ | 26 s |
| receitas-sugestao | ✅ | 58 s |
| financeiro-gastos | ✅ | 7 s |
| financeiro-ranking-desperdicio | ✅ | 21 s |
| faq-documentacao | ✅ | 22 s |
| guardrail-fora-do-escopo | ✅ (bloqueado) | 3 s |

**7/7.** Uma rodada anterior, direto no grafo e antes dos créditos, também fechou 7/7, mas com o
JeV respondendo 403 (plano gratuito) e o Gemini com 503 por alta demanda; receitas levou 162 s. Com
os créditos, o `/v1/decisions` responde 200 (`typesafe-ai/jev`) e o log não registra mais "JeV
falhou, usando o LLM".

**Juiz (grounding).** Nos cenários aprovados o Juiz justificou citando o retorno das tools, por
exemplo: *"A resposta reflete fielmente os dados retornados pela tool sobre o total de gastos no mês
de outubro"*. Desde esta versão ele compara a resposta com o que as tools devolveram (antes comparava
o texto do especialista com ele mesmo), e falha na avaliação vira `INDISPONIVEL`, não `APROVADO`.

## 2. SRE (`telemetry/evals/sre_report.py`, janela de 30 minutos)

Janela de 30 minutos (`JANELA = "30m"`, em vez dos 7 dias padrão) para não misturar com a rodada
antiga. Cobre os 7 turnos da seção 1 mais 3 reenvios. Os totais vêm de `increase()` do Prometheus, que
extrapola entre raspagens de 15 s: **os contadores são estimativas** (o relatório mostra 5,7 turnos e
0 bloqueios onde houve 10 e 1), e custo por turno herda essa imprecisão.

| Métrica | Valor | SLO |
|---|---|---|
| Índice de erros | 0% | ≤ 5% ✅ |
| Orçamento de erro consumido | 0 | — |
| Latência p95 do turno | 52,5 s | ≤ 8 s ❌ |
| Custo observado | US$ 0,0256 | — |
| Custo médio por turno | US$ 0,0045 | — |
| Custo por resolução | US$ 0,0045 | — |
| **Estimativa 100 usuários/semana** | **US$ 9,00** | — |
| **Estimativa 1000 usuários/semana** | **US$ 89,98** | — |
| ROI por resolução | US$ 0,035 − 0,0045 | — |

### O SLO de latência não bate

O erro caiu de 22,2% para 0% depois que os provedores deixaram de estourar cota (o 429 do plano
gratuito era a causa dos erros e da latência ≥ 120 s da rodada de 2026-10-11). A latência continua
fora da meta, por outro motivo: **o turno de receitas leva ~58 s** (os demais ficam entre 3 s e 26 s),
provavelmente por encadear tools (Spoonacular, estoque) e chamadas de LLM; **não medi onde o tempo
vai** (o histograma por node no Prometheus responde isso). Um turno comum passa
por vários agentes (guardrail, roteador, especialista, orquestrador, juiz), e o p95 é puxado pelos
mais longos. Para chegar a 8 s seria preciso otimizar esse caminho (menos chamadas por turno ou
paralelizá-las); isso não foi feito.

O custo por turno subiu de US$ 0,0035 para US$ 0,0045 em relação à rodada antiga. Não isolei a causa;
a diferença é de US$ 0,001 e as duas medições têm a imprecisão do `increase()` e mix de cenários
diferentes.

### Premissas (estimativas, não medidas)

- **Mensagens por usuário por semana: 20** (~3 por dia: uma consulta e uma ação).
- **Valor por resolução: US$ 0,035.** Uma família brasileira desperdiça cerca de R$ 1.002/ano em
  alimentos (Embrapa/FGV, 2018, sem correção pela inflação, portanto conservador). Supondo que o
  Frigus evite 20% disso: R$ 1.002 × 0,20 ÷ 52 semanas ÷ 20 mensagens ÷ R$ 5,50/US$.
- **Preços:** Gemini 3.6 Flash US$ 0,75 / US$ 3,75 por 1M tokens de entrada/saída (vale até
  2026-12-31; dobra em 2027); Groq `gpt-oss-120b` US$ 0,15 / US$ 0,60.

Com essas premissas, cada resolução custa US$ 0,0045 e vale US$ 0,035: o ROI é positivo com folga
de ~7,8×, e continua positivo mesmo se o desperdício evitado for de 3% em vez de 20%.

## 3. Persistência e isolamento de sessões

Contra o MongoDB e o Postgres reais:

- **Histórico sobrevive a reinício:** chat com 20 mensagens enviadas; API derrubada e reiniciada;
  `GET /v1/chats/{id}/messages` devolveu as 34 mensagens (17 trocas com sucesso; turnos com erro 500
  não são gravados).
- **Outro usuário não acessa o chat:** `validar_ownership` com o dono passa; com outro `user_id`
  levanta `ChatDeOutroUsuario` (HTTP 403 na API).
- **Estoque vem só da identidade:** um usuário sem vínculo não recebe estoque (`None`); o `stock_id`
  não é mais aceito no corpo da mensagem (422).
