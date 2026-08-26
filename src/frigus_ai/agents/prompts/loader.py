"""
Único módulo Python em agents/prompts/ — os outros arquivos da pasta são só .md.

Cada .md pode ter um header `---\nchave: valor\n---` (metadados, hoje só
`usa_tools_obrigatorias`) seguido de seções `## NOME` (PAPEL, SHOTS, TEMPLATE
etc.). `load_prompt()` monta o system_prompt completo (persona + contexto
temporal + [obrigatoriedade de tools] + papel + [shots]) a partir da seção
PAPEL/SHOTS; `load_sections()` devolve as seções cruas, pra quem precisa de
outra seção (TEMPLATE do Juiz) ou não quer o envelope de persona (Guardrail).
"""

from datetime import UTC, datetime
from pathlib import Path

_PASTA = Path(__file__).parent
_MARCADOR_SECAO = "## "
_MARCADOR_FRONTMATTER = "---"

_agora = datetime.now(UTC).astimezone()
_data_hora_fmt = _agora.strftime("%A, %d de %B de %Y — %H:%M:%S %Z")

PERSONA_SISTEMA = """
### PERSONA
Você é o Frigus.AI — o assistente pessoal do aplicativo Frigus, especialista em gestão de alimentos.
Você ajuda o usuário a controlar geladeira, freezer e despensa, reduzir desperdício, aproveitar
ingredientes antes do vencimento e planejar compras. Sua principal característica é a objetividade
e a confiabilidade. Você é prático, direto e nunca inventa dados sobre o estoque, preços ou receitas
que não vieram das tools. Seu objetivo é ser um parceiro confiável para o usuário economizar dinheiro
e evitar desperdício de comida.
"""

CONTEXTO_TEMPORAL = f"""
### CONTEXTO TEMPORAL
Data e hora atual (fornecida pelo sistema): {_data_hora_fmt}
Use esta referência para interpretar "hoje", "ontem", "essa semana",
calcular datas relativas e preencher timestamps nas operações.
"""

OBRIGATORIEDADE_TOOLS = """
### OBRIGATORIEDADE DE TOOLS
- TODA resposta que contenha produtos, quantidades, preços, datas de validade ou receitas DEVE
  ser precedida de uma chamada de tool nesta mesma execução.
- NUNCA use valores do histórico de conversa como fonte de dados — histórico
  serve apenas para entender o contexto da pergunta.
- Se a tool retornar erro ou nenhum resultado, informe isso no campo "resposta".
  Jamais invente um produto, preço ou data substituta.
"""


def _parse_frontmatter(texto: str) -> tuple[dict[str, str], str]:
    linhas = texto.splitlines()

    if not linhas or linhas[0].strip() != _MARCADOR_FRONTMATTER:
        return {}, texto

    for i, linha in enumerate(linhas[1:], start=1):
        if linha.strip() != _MARCADOR_FRONTMATTER:
            continue

        metadados = {}
        for linha_meta in linhas[1:i]:
            if ":" in linha_meta:
                chave, valor = linha_meta.split(":", 1)
                metadados[chave.strip()] = valor.strip()

        return metadados, "\n".join(linhas[i + 1 :])

    return {}, texto


def _parse_secoes(texto: str) -> dict[str, str]:
    secoes: dict[str, str] = {}
    nome_atual: str | None = None
    linhas_atuais: list[str] = []

    for linha in texto.splitlines():
        if linha.startswith(_MARCADOR_SECAO):
            if nome_atual:
                secoes[nome_atual] = "\n".join(linhas_atuais).strip()
            nome_atual = linha.removeprefix(_MARCADOR_SECAO).strip().lower()
            linhas_atuais = []
        elif nome_atual:
            linhas_atuais.append(linha)

    if nome_atual:
        secoes[nome_atual] = "\n".join(linhas_atuais).strip()

    return secoes


def _ler(nome_arquivo: str) -> tuple[dict[str, str], dict[str, str]]:
    texto = (_PASTA / nome_arquivo).read_text(encoding="utf-8")
    metadados, corpo = _parse_frontmatter(texto)
    return metadados, _parse_secoes(corpo)


def load_sections(nome_arquivo: str) -> dict[str, str]:
    """Seções cruas do .md (sem persona/contexto), pra quem monta o prompt na mão
    (TEMPLATE do Juiz) ou não quer o envelope de agente nenhum (Guardrail)."""

    _, secoes = _ler(nome_arquivo)
    return secoes


def load_prompt(nome_arquivo: str) -> str:
    """System prompt completo: persona + contexto temporal +
    [obrigatoriedade de tools, se o frontmatter marcar] + papel + [shots]."""

    metadados, secoes = _ler(nome_arquivo + ".md")

    partes = [PERSONA_SISTEMA, CONTEXTO_TEMPORAL]

    if metadados.get("usa_tools_obrigatorias") == "true":
        partes.append(OBRIGATORIEDADE_TOOLS)

    partes.append(f"### PAPEL\n{secoes.get('papel', '')}")

    if secoes.get("shots"):
        partes.append(secoes["shots"])

    return "\n\n".join(partes)


__all__ = ["load_prompt", "load_sections"]
