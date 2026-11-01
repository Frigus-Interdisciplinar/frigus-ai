# 🚀 Pull Request

## 📌 Contexto

O mobile precisa consultar o estoque da conta autenticada pelo Core, sem depender da identidade de uma chave compartilhada da API pública da IA. A sugestão de receitas também precisa devolver IDs reais do catálogo que possam ser confirmados pelo Core.

No diagnóstico local, o lote de Suco De Frutas existia no estoque solicitado e era retornado pelo SQL e pela tool. As falhas reproduzidas ocorreram nos provedores: chamada de uma ferramenta inexistente chamada `JSON`, limite de tokens por minuto e indisponibilidade do modelo gratuito de reserva. Essas falhas não devem virar estoque vazio, pedido incompreendido ou turno fictício persistido.

## 🛠️ O que foi feito?

- [x] Adicionada a ponte privada `POST /internal/core/chat`, com chave de serviço, validação do contrato, autorização do estoque e ownership da conversa.
- [x] Propagados usuário, estoque e preferências atuais por contexto do turno; receitas consultadas e efetivamente escolhidas retornam como IDs reais do catálogo, sem gravar candidatos automaticamente no fluxo Core.
- [x] Mantidos os contratos públicos existentes; o mobile continua consumindo o BFF, e o Core confirma as sugestões antes de responder ao aplicativo.
- [x] Traduzidas falhas SDK de Groq/OpenAI para HTTP 503 com código `provedor_ia_indisponivel`, sem payload técnico ou credencial na resposta e sem persistir o turno falho.
- [x] Preservado o fallback de interpretação para saída estruturada inválida; falha do provedor no roteador passou a ser distinguida de pedido incompreendido.
- [x] Explicitado no prompt de estoque que a consulta usa `query_stock`, que local de armazenamento não é nome de produto e que `JSON` é apenas o formato do texto final.
- [x] Documentada em `.env.example` a variável da chave de serviço. Nenhuma credencial foi incluída neste PR, e nenhum modelo pago foi habilitado como alternativa automática.

## 🧪 Como validar?

1. Na raiz do repositório, executar:

   ```powershell
   .venv/Scripts/python.exe -m pytest -q
   .venv/Scripts/python.exe -m ruff check src/frigus_ai/domain/errors.py src/frigus_ai/services/chat_service.py src/frigus_ai/graph/nodes/router.py tests/services/test_chat_provider_errors.py
   ```

   Resultado já confirmado nesta revisão: **470 testes passaram, com 5 avisos, em 405,22 segundos**; Ruff nos quatro arquivos acima e `git diff --check` passaram. A suíte inclui os sete casos novos de falha de provedor/roteador e contrato HTTP 503.

2. Conferir os testes da ponte Core: chave ausente/incorreta não cria conversa; estoque sem acesso e conversa de outra conta são bloqueados; usuário/estoque/preferências chegam ao turno; apenas IDs consultados e escolhidos são devolvidos; nenhuma receita é inventada quando não há recomendação.

3. Conferir os testes dos provedores: HTTP 400/429/404 não grava turno, não revela a mensagem bruta do SDK e não vira resposta de estoque vazio ou de pedido confuso. A rota interna responde 503 com código identificável.

4. Evidência real de leitura já obtida no ambiente local: SQL, ORM e `query_stock` encontraram Suco De Frutas, 43 unidades, na geladeira do estoque solicitado. Após o ajuste do prompt, o especialista chamou a tool e respondeu com os dados reais. O PostgreSQL foi forçado a transações read-only e o chatbot com persistência não foi acionado.

5. Antes do deploy, repetir a suíte no **Python 3.13 declarado pelo projeto**. A validação acima usou o venv existente, **Python 3.14.7**, fora do intervalo `>=3.13,<3.14` do `pyproject.toml`; o ambiente não foi alterado.

6. No ambiente de implantação, configurar `API_KEYS__CORE_SERVICE_KEY` na IA e `FRIGUS_AI_API_KEY` no Core com o mesmo segredo de serviço, manter `FRIGUS_AI_BASE_URL` como origem da IA e confirmar o PostgreSQL compartilhado. Validar a disponibilidade de um provedor/modelo configurado e depois executar o roteiro autenticado no aplicativo. Esse deploy e essa validação ponta a ponta ainda estão pendentes.

## 🔍 Checklist de Qualidade

- [x] **Auto-review:** Imports corrigidos e conferidos por Ruff; diagnósticos temporários não foram adicionados ao runtime; logs novos contêm somente classe e status da falha, sem pergunta, token ou payload do provedor.
- [x] **Breaking Changes:** A ponte privada exige a nova chave de serviço documentada e implantação coordenada Core/IA. As rotas públicas existentes permanecem. Falhas de provedor agora têm resposta 503 identificável; consumidores devem preservar o tratamento de indisponibilidade e não reenviar operações automaticamente.
- [x] **Performance:** As consultas continuam limitadas ao estoque autorizado. Não foram adicionados loops de reenvio, chamadas pagas automáticas ou consultas de candidatos com persistência no fluxo Core. O limite real de tokens do provedor continua sendo uma restrição operacional.

**Pendências e limites:** a chave do gateway está ausente na configuração local; Groq apresentou limite de tokens por minuto e o modelo gratuito do OpenRouter respondeu indisponível. Não foi feita troca para modelo pago, edição de credenciais, alteração de dependências ou implantação. Esses resultados locais não comprovam a configuração nem a disponibilidade dos provedores em produção. Os cinco avisos dos testes são deprecações existentes de Starlette/Google/Neo4j e índice do Qdrant local.

---

### 📸 Evidências Visuais

<details>
<summary>Clique para expandir</summary>

Não há alteração visual neste repositório. As evidências são os testes automatizados, as consultas read-only e o retorno real da tool/especialista descritos acima. O roteiro no aparelho após implantação coordenada permanece pendente.

</details>
