from typing import Required, TypedDict
from enum import StrEnum


class ResultadoGuardrail(TypedDict, total=False):
    bloqueado: Required[bool]
    motivo:    Required[str]
    mensagem:  str
    conteudo:  str


class Categoria(StrEnum):
    APROVADO        = "APROVADO"
    OFENSIVO        = "OFENSIVO"
    PERIGOSO        = "PERIGOSO"
    ILICITO         = "ILICITO"
    POLITICO        = "POLITICO"
    CONSELHO_MEDICO = "CONSELHO_MEDICO"


# PII do usuário — redige na entrada E na saída
PII_USUARIO = [
    ("CPF",   r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}"),
    ("CNPJ",  r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}"),
    ("SENHA", r"(?i)senha[:\s]+\S+"),
]

PII = PII_USUARIO + [
    ("EMAIL",    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    ("TELEFONE", r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}"),
]


# Padroes para detectar tentativas de jailbreak/injeção
_PADROES_INJECAO = [
    r"ignore\s+(as\s+)?instru[çc][oõ]es",
    r"ignore\s+previous\s+instructions",
    r"forget\s+your\s+instructions",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(if\s+)?",
    r"pretend\s+(you\s+are|to\s+be)",
    r"jailbreak",
    r"dan\s+mode",
    r"modo\s+irrestrito",
    r"system\s*prompt",
    r"<\s*system\s*>",
    r"\[INST\]",
    r"###\s*instruction",
    r"override\s+(your\s+)?instructions",
    r"desconsider[ea]\s+(suas\s+)?instru[çc][oõ]es",
]

_KEYWORDS_DADOS_INTERNOS = [
    "prompt do sistema", "system prompt", "suas instruções", "your instructions",
    "variável de ambiente", "chave de api", "api key", "senha do sistema",
    "token de acesso", "banco de dados interno", "tabela interna",
    "dados de outros usuários", "lista de usuários", "credenciais",
    "hash_password", "search_path",
]

_RESPOSTAS_BLOQUEIO = {
    "OFENSIVO":        ("conteudo_ofensivo", "Por favor, mantenha um tom respeitoso para que eu possa te ajudar."),
    "PERIGOSO":        ("pedido_perigoso",   "Não posso ajudar com esse tipo de solicitação."),
    "ILICITO":         ("pedido_ilicito",    "Não posso auxiliar com atividades ilegais ou irregulares."),
    "POLITICO":        ("pergunta_politica", "Não me envolvo em temas políticos. Posso ajudar com seu estoque, compras, receitas ou finanças domésticas."),
    "CONSELHO_MEDICO": ("conselho_medico",   "Não posso dar conselhos de saúde, nutrição clínica ou diagnóstico — procure um profissional. Posso ajudar com estoque, compras ou receitas."),
}
