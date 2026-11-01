# Diagnóstico de estoque e receitas no mobile

## Evidência local, sem gravação de domínio

Em 2026-11-01 a consulta SQL e a consulta ORM do ambiente local encontraram o lote
34901, estoque 1813: Suco De Frutas, 43 unidades, BEVERAGE/FRIDGE, FRESH e validade
2028-07-28. A tool `query_stock(storage_place="Geladeira")`, executada por `ainvoke`
com o ContextVar do estoque, retornou o mesmo item. O engine foi limitado a
transações read-only durante os diagnósticos. Não há filtro implícito que elimine
bebidas nessa consulta. Não foi chamado o endpoint de chat nem persistido histórico
no Mongo durante os testes reais.

`match_recipes_to_stock`, no turno Core com persistência desabilitada, retornou
sucesso com zero receitas compatíveis para esse estoque. Isso é diferente de uma
exceção do provedor; não deve ser descrito como falha de banco ou estoque vazio.

A configuração local efetiva não tem chave do gateway, nem alias antigo com valor
que pudesse ser migrado. Groq e OpenRouter estão configurados. As chamadas reais
isoladas reproduziram:

- Groq `openai/gpt-oss-120b`: HTTP 400 `tool_use_failed`, tentativa de invocar uma
  ferramenta chamada `JSON`, que não existe nas tools fornecidas.
- Groq: HTTP 429 `rate_limit_exceeded`, por tokens por minuto (limite 8.000), não
  prova de esgotamento de cota diária.
- OpenRouter `qwen/qwen3.8-27b:free`: HTTP 404, informando indisponibilidade da
  modalidade gratuita. Não foi trocado por um modelo pago.

A documentação oficial do Groq confirma o limite base e a compatibilidade com
tools: https://console.groq.com/docs/rate-limits e
https://console.groq.com/docs/tool-use/overview. A página oficial do OpenRouter
ainda apresenta a modalidade gratuita, mas a chamada real desta chave retornou
404: https://openrouter.ai/qwen/qwen3.8-27b%3Afree.
Disponibilidade de catálogo e disponibilidade real para uma chave não são a mesma
evidência. Esses resultados são locais; configuração e disponibilidade em Render
não foram verificadas nesta tarefa.

## Ajustes

- `graph/prompts/estoque.md`: deixa explícito consultar `query_stock` no turno,
  distinguir nome de local de nome de produto e não transformar erro em estoque
  vazio. JSON é apenas o texto final, nunca o nome de uma ferramenta.
- `domain/errors.py`: erro de domínio `ProvedorIAIndisponivel`, HTTP 503 e código
  `provedor_ia_indisponivel`.
- `services/chat_service.py`: falhas SDK de Groq/OpenAI no grafo são traduzidas
  para esse erro seguro antes de persistir o turno. O log contém somente classe e
  status, sem mensagem bruta, pergunta, credencial ou payload do provedor.
- `graph/nodes/router.py`: falha SDK do provedor também é propagada como 503,
  em vez de fingir que o pedido do usuário foi confuso. Saída estruturada inválida
  continua usando o fallback genérico existente.
- `tests/services/test_chat_provider_errors.py`: cobre 400/429/404, preservação do
  estoque recebido, ausência de persistência/segredos e resposta HTTP 503 segura
  na rota Core.

Depois do ajuste de prompt, uma nova execução real isolada do especialista de
estoque chamou `query_stock` e respondeu com Suco De Frutas, 43 unidades, validade
28/07/2028 e status Fresco. Nenhum dado fictício foi usado para contornar o erro.

O `.env`, os modelos configurados, a política de preços e o WIP preexistente de
Core mobile/receitas foram preservados. Não há segredo disponível que permita
habilitar o gateway automaticamente. Não foi feito deploy.

## Contrato legado

No código Python atual, `POST /v1/chats` não recebe estoque no corpo; o estoque é
resolvido pela identidade da autenticação. `MessageCreate` aceita somente
`content` e tem `extra="forbid"`: enviar `stock_id` para a rota legada produz 422.
Com autenticação pública desligada, o usuário é o primeiro usuário local com
estoque, não a identidade do mobile. A integração WIP `/internal/core/chat` recebe
userId/stockId explícitos, verifica acesso e propaga o estoque ao runner.

## Validação e comandos

47 testes direcionados passaram na primeira execução. A suíte completa final
passou com **470 testes e 5 avisos em 405,22 segundos**, incluindo os sete casos
novos (três falhas de serviço, três falhas do roteador e o contrato HTTP 503).
A coleta dos sete casos foi conferida no cache do pytest. Ruff nos quatro
arquivos Python modificados e `git diff --check` passaram. Os avisos são
deprecações existentes de Starlette/Google/Neo4j e o índice do Qdrant local.

Comandos sem segredos, a partir da raiz:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check src/frigus_ai/domain/errors.py src/frigus_ai/services/chat_service.py src/frigus_ai/graph/nodes/router.py tests/services/test_chat_provider_errors.py
```

`uv` não estava no PATH desta sessão. O venv existente declara Python 3.14.7,
enquanto o pyproject exige 3.13; o ambiente não foi alterado. Não houve commit,
push, edição de credenciais nem conversa real com persistência.
