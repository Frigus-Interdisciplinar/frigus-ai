# Extração estruturada de NFC-e

`POST /v1/invoices/extract` recebe uma lista de objetos de produtos extraídos do HTML da NFC-e, autenticado pela dependência existente de usuário/API key. Não acessa URLs nem recebe o texto completo da página. A IA precisa retornar um produto por entrada, preservar os campos fiscais e enriquecer com nome normalizado, marca, categoria, local de armazenamento, unidade de medida e confiança. Os códigos das categorias, armazenamentos e unidades coincidem com os enums da Core API. A rota reutiliza `estruturado()` e a cadeia Gemini Flash → Groq GPT OSS → OpenRouter Qwen e é limitada a 10 chamadas por minuto.

Arquivos adicionados: `src/frigus_ai/api/routes/v1/invoices.py`, `src/frigus_ai/schemas/invoice.py`, `tests/api/test_invoices.py`. A rota foi registrada em `src/frigus_ai/api/routes/v1/__init__.py`. O contrato substituiu a versão inicial baseada em texto fiscal e mantém sem alterações a autenticação e a persistência da `frigus-ai`.

Validação local após o contrato de produtos: `pytest tests/api/test_invoices.py` (2 aprovados) e `ruff check` nos arquivos alterados. Integração real depende de uma chave válida e cota no provedor de modelo configurado.
