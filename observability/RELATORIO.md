# Relatório de avaliação e SRE — Frigus AI

Execução de 2026-10-11 contra a infra real: Postgres (Supabase), MongoDB (Atlas), Redis (Upstash),
Qdrant Cloud e Prometheus local (`docker compose --profile observability`). LLMs no plano gratuito
(Gemini 3.6 Flash e Groq `gpt-oss-120b`).

Reproduzir:

```bash
uv run python -m frigus_ai.telemetry.evals.run_scenarios   # cenários
uv run python -m frigus_ai.main api                       # API local, com o Prometheus no ar
uv run python -m frigus_ai.telemetry.evals.sre_report     # relatório
```

## 1. Cenários de qualidade (`telemetry/evals/run_scenarios.py`)

| Cenário | Resultado | Latência |
|---|---|---|
| estoque-consulta | ✅ | 19,5 s |
| compras-consulta | ❌ 429 do provedor | 8,2 s |
| receitas-sugestao | ❌ 429 do provedor | 35,0 s |
| financeiro-gastos | ✅ | 12,2 s |
| financeiro-ranking-desperdicio | ✅ | 37,1 s |
| faq-documentacao | ✅ | 57,3 s |
| guardrail-fora-do-escopo | ✅ (bloqueado) | 0,6 s |

**5/7.** As duas falhas são limite de requisições do provedor de LLM, não erro de roteamento: os
mesmos cenários passaram na rodada de tráfego seguinte.

**Juiz (grounding).** Nos cenários aprovados o Juiz justificou citando o retorno das tools, por
exemplo: *"A resposta reflete fielmente os dados retornados pela tool sobre o total de gastos no mês
de outubro"*. Desde esta versão ele compara a resposta com o que as tools devolveram (antes comparava
o texto do especialista com ele mesmo), e falha na avaliação vira `INDISPONIVEL`, não `APROVADO`.

## 2. SRE (`telemetry/evals/sre_report.py`, janela de 7 dias)

45 turnos observados: os cenários acima, mais 20 mensagens pela API e execuções anteriores na janela.

| Métrica | Valor | SLO |
|---|---|---|
| Turnos / resoluções | 45 / 34 | — |
| Índice de erros | 22,2% | ≤ 5% ❌ |
| Orçamento de erro consumido | 4,4× | — |
| Latência p95 do turno | ≥ 120 s (último bucket do histograma) | ≤ 8 s ❌ |
| Bloqueios do guardrail | 1 | fora do índice de erros |
| Custo observado | US$ 0,158 | — |
| Custo médio por turno | US$ 0,0035 | — |
| Custo por resolução | US$ 0,0046 | — |
| **Estimativa 100 usuários/semana** | **US$ 7,01** | — |
| **Estimativa 1000 usuários/semana** | **US$ 70,06** | — |
| ROI na janela | US$ 1,04 | — |

### Por que os dois SLOs falharam

Os erros e a latência têm a mesma causa: **limite do plano gratuito dos provedores**. O log da API
registrou 41 respostas 429; 36 novas tentativas do cliente HTTP; Groq limitado a 8.000 tokens por
minuto no `gpt-oss-120b` e cota do Gemini excedida. A latência alta é o tempo das novas tentativas
esperando o limite liberar; quando os dois provedores estouram juntos, o turno falha (os 3 erros 500
da rodada de tráfego). Um turno passa por vários agentes (guardrail, roteador, especialista,
orquestrador, juiz), então uma mensagem consome boa parte do limite de um minuto.

Conclusão: no plano gratuito o sistema não sustenta nem um usuário mandando duas mensagens por
minuto. **O custo projetado (US$ 70/semana para 1000 usuários) já é o do plano pago**, e é nele que
os SLOs fazem sentido. A cadeia de reserva de modelos funciona (testada isoladamente: o agente cai do
modelo principal para o Groq e usa a tool), mas o último elo, o modelo gratuito do OpenRouter, deixou
de existir (404) e precisa ser trocado.

### Premissas (estimativas, não medidas)

- **Mensagens por usuário por semana: 20** (~3 por dia: uma consulta e uma ação).
- **Valor por resolução: US$ 0,035.** Uma família brasileira desperdiça cerca de R$ 1.002/ano em
  alimentos (Embrapa/FGV, 2018, sem correção pela inflação, portanto conservador). Supondo que o
  Frigus evite 20% disso: R$ 1.002 × 0,20 ÷ 52 semanas ÷ 20 mensagens ÷ R$ 5,50/US$.
- **Preços:** Gemini 3.6 Flash US$ 0,75 / US$ 3,75 por 1M tokens de entrada/saída (vale até
  2026-12-31; dobra em 2027); Groq `gpt-oss-120b` US$ 0,15 / US$ 0,60.

Com essas premissas, cada resolução custa US$ 0,0046 e vale US$ 0,035: o ROI é positivo com folga
de ~7×, e continua positivo mesmo se o desperdício evitado for de 3% em vez de 20%.

## 3. Persistência e isolamento de sessões

Contra o MongoDB e o Postgres reais:

- **Histórico sobrevive a reinício:** chat com 20 mensagens enviadas; API derrubada e reiniciada;
  `GET /v1/chats/{id}/messages` devolveu as 34 mensagens (17 trocas com sucesso; turnos com erro 500
  não são gravados).
- **Outro usuário não acessa o chat:** `validar_ownership` com o dono passa; com outro `user_id`
  levanta `ChatDeOutroUsuario` (HTTP 403 na API).
- **Estoque vem só da identidade:** um usuário sem vínculo não recebe estoque (`None`); o `stock_id`
  não é mais aceito no corpo da mensagem (422).
