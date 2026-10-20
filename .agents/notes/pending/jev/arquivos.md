# JeV — próximos usos

Com `LLM__GATEWAY__API_KEY`, o JeV (`infra/llm/jev/`, Decisions API do Vercel AI Gateway) já
decide em três pontos, cada um caindo no LLM se falhar: guardrail de entrada (`choice` da
categoria), roteador (um `predicate` por especialista + `etapas`; o LLM só entra pra escrever
resposta direta) e juiz (`choice` de grounding + `predicate` de relevância e completude; o feedback
vira frase fixa por critério). O contrato mapeia os três tipos (predicado, escolha, nota).

Pegadinhas do contrato e do gateway: `.agents/skills/jev.md`. Nada disso foi testado ao vivo: a conta Vercel ainda precisa de cartão cadastrado (ver
`pending/requisitos-disciplina/arquivos.md`). Comparar com `observability/RELATORIO.md` antes de manter.

Observabilidade: `frigus_jev_decisions_total{uso, pergunta, escolha, modelo}` (escolha inclui `recusa` e
`invalida`; `modelo` mostra se respondeu o JeV ou a reserva) e `frigus_jev_confidence{uso}`, mais
latência/erro em `frigus_external_call_*{target="jev"}`. Painéis "JeV: ..." no Grafana. Cada uso
novo passa o próprio `uso` pro `decidir`/`escolher`.

Próximos usos, em ordem de prioridade:

1. **Triagem do guardrail de saída.** `choice` entre `adequada`/`corrigir`/`incerta` antes do
   revisor; o revisor (LLM) só roda se não for `adequada`. Só compensa se evitar chamadas de verdade.
2. **Categoria do produto** no cadastro de estoque/compras: produto já cadastrado reaproveita a
   categoria; categoria informada é respeitada; produto novo sem categoria pergunta ao JeV
   (`Category` + `indefinida` → pede esclarecimento). Exige o caminho da tool assíncrono.
3. **Resolução de nome de produto** (ideia, sem urgência): limpar o nome (NFC + espaços) → busca
   exata → candidatos do estoque do usuário → JeV escolhe entre eles, `nenhum` ou `ambiguo` →
   revalida o ID no banco antes de operar. Falta a busca de candidatos; no máximo 255 opções.

Não usar limiar de `confidence` sem calibrar com exemplos do Frigus.
