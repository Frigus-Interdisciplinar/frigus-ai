"""
Único módulo Python em agents/prompts/ — os outros arquivos da pasta são só .md.

Cada .md pode ter um header `---\nchave: valor\n---` (metadados, hoje só
`usa_tools_obrigatorias`) seguido de seções `## NOME` (PAPEL, SHOTS, TEMPLATE
etc.). `load_prompt()` monta o system_prompt completo (persona + contexto
temporal + [obrigatoriedade de tools] + papel + [shots]) a partir da seção
PAPEL/SHOTS; `load_sections()` devolve as seções cruas, pra quem precisa de
outra seção (TEMPLATE do Juiz) ou não quer o envelope de persona (Guardrail).
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from frigus_ai.schemas.models import Fatos

_PASTA = Path(__file__).parent
_MARCADOR_SECAO = "## "
_MARCADOR_FRONTMATTER = "---"

PERSONA_SISTEMA = """
### PERSONA
Você é o Frigus.AI — o assistente pessoal do aplicativo Frigus, especialista em gestão de alimentos. Você ajuda o usuário a controlar geladeira, freezer e despensa, reduzir desperdício, aproveitar ingredientes antes do vencimento e planejar compras. Sua principal característica é a objetividade e a confiabilidade. Você é prático, direto e nunca inventa dados sobre o estoque, preços ou receitas que não vieram das tools. Seu objetivo é ser um parceiro confiável para o usuário economizar dinheiro e evitar desperdício de comida.
"""

def contexto_temporal() -> str:
    """Montado a cada chamada, nunca no import: como constante de módulo, um processo de API vivo continuava dizendo "hoje" com a data em que subiu — e "o que vence hoje" é o core do domínio. Por isso `load_prompt` também não pode ser cacheado."""
    agora = datetime.now(UTC).astimezone()

    return f"""
### CONTEXTO TEMPORAL
Data e hora atual (fornecida pelo sistema): {agora.strftime("%A, %d de %B de %Y — %H:%M:%S %Z")}
Use esta referência para interpretar "hoje", "ontem", "essa semana", calcular datas relativas e preencher timestamps nas operações.
"""

OBRIGATORIEDADE_TOOLS = """
### OBRIGATORIEDADE DE TOOLS
- TODA resposta que contenha produtos, quantidades, preços, datas de validade ou receitas DEVE ser precedida de uma chamada de tool nesta mesma execução.
- NUNCA use valores do histórico de conversa como fonte de dados — histórico serve apenas para entender o contexto da pergunta.
- Se a tool retornar erro ou nenhum resultado, informe isso no campo "resposta". Jamais invente um produto, preço ou data substituta.
"""

CONTEXTO_FACTOS = """
### CONTEXTO DE FATOS ESTRUTURADOS
Estes são fatos sobre o usuário extraídos da conversa (alergias, preferências, restrições alimentares e hábitos). Use estas informações para personalizar a resposta, filtrar opções e evitar sugerir itens que conflitam com o perfil do usuário.

- Alergias: {alergias}
- Preferências: {preferencias}
- Restrições: {restricoes}
- Hábitos: {habitos}

Se algum campo estiver vazio, ignore-o e não inclua na resposta. Não invente ou alucine fatos que não estejam nesta lista.
"""

def _formatar_fatos(fatos: Fatos) -> str:
    """Formata objeto Fatos em texto para inclusão no prompt."""
    alergias = ", ".join(fatos.alergias) if fatos.alergias else "nenhuma"
    preferencias = ", ".join(fatos.preferencias) if fatos.preferencias else "nenhuma"
    restricoes = ", ".join(fatos.restricoes) if fatos.restricoes else "nenhuma"
    habitos = ", ".join(fatos.habitos) if fatos.habitos else "nenhuma"
    return CONTEXTO_FACTOS.format(
        alergias=alergias,
        preferencias=preferencias,
        restricoes=restricoes,
        habitos=habitos,
    )


CONTEXTO_CONVERSAS = """
### CONVERSAS ANTERIORES RELEVANTES
Resumos de outras conversas deste usuário parecidas com a pergunta atual. Use só como
contexto (o que ele já pediu, decidiu ou deixou pendente) — nunca como fonte de estoque,
preço ou validade, que mudam e só valem vindos das tools.

{resumos}
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


@lru_cache(maxsize=32)
def _ler(nome_arquivo: str) -> tuple[dict[str, str], dict[str, str]]:
    texto = (_PASTA / nome_arquivo).read_text(encoding="utf-8")
    metadados, corpo = _parse_frontmatter(texto)
    return metadados, _parse_secoes(corpo)


def load_sections(nome_arquivo: str) -> dict[str, str]:
    """Seções cruas do .md (sem persona/contexto), pra quem monta o prompt na mão
    (TEMPLATE do Juiz) ou não quer o envelope de agente nenhum (Guardrail)."""

    _, secoes = _ler(nome_arquivo)
    return secoes


def load_prompt(
    nome_arquivo: str, fatos: Fatos | None = None, conversas: Sequence[str] = ()
) -> str:
    """System prompt completo: persona + contexto temporal +
    [obrigatoriedade de tools, se o frontmatter marcar] + papel + [shots].

    Se `fatos` for fornecido, inclui uma seção CONTEXTO DE FATOS estruturados
    no final do prompt para que o LLM possa usar essas informações na resposta.
    Ordem fixa no fim: fatos (sobre o usuário) antes de conversas (sobre o passado).
    """

    metadados, secoes = _ler(nome_arquivo + ".md")

    partes = [PERSONA_SISTEMA, contexto_temporal()]

    if metadados.get("usa_tools_obrigatorias") == "true":
        partes.append(OBRIGATORIEDADE_TOOLS)

    partes.append(f"### PAPEL\n{secoes.get('papel', '')}")

    if secoes.get("shots"):
        partes.append(secoes["shots"])

    if fatos is not None:
        partes.append(_formatar_fatos(fatos))

    if conversas:
        resumos = "\n".join(f"- {c}" for c in conversas)
        partes.append(CONTEXTO_CONVERSAS.format(resumos=resumos))

    return "\n\n".join(partes)


__all__ = ["contexto_temporal", "load_prompt", "load_sections"]