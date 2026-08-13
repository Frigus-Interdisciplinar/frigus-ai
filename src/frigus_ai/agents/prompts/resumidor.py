from frigus_ai.agents.prompts.base import GenericAgent


class ResumidorPrompt(GenericAgent):
    PAPEL = """
    Resuma a conversa abaixo entre o usuário e o Frigus.AI em até 5 linhas,
    destacando: produtos mencionados, decisões de compra, preferências alimentares
    e qualquer pendência em aberto. Seja objetivo, sem repetir a conversa literalmente.

    CONVERSA:
    {conversa}
    """


class PerfilPrompt(GenericAgent):
    PAPEL = """
    Você mantém um perfil comportamental curto (até 6 linhas) sobre os hábitos do
    usuário no Frigus.AI: preferências alimentares, categorias mais consumidas,
    frequência de compras, tendência a desperdício e preferências de receita.

    Atualize o perfil abaixo incorporando o novo resumo de conversa, mantendo apenas
    o que ainda for relevante (não apenas concatene, sintetize).

    PERFIL ATUAL:
    {perfil_atual}

    NOVO RESUMO:
    {resumo}
    """
